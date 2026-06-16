# AMADEUS Web Pipeline

FastAPI + static frontend wrapper for running the AMADEUS reconstruction pipeline from a browser upload.

## What It Does

1. Upload an `.mp4` foot/checkerboard video.
2. Store the upload as a pipeline job.
3. Run the configured AMADEUS pipeline command in the background.
4. Collect generated artifacts: `.stl`, `.3mf`, `.json`, `.txt`, `stdout.log`, `stderr.log`.
5. Show processing status and let the user preview/download outputs from the result page.

## Folder Layout

```text
web/
  docker-compose.yml
  backend/
    Dockerfile
    requirements.txt
    app/
      main.py
      database.py
      models.py
      schemas.py
      static/
        index.html
        processing.html
        result.html
        *.js
        styles.css
      uploads/
      jobs/
```

## Pipeline Command Contract

The web app runs the command stored in `AMADEUS_PIPELINE_CMD`.

Supported placeholders:

| Placeholder | Meaning |
| --- | --- |
| `{input_video}` | Uploaded MP4 path inside the web container |
| `{output_dir}` | Per-job output directory |
| `{job_dir}` | Per-job working directory |
| `{upload_id}` | Database upload ID |
| `{original_filename}` | Original uploaded filename |

Current CLI pipeline entrypoint:

```bash
bash /pipeline/run_pipeline.sh {input_video}
```

The web runner remains a wrapper around `AMADEUS_PIPELINE_CMD`. To run the current CLI pipeline inside the web container, mount `../code` as `/pipeline` and make the required GPU, Docker, COLMAP, model, and OrcaSlicer runtime assets available to that container or host environment.

## Demo Mode

If `AMADEUS_PIPELINE_CMD` is empty, the app runs in demo mode:

1. The uploaded MP4 is accepted normally.
2. The processing page shows staged progress for about 90 seconds.
3. The job is marked as completed.
4. A placeholder foot-shaped STL is generated and loaded in the result viewer.

Change the demo duration if needed:

```bash
export AMADEUS_DEMO_DURATION_SECONDS=60
```

## Run With Docker Compose

From this `web/` directory:

```bash
export AMADEUS_PIPELINE_CMD='bash /pipeline/run_pipeline.sh {input_video}'
export AMADEUS_PIPELINE_ARTIFACT_DIRS='/pipeline/print_output'
docker compose up --build
```

Then open:

```text
http://localhost:8000
```

The current `docker-compose.yml` still mounts `../src` as `/pipeline` for scaffold/demo use. For the runnable CLI pipeline, change that mount to `../code:/pipeline` before enabling the command above.

```text
code/run_pipeline.sh
```

## Run Locally Without Docker

Use this mode when Docker Desktop is not installed or `docker` is not available.

From the repository root:

```bash
cd web
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

Local mode stores upload metadata in:

```text
web/backend/app/amadeus_local.db
```

That local database is ignored by Git.

## Output Locations

Each upload creates a local job directory:

```text
web/backend/app/jobs/<job-id>/
  input/
  pipeline_output/
  artifacts/
    model.stl
    project.3mf
    report.json
    report.txt
  logs/
    stdout.log
    stderr.log
```

The result page links to these files automatically when they exist.

## Custom Artifact Search

If the pipeline writes outputs somewhere else, set:

```bash
export AMADEUS_PIPELINE_ARTIFACT_DIRS='/some/output/path:/another/output/path'
```

The same placeholders are supported:

```bash
export AMADEUS_PIPELINE_ARTIFACT_DIRS='{output_dir}:{job_dir}/custom_results'
```

## Failure Debugging

If the pipeline fails, open the result page and download:

- `stderr.log`
- `stdout.log`

If `AMADEUS_PIPELINE_CMD` is empty, uploads will fail with a clear configuration error instead of silently showing a fake result.
