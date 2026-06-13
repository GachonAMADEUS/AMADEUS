from datetime import datetime
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Upload
from .schemas import ResultResponse, UploadResponse


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
UPLOAD_DIR = APP_DIR / "uploads"
JOBS_DIR = APP_DIR / "jobs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_CMD_TEMPLATE = os.getenv("AMADEUS_PIPELINE_CMD", "").strip()
PIPELINE_CWD = os.getenv("AMADEUS_PIPELINE_CWD", "").strip()
PIPELINE_ARTIFACT_DIRS = os.getenv("AMADEUS_PIPELINE_ARTIFACT_DIRS", "").strip()
DEMO_DURATION_SECONDS = int(os.getenv("AMADEUS_DEMO_DURATION_SECONDS", "90"))
DEMO_STL_SOURCE = STATIC_DIR / "models" / "UMesh_final_foot_03.stl"

ARTIFACT_FILENAMES = {
    "stl": "model.stl",
    "3mf": "project.3mf",
    "json": "report.json",
    "txt": "report.txt",
    "stdout": "stdout.log",
    "stderr": "stderr.log",
}

app = FastAPI(title="Amadeus Web Pipeline")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def ensure_upload_columns():
    inspector = inspect(engine)
    if not inspector.has_table("uploads"):
        return

    existing = {column["name"] for column in inspector.get_columns("uploads")}
    columns = {
        "progress": "INT NOT NULL DEFAULT 0",
        "stage": "VARCHAR(255) NOT NULL DEFAULT 'queued'",
        "error_message": "TEXT NULL",
        "job_dir": "VARCHAR(1024) NULL",
        "input_path": "VARCHAR(1024) NULL",
        "stdout_path": "VARCHAR(1024) NULL",
        "stderr_path": "VARCHAR(1024) NULL",
        "result_stl_path": "VARCHAR(1024) NULL",
        "result_3mf_path": "VARCHAR(1024) NULL",
        "result_report_path": "VARCHAR(1024) NULL",
        "result_json_path": "VARCHAR(1024) NULL",
        "started_at": "DATETIME NULL",
        "finished_at": "DATETIME NULL",
    }

    with engine.begin() as connection:
        for name, ddl in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE uploads ADD COLUMN {name} {ddl}"))


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_upload_columns()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/processing")
def processing():
    return FileResponse(STATIC_DIR / "processing.html")


@app.get("/result")
def result():
    return FileResponse(STATIC_DIR / "result.html")


def render_template(value: str, context: dict[str, str], *, shell_quote: bool) -> str:
    rendered = value
    for key, raw in context.items():
        replacement = shlex.quote(raw) if shell_quote else raw
        rendered = rendered.replace("{" + key + "}", replacement)
    return rendered


def default_pipeline_command() -> str | None:
    if PIPELINE_CMD_TEMPLATE:
        return PIPELINE_CMD_TEMPLATE

    for candidate in (Path("/pipeline/pipeline.py"), Path("/pipeline/main.py")):
        if candidate.exists():
            return f"python {candidate} --input-video {{input_video}} --output-dir {{output_dir}}"

    return None


def artifact_url(upload_id: int, artifact_key: str, path_value: str | None) -> str | None:
    if not path_value or not Path(path_value).exists():
        return None
    filename = ARTIFACT_FILENAMES[artifact_key]
    return f"/api/uploads/{upload_id}/artifacts/{filename}"


def set_job_state(
    db: Session,
    record: Upload,
    *,
    status: str,
    progress: int,
    stage: str,
    error_message: str | None = None,
):
    record.status = status
    record.progress = max(0, min(100, progress))
    record.stage = stage
    record.error_message = error_message
    db.add(record)
    db.commit()
    db.refresh(record)


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def artifact_search_roots(job_dir: Path, output_dir: Path, context: dict[str, str]) -> list[Path]:
    roots = [output_dir, job_dir]

    if PIPELINE_CWD:
        cwd = Path(render_template(PIPELINE_CWD, context, shell_quote=False))
        roots.extend([cwd / "output", cwd / "outputs", cwd / "reports"])

    if PIPELINE_ARTIFACT_DIRS:
        for raw in PIPELINE_ARTIFACT_DIRS.split(os.pathsep):
            raw = raw.strip()
            if raw:
                roots.append(Path(render_template(raw, context, shell_quote=False)))

    return [root for root in unique_paths(roots) if root.exists()]


def find_artifact(roots: list[Path], suffixes: tuple[str, ...], preferred_words: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                candidates.append(path)

    if not candidates:
        return None

    def score(path: Path) -> tuple[int, float]:
        name = path.name.lower()
        keyword_score = sum(1 for word in preferred_words if word in name)
        return keyword_score, path.stat().st_mtime

    return sorted(candidates, key=score, reverse=True)[0]


def copy_artifact(source: Path | None, destination: Path) -> str | None:
    if source is None:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return str(destination)


def collect_pipeline_artifacts(record: Upload, job_dir: Path, output_dir: Path, context: dict[str, str]):
    artifacts_dir = job_dir / "artifacts"
    roots = artifact_search_roots(job_dir, output_dir, context)

    stl = find_artifact(roots, (".stl",), ("final", "scaled", "repaired", "processed", "foot"))
    project = find_artifact(roots, (".3mf",), ("final", "project", "sliced", "bambu", "foot"))
    report_json = find_artifact(roots, (".json",), ("report", "summary", "measurement", "result"))
    report_txt = find_artifact(roots, (".txt",), ("report", "summary", "result"))

    record.result_stl_path = copy_artifact(stl, artifacts_dir / ARTIFACT_FILENAMES["stl"])
    record.result_3mf_path = copy_artifact(project, artifacts_dir / ARTIFACT_FILENAMES["3mf"])
    record.result_json_path = copy_artifact(report_json, artifacts_dir / ARTIFACT_FILENAMES["json"])
    record.result_report_path = copy_artifact(report_txt, artifacts_dir / ARTIFACT_FILENAMES["txt"])


def ellipsoid_vertices(
    center: tuple[float, float, float],
    scale: tuple[float, float, float],
    lat_segments: int,
    lon_segments: int,
) -> list[list[tuple[float, float, float]]]:
    vertices: list[list[tuple[float, float, float]]] = []
    cx, cy, cz = center
    sx, sy, sz = scale

    for lat in range(lat_segments + 1):
        theta = math.pi * lat / lat_segments
        row: list[tuple[float, float, float]] = []
        for lon in range(lon_segments + 1):
            phi = 2 * math.pi * lon / lon_segments
            x = cx + sx * math.sin(theta) * math.cos(phi)
            y = cy + sy * math.cos(theta)
            z = cz + sz * math.sin(theta) * math.sin(phi)
            row.append((x, y, z))
        vertices.append(row)

    return vertices


def add_ellipsoid_triangles(
    triangles: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]],
    center: tuple[float, float, float],
    scale: tuple[float, float, float],
    *,
    lat_segments: int = 16,
    lon_segments: int = 32,
):
    vertices = ellipsoid_vertices(center, scale, lat_segments, lon_segments)

    for lat in range(lat_segments):
        for lon in range(lon_segments):
            p1 = vertices[lat][lon]
            p2 = vertices[lat + 1][lon]
            p3 = vertices[lat + 1][lon + 1]
            p4 = vertices[lat][lon + 1]

            if lat != 0:
                triangles.append((p1, p2, p4))
            if lat != lat_segments - 1:
                triangles.append((p2, p3, p4))


def write_demo_foot_stl(path: Path):
    triangles: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = []
    parts = [
        ((0.0, 0.22, 0.0), (1.05, 0.28, 2.05)),
        ((0.0, 0.32, -1.52), (0.82, 0.42, 0.64)),
        ((0.0, 0.42, -0.35), (0.82, 0.36, 0.95)),
        ((0.0, 0.38, 1.25), (1.08, 0.34, 0.72)),
        ((-0.58, 0.45, 1.88), (0.25, 0.21, 0.34)),
        ((-0.28, 0.48, 2.03), (0.28, 0.23, 0.42)),
        ((0.04, 0.5, 2.08), (0.3, 0.24, 0.46)),
        ((0.36, 0.47, 1.98), (0.26, 0.22, 0.38)),
        ((0.64, 0.43, 1.82), (0.22, 0.2, 0.31)),
    ]

    for center, scale in parts:
        add_ellipsoid_triangles(triangles, center, scale)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stl:
        stl.write("solid amadeus_demo_foot\n")
        for triangle in triangles:
            stl.write("  facet normal 0 0 0\n")
            stl.write("    outer loop\n")
            for vertex in triangle:
                stl.write(f"      vertex {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
            stl.write("    endloop\n")
            stl.write("  endfacet\n")
        stl.write("endsolid amadeus_demo_foot\n")


def run_demo_pipeline(db: Session, record: Upload, job_dir: Path, output_dir: Path):
    artifacts_dir = job_dir / "artifacts"
    logs_dir = job_dir / "logs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = logs_dir / ARTIFACT_FILENAMES["stdout"]
    stderr_path = logs_dir / ARTIFACT_FILENAMES["stderr"]
    stl_path = artifacts_dir / ARTIFACT_FILENAMES["stl"]
    report_json_path = artifacts_dir / ARTIFACT_FILENAMES["json"]
    report_txt_path = artifacts_dir / ARTIFACT_FILENAMES["txt"]

    record.stdout_path = str(stdout_path)
    record.stderr_path = str(stderr_path)
    record.result_stl_path = str(stl_path)
    record.result_json_path = str(report_json_path)
    record.result_report_path = str(report_txt_path)
    db.commit()

    demo_steps = [
        ("frame filtering", 15),
        ("segmentation", 35),
        ("3D reconstruction", 60),
        ("mesh postprocessing", 82),
        ("STL export", 95),
    ]
    step_delay = max(1, DEMO_DURATION_SECONDS) / len(demo_steps)

    stdout_lines = [
        "AMADEUS demo mode started.",
        "No AMADEUS_PIPELINE_CMD was configured, so a prototype STL will be generated.",
    ]

    for stage, progress in demo_steps:
        set_job_state(db, record, status="running", progress=progress, stage=stage)
        stdout_lines.append(f"{datetime.utcnow().isoformat()} {stage} {progress}%")
        time.sleep(step_delay)

    if DEMO_STL_SOURCE.exists():
        shutil.copy2(DEMO_STL_SOURCE, stl_path)
        demo_result_note = "Bundled UMesh_final_foot_03.stl was used as the demo result."
    else:
        write_demo_foot_stl(stl_path)
        demo_result_note = "Fallback placeholder STL was generated because the bundled demo STL was missing."

    report = {
        "mode": "demo",
        "status": "completed",
        "input_file": record.original_filename,
        "duration_seconds": DEMO_DURATION_SECONDS,
        "source_stl": str(DEMO_STL_SOURCE) if DEMO_STL_SOURCE.exists() else None,
        "artifacts": {
            "stl": str(stl_path),
            "report_json": str(report_json_path),
            "report_txt": str(report_txt_path),
        },
        "note": demo_result_note,
    }

    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_txt_path.write_text(
        "\n".join(
            [
                "AMADEUS Demo Report",
                "===================",
                f"Input file: {record.original_filename}",
                f"Duration: {DEMO_DURATION_SECONDS} seconds",
                f"Result: {demo_result_note}",
                "",
                "This report is generated by demo mode.",
            ]
        ),
        encoding="utf-8",
    )
    stdout_path.write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")

    record.finished_at = datetime.utcnow()
    set_job_state(db, record, status="completed", progress=100, stage="completed")


def run_pipeline_job(upload_id: int):
    db = SessionLocal()
    try:
        record = db.get(Upload, upload_id)
        if record is None:
            return

        job_dir = Path(record.job_dir or JOBS_DIR / str(upload_id))
        input_video = Path(record.input_path or UPLOAD_DIR / record.stored_filename)
        output_dir = job_dir / "pipeline_output"
        logs_dir = job_dir / "logs"
        output_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        stdout_path = logs_dir / ARTIFACT_FILENAMES["stdout"]
        stderr_path = logs_dir / ARTIFACT_FILENAMES["stderr"]
        record.stdout_path = str(stdout_path)
        record.stderr_path = str(stderr_path)
        record.started_at = datetime.utcnow()
        set_job_state(db, record, status="running", progress=10, stage="pipeline starting")

        command_template = default_pipeline_command()
        if not command_template:
            run_demo_pipeline(db, record, job_dir, output_dir)
            return

        context = {
            "input_video": str(input_video),
            "job_dir": str(job_dir),
            "output_dir": str(output_dir),
            "upload_id": str(record.id),
            "original_filename": record.original_filename,
        }
        command = render_template(command_template, context, shell_quote=True)
        cwd = render_template(PIPELINE_CWD, context, shell_quote=False) if PIPELINE_CWD else str(job_dir)

        set_job_state(db, record, status="running", progress=20, stage="pipeline running")
        with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
            completed = subprocess.run(
                command,
                cwd=cwd if Path(cwd).exists() else str(job_dir),
                shell=True,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                check=False,
            )

        record.finished_at = datetime.utcnow()
        if completed.returncode != 0:
            set_job_state(
                db,
                record,
                status="failed",
                progress=100,
                stage="pipeline failed",
                error_message=f"Pipeline exited with code {completed.returncode}. Check stderr.log.",
            )
            db.commit()
            return

        set_job_state(db, record, status="running", progress=90, stage="collecting artifacts")
        collect_pipeline_artifacts(record, job_dir, output_dir, context)

        if not record.result_stl_path and not record.result_3mf_path:
            set_job_state(
                db,
                record,
                status="failed",
                progress=100,
                stage="artifacts missing",
                error_message="Pipeline finished, but no STL or 3MF artifact was found.",
            )
        else:
            set_job_state(db, record, status="completed", progress=100, stage="completed")
        db.commit()
    except Exception as exc:
        record = db.get(Upload, upload_id)
        if record is not None:
            record.finished_at = datetime.utcnow()
            set_job_state(
                db,
                record,
                status="failed",
                progress=100,
                stage="server error",
                error_message=str(exc),
            )
    finally:
        db.close()


@app.post("/api/uploads", response_model=UploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only .mp4 files are supported.")

    stored_filename = f"{uuid4().hex}.mp4"
    job_token = uuid4().hex
    job_dir = JOBS_DIR / job_token
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    destination = input_dir / stored_filename

    with destination.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    record = Upload(
        original_filename=filename,
        stored_filename=stored_filename,
        status="queued",
        progress=5,
        stage="queued",
        job_dir=str(job_dir),
        input_path=str(destination),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    background_tasks.add_task(run_pipeline_job, record.id)
    return record


@app.get("/api/uploads/{upload_id}", response_model=UploadResponse)
def get_upload(upload_id: int, db: Session = Depends(get_db)):
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return record


@app.get("/api/result/{upload_id}", response_model=ResultResponse)
def get_result(upload_id: int, db: Session = Depends(get_db)):
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    if record.status == "completed":
        message = "Pipeline result is ready."
    elif record.status == "failed":
        message = "Pipeline failed. Check the logs for details."
    else:
        message = "Pipeline is still running."

    return ResultResponse(
        upload_id=record.id,
        status=record.status,
        progress=record.progress,
        stage=record.stage,
        message=message,
        model_stl_url=artifact_url(record.id, "stl", record.result_stl_path),
        project_3mf_url=artifact_url(record.id, "3mf", record.result_3mf_path),
        report_json_url=artifact_url(record.id, "json", record.result_json_path),
        report_txt_url=artifact_url(record.id, "txt", record.result_report_path),
        stdout_url=artifact_url(record.id, "stdout", record.stdout_path),
        stderr_url=artifact_url(record.id, "stderr", record.stderr_path),
        error_message=record.error_message,
    )


@app.get("/api/uploads/{upload_id}/artifacts/{filename}")
def get_upload_artifact(upload_id: int, filename: str, db: Session = Depends(get_db)):
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    path_map = {
        ARTIFACT_FILENAMES["stl"]: record.result_stl_path,
        ARTIFACT_FILENAMES["3mf"]: record.result_3mf_path,
        ARTIFACT_FILENAMES["json"]: record.result_json_path,
        ARTIFACT_FILENAMES["txt"]: record.result_report_path,
        ARTIFACT_FILENAMES["stdout"]: record.stdout_path,
        ARTIFACT_FILENAMES["stderr"]: record.stderr_path,
    }
    path_value = path_map.get(filename)
    if not path_value:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    path = Path(path_value)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file is missing.")

    return FileResponse(path, filename=filename)


@app.get("/api/models/stl")
def list_stl_models():
    models = []
    for path in sorted(STATIC_DIR.rglob("*.stl")):
        relative_path = path.relative_to(STATIC_DIR).as_posix()
        models.append(
            {
                "name": path.name,
                "path": relative_path,
                "url": f"/static/{relative_path}",
            }
        )
    return {"models": models}
