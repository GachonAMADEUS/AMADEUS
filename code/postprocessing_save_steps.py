# postprocessing_save_steps.py
import argparse
import os
import shutil
import time
from pathlib import Path

import numpy as np
import trimesh


def clean_mesh(mesh):
    mesh.remove_unreferenced_vertices()

    try:
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.remove_unreferenced_vertices()
    except Exception:
        pass

    try:
        mesh.merge_vertices(digits_vertex=6)
    except Exception:
        try:
            mesh.merge_vertices()
        except Exception:
            pass

    try:
        unique = mesh.unique_faces()
        mesh.update_faces(unique)
        mesh.remove_unreferenced_vertices()
    except Exception:
        pass

    try:
        mesh.fix_normals()
    except Exception:
        pass

    return mesh


def keep_largest_component(mesh):
    parts = mesh.split(only_watertight=False)
    if len(parts) == 0:
        return mesh
    return max(parts, key=lambda m: len(m.vertices))


def keep_origin_scored_component(
    mesh,
    origin=(0.0, 0.0, 0.0),
    min_vertex_ratio=0.10,
    distance_tolerance=0.05,
):
    parts = mesh.split(only_watertight=False)
    if len(parts) == 0:
        return mesh
    if len(parts) == 1:
        return parts[0]

    origin = np.asarray(origin, dtype=np.float64)
    max_vertices = max(len(part.vertices) for part in parts)
    min_vertices = max(1, int(np.ceil(max_vertices * min_vertex_ratio)))

    infos = []
    for idx, part in enumerate(parts):
        vertex_count = len(part.vertices)
        centroid = np.mean(part.vertices, axis=0)
        distance = float(np.linalg.norm(centroid - origin))

        infos.append({
            "idx": idx,
            "mesh": part,
            "vertices": vertex_count,
            "size_ratio": vertex_count / max_vertices,
            "centroid": centroid,
            "distance": distance,
        })

    candidates = [info for info in infos if info["vertices"] >= min_vertices]
    if len(candidates) == 0:
        candidates = infos

    closest_distance = min(info["distance"] for info in candidates)
    tie_distance = closest_distance * (1.0 + distance_tolerance)
    for info in candidates:
        info["distance_ratio"] = (
            info["distance"] / closest_distance
            if closest_distance > 1e-12
            else 1.0
        )
        info["in_tie_group"] = info["distance"] <= tie_distance

    tie_group = [info for info in candidates if info["in_tie_group"]]
    chosen = max(tie_group, key=lambda info: info["vertices"])

    print(
        "[component select] "
        f"parts={len(parts)}, candidates={len(candidates)}, "
        f"min_vertices={min_vertices}, origin={origin.tolist()}, "
        f"closest_distance={closest_distance:.6f}, "
        f"distance_tolerance={distance_tolerance:.4f}, "
        f"tie_distance={tie_distance:.6f}, selected_idx={chosen['idx']}"
    )
    for rank, info in enumerate(
        sorted(candidates, key=lambda item: (item["distance"], -item["vertices"]))[:10],
        start=1,
    ):
        centroid = info["centroid"]
        print(
            f"  #{rank}: idx={info['idx']}, V={info['vertices']}, "
            f"size_ratio={info['size_ratio']:.4f}, "
            f"distance={info['distance']:.6f}, "
            f"distance_ratio={info['distance_ratio']:.4f}, "
            f"in_tie_group={info['in_tie_group']}, "
            f"centroid=({centroid[0]:.6f}, {centroid[1]:.6f}, {centroid[2]:.6f})"
        )

    return chosen["mesh"]


def safe_slice(mesh, plane_normal, plane_origin):
    sliced = trimesh.intersections.slice_mesh_plane(
        mesh,
        plane_normal=plane_normal,
        plane_origin=plane_origin,
        cap=False
    )
    if sliced is None or sliced.is_empty:
        raise ValueError("절단 후 메시가 비었습니다.")
    return sliced


def boundary_edges(mesh):
    # 한 번만 등장하는 edge = boundary edge
    edges = mesh.edges_sorted
    edges_unique, counts = np.unique(edges, axis=0, return_counts=True)
    b_edges = edges_unique[counts == 1]
    return b_edges


def edges_to_loops(edges):
    # boundary edge들을 vertex loop들로 연결
    from collections import defaultdict

    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)

    visited_edges = set()
    loops = []

    def edge_key(u, v):
        return tuple(sorted((u, v)))

    for a, b in edges:
        ek = edge_key(a, b)
        if ek in visited_edges:
            continue

        loop = [a, b]
        visited_edges.add(ek)

        current = b
        prev = a

        while True:
            nbrs = adj[current]
            candidates = [x for x in nbrs if x != prev]

            next_v = None
            for c in candidates:
                ek2 = edge_key(current, c)
                if ek2 not in visited_edges:
                    next_v = c
                    break

            if next_v is None:
                # 닫힌 루프인지 확인
                if loop[0] in adj[current]:
                    break
                else:
                    # 열린 체인이면 버림
                    loop = None
                    break

            loop.append(next_v)
            visited_edges.add(edge_key(current, next_v))
            prev, current = current, next_v

            if next_v == loop[0]:
                break

        if loop is not None:
            # 마지막이 시작점이면 제거
            if loop[-1] == loop[0]:
                loop = loop[:-1]
            if len(loop) >= 3:
                loops.append(loop)

    return loops


def polygon_area_2d(points2d):
    x = points2d[:, 0]
    y = points2d[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - y * np.roll(x, -1))


def triangulate_loop_xy(loop_points_3d):
    import mapbox_earcut as earcut

    pts2d = loop_points_3d[:, :2]

    # 연속 중복점 제거
    cleaned = [pts2d[0]]
    for i in range(1, len(pts2d)):
        if np.linalg.norm(pts2d[i] - cleaned[-1]) > 1e-8:
            cleaned.append(pts2d[i])

    pts2d = np.asarray(cleaned, dtype=np.float64)

    # 시작점-끝점이 같으면 마지막 점 제거
    if len(pts2d) >= 2 and np.linalg.norm(pts2d[0] - pts2d[-1]) < 1e-8:
        pts2d = pts2d[:-1]

    if len(pts2d) < 3:
        return None, None

    # 단일 외곽 루프만 있으므로 "마지막 인덱스"만 넘기면 됨
    ring_end_indices = np.array([len(pts2d)], dtype=np.uint32)

    try:
        tri_idx = earcut.triangulate_float64(pts2d, ring_end_indices)
    except Exception as e:
        print("earcut triangulation 실패:", e)
        return None, None

    tri_idx = np.asarray(tri_idx, dtype=np.int64)
    if len(tri_idx) == 0:
        return None, None

    faces = tri_idx.reshape(-1, 3)

    z_val = float(np.mean(loop_points_3d[:, 2]))
    verts3d = np.column_stack([
        pts2d[:, 0],
        pts2d[:, 1],
        np.full(len(pts2d), z_val, dtype=np.float64)
    ])

    return verts3d, faces


def add_cap_for_plane(mesh, target_z, z_tol=1e-4, area_min_ratio=0.01):
    """
    boundary loop 중 평균 z가 target_z 근처인 루프만 찾아 cap 생성.
    area가 너무 작은 루프는 무시.
    """
    b_edges = boundary_edges(mesh)
    loops = edges_to_loops(b_edges)

    if len(loops) == 0:
        print(f"[z={target_z}] boundary loop를 찾지 못했습니다.")
        return mesh

    verts = mesh.vertices
    loop_infos = []

    for loop in loops:
        pts = verts[np.array(loop)]
        mean_z = np.mean(pts[:, 2])
        z_span = np.max(pts[:, 2]) - np.min(pts[:, 2])
        area_xy = abs(polygon_area_2d(pts[:, :2]))

        loop_infos.append({
            "loop": loop,
            "mean_z": mean_z,
            "z_span": z_span,
            "area_xy": area_xy
        })

    # target_z 근처 루프만 후보
    candidates = [x for x in loop_infos if abs(x["mean_z"] - target_z) <= z_tol]

    if len(candidates) == 0:
        print(f"[z={target_z}] target_z 근처 루프가 없습니다. z_tol을 늘려보세요.")
        # 디버깅용 출력
        for i, info in enumerate(sorted(loop_infos, key=lambda d: abs(d["mean_z"] - target_z))[:10]):
            print(f"  후보{i}: mean_z={info['mean_z']:.6f}, z_span={info['z_span']:.6f}, area={info['area_xy']:.6f}")
        return mesh

    # 너무 작은 조각 제외
    max_area = max(x["area_xy"] for x in candidates)
    candidates = [x for x in candidates if x["area_xy"] >= max_area * area_min_ratio]

    # 가장 큰 루프 선택
    chosen = max(candidates, key=lambda d: d["area_xy"])
    loop = chosen["loop"]
    loop_pts = verts[np.array(loop)]

    print(
        f"[z={target_z}] loop 선택: "
        f"points={len(loop)}, mean_z={chosen['mean_z']:.6f}, "
        f"z_span={chosen['z_span']:.6f}, area={chosen['area_xy']:.6f}"
    )

    cap_verts, cap_faces = triangulate_loop_xy(loop_pts)
    if cap_verts is None or cap_faces is None or len(cap_faces) == 0:
        print(f"[z={target_z}] 삼각분할 실패")
        return mesh

    old_v = mesh.vertices.copy()
    old_f = mesh.faces.copy()

    offset = len(old_v)
    new_vertices = np.vstack([old_v, cap_verts])
    new_faces = np.vstack([old_f, cap_faces + offset])

    capped = trimesh.Trimesh(vertices=new_vertices, faces=new_faces, process=False)
    capped = clean_mesh(capped)

    return capped


def make_watertight_voxel(
    mesh,
    pitch=0.002,
    max_iter=30,
    fallback_pitch_multipliers=(1.0, 1.5, 2.0, 3.0),
):
    print("Voxel 기반 watertight 생성 중...")

    # voxelization (속까지 채워짐)
    voxel = None
    last_error = None

    for multiplier in fallback_pitch_multipliers:
        current_pitch = pitch * multiplier
        try:
            print(
                f"  voxelize try: pitch={current_pitch:.6f}, "
                f"max_iter={max_iter}"
            )
            voxel = mesh.voxelized(
                current_pitch,
                method="subdivide",
                max_iter=max_iter,
            )
            break
        except ValueError as e:
            last_error = e
            print(f"  voxelize failed: {e}")

    if voxel is None:
        raise ValueError(
            "voxel watertight conversion failed. "
            "Try increasing watertight_pitch or voxel_max_iter."
        ) from last_error

    # 내부 채우기
    voxel = voxel.fill()

    # 다시 mesh로 변환. trimesh의 marching_cubes는 voxel index 좌표계로
    # mesh를 반환하므로, 원본 scene 좌표계를 보존하려면 voxel transform을
    # 반드시 적용해야 한다.
    watertight_mesh = voxel.marching_cubes
    watertight_mesh.apply_transform(voxel.transform)

    watertight_mesh.remove_unreferenced_vertices()
    watertight_mesh.merge_vertices()

    return watertight_mesh


def estimate_voxel_grid(mesh, pitch):
    extents = np.asarray(mesh.extents, dtype=np.float64)
    dims = np.floor(extents / pitch).astype(np.int64) + 1
    dims = np.maximum(dims, 1)
    voxel_count = int(np.prod(dims, dtype=np.int64))
    return dims, voxel_count


def choose_safe_watertight_pitch(mesh, requested_pitch, max_voxels, min_pitch):
    requested_pitch = max(float(requested_pitch), float(min_pitch))
    dims, voxel_count = estimate_voxel_grid(mesh, requested_pitch)

    if voxel_count <= max_voxels:
        return requested_pitch, dims, voxel_count, False

    extents = np.asarray(mesh.extents, dtype=np.float64)
    volume = float(np.prod(np.maximum(extents, requested_pitch)))
    safe_pitch = (volume / float(max_voxels)) ** (1.0 / 3.0)
    safe_pitch = max(safe_pitch, requested_pitch, float(min_pitch))

    safe_dims, safe_voxel_count = estimate_voxel_grid(mesh, safe_pitch)
    while safe_voxel_count > max_voxels:
        safe_pitch *= 1.05
        safe_dims, safe_voxel_count = estimate_voxel_grid(mesh, safe_pitch)

    return safe_pitch, safe_dims, safe_voxel_count, True


# ===== 추가: 단계별 저장/로그 유틸 =====

def mesh_summary(mesh):
    bounds = None if mesh.bounds is None else mesh.bounds.tolist()
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "bounds": bounds,
    }


def save_step(mesh, step_dir, step_no, name, ext="ply"):
    """
    각 단계 메시를 step_dir 아래에 저장한다.
    예: 03_z_min_slice.ply
    """
    os.makedirs(step_dir, exist_ok=True)
    filename = f"{step_no:02d}_{name}.{ext}"
    path = os.path.join(step_dir, filename)

    mesh.export(path)

    info = mesh_summary(mesh)
    print(
        f"[SAVE] {path} | "
        f"V={info['vertices']}, F={info['faces']}, "
        f"watertight={info['watertight']}, bounds={info['bounds']}"
    )

    return path


def save_boundary_loops(mesh, step_dir, step_no, name):
    """
    현재 메시의 boundary edge만 별도 PLY로 저장한다.
    cap이 붙기 전/후 열린 경계 확인용이다.
    """
    os.makedirs(step_dir, exist_ok=True)

    b_edges = boundary_edges(mesh)
    if len(b_edges) == 0:
        print(f"[SAVE] {step_no:02d}_{name}: boundary edge 없음")
        return None

    # Path3D로 저장하면 MeshLab/Blender에서 선 형태로 확인 가능
    path_obj = trimesh.load_path(mesh.vertices[b_edges])
    path = os.path.join(step_dir, f"{step_no:02d}_{name}_boundary_edges.ply")
    path_obj.export(path)

    loops = edges_to_loops(b_edges)
    print(f"[SAVE] {path} | boundary_edges={len(b_edges)}, loops={len(loops)}")

    return path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Postprocess one *_unprocessed.ply file from 2dgs_output."
    )

    parser.add_argument(
        "--input",
        dest="input_path",
        default=None,
        help="Input ply filename or path. Relative values are resolved from 2dgs_output.",
    )
    parser.add_argument("--z-min", type=float, default=0.0)
    parser.add_argument("--z-max", type=float, default=0.8)
    parser.add_argument("--z-tol", type=float, default=1e-3)
    parser.add_argument("--step-ext", default="ply")
    parser.set_defaults(save_steps=True)
    parser.add_argument(
        "--save-steps",
        dest="save_steps",
        action="store_true",
        help="Save intermediate meshes for each postprocessing step. Enabled by default.",
    )
    parser.add_argument(
        "--no-save-steps",
        dest="save_steps",
        action="store_false",
        help="Disable saving intermediate meshes.",
    )
    parser.add_argument("--save-boundaries", action="store_true", default=False)
    parser.add_argument("--watertight-pitch", type=float, default=0.002)
    parser.add_argument(
        "--watertight-mode",
        choices=("auto", "voxel", "skip"),
        default="auto",
        help="Watertight conversion mode. auto increases pitch when the voxel grid is too large.",
    )
    parser.add_argument(
        "--watertight-max-voxels",
        type=int,
        default=100_000_000,
        help="Maximum estimated voxel grid size used by --watertight-mode auto.",
    )
    parser.add_argument(
        "--watertight-min-pitch",
        type=float,
        default=0.002,
        help="Minimum pitch allowed by --watertight-mode auto.",
    )
    parser.add_argument("--voxel-max-iter", type=int, default=30)
    parser.add_argument(
        "--initial-component",
        choices=("auto", "skip", "largest"),
        default="largest",
        help=(
            "Initial connected-component filtering before z slicing. "
            "largest always runs it; auto skips it for very large meshes to avoid OOM."
        ),
    )
    parser.add_argument(
        "--initial-component-face-limit",
        type=int,
        default=1_000_000,
        help="Face-count limit used by --initial-component auto.",
    )
    parser.add_argument(
        "--component-distance-tolerance",
        type=float,
        default=0.05,
        help=(
            "Distance tolerance for Step 6 component tie-break. "
            "Candidates within this ratio of the closest component are tied by size."
        ),
    )

    return parser.parse_args()


def select_input_file(input_root):
    candidates = sorted(
        input_root.glob("*_unprocessed.ply"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if len(candidates) == 0:
        raise FileNotFoundError(f"No *_unprocessed.ply file found in {input_root}")

    selected = candidates[0]
    print("Auto-selected latest input:", selected)
    return selected


def resolve_input_path(input_arg, input_root):
    if input_arg is None:
        return select_input_file(input_root)

    path = Path(input_arg)
    if not path.is_absolute():
        if path.exists():
            path = path
        else:
            path = input_root / path

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    return path


def build_output_paths(input_path, output_root):
    stem = input_path.stem

    if stem.endswith("_unprocessed"):
        name = stem[: -len("_unprocessed")]
    else:
        name = stem

    output_path = output_root / f"{name}_postprocessed.stl"
    step_dir = output_root / f"{name}_postprocess_steps"

    return output_path, step_dir


def timestamp_for_path(path):
    return time.strftime("%Y%m%d_%H%M%S", time.localtime(path.stat().st_ctime))


def timestamped_sibling_path(path):
    timestamp = timestamp_for_path(path)

    if path.is_dir():
        candidate = path.with_name(f"{path.name}_{timestamp}")
    else:
        candidate = path.with_name(f"{path.stem}_{timestamp}{path.suffix}")

    counter = 1
    while candidate.exists():
        if path.is_dir():
            candidate = path.with_name(f"{path.name}_{timestamp}_{counter}")
        else:
            candidate = path.with_name(f"{path.stem}_{timestamp}_{counter}{path.suffix}")
        counter += 1

    return candidate


def archive_existing_path(path):
    if not path.exists():
        return None

    archived_path = timestamped_sibling_path(path)
    shutil.move(str(path), str(archived_path))
    print("Archived existing path:", path, "->", archived_path)
    return archived_path


def archive_existing_outputs(output_path, step_dir):
    archive_existing_path(output_path)
    archive_existing_path(step_dir)


def backup_processed_input(input_path, backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / input_path.name
    archive_existing_path(backup_path)
    shutil.move(str(input_path), str(backup_path))
    print("Processed input moved to backup:", backup_path)
    return backup_path


def process_foot_with_manual_caps(
    input_path,
    output_path,
    z_min=0.0,
    z_max=0.8,
    z_tol=1e-3,
    step_dir=None,
    step_ext="ply",
    save_steps=False,
    save_boundaries=False,
    watertight_pitch=0.002,
    watertight_mode="auto",
    watertight_max_voxels=100_000_000,
    watertight_min_pitch=0.002,
    component_origin=(0.0, 0.0, 0.0),
    component_min_vertex_ratio=0.10,
    component_distance_tolerance=0.05,
    initial_component_mode="auto",
    initial_component_face_limit=1_000_000,
    voxel_max_iter=30,
    voxel_fallback_pitch_multipliers=(1.0, 1.5, 2.0, 3.0),
):
    if step_dir is None:
        base = os.path.splitext(os.path.basename(output_path))[0]
        step_dir = base + "_steps"

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print("1. 메시 로드")
    mesh = trimesh.load(input_path, force='mesh', process=False)

    if isinstance(mesh, trimesh.Scene):
        if len(mesh.geometry) == 0:
            raise ValueError("비어 있는 Scene입니다.")
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    if mesh.is_empty:
        raise ValueError("메시가 비어 있습니다.")

    if save_steps:
        save_step(mesh, step_dir, 1, "loaded_raw", ext=step_ext)

    print("2. 기본 clean")
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 2, "cleaned_initial", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 2, "cleaned_initial")

    print("3. 초기 연결 성분 정리")
    should_keep_initial_component = (
        initial_component_mode == "largest"
        or (
            initial_component_mode == "auto"
            and len(mesh.faces) <= initial_component_face_limit
        )
    )

    if should_keep_initial_component:
        print(
            "   largest component 실행: "
            f"faces={len(mesh.faces)}, limit={initial_component_face_limit}"
        )
        mesh = keep_largest_component(mesh)
        mesh = clean_mesh(mesh)
    else:
        print(
            "   skipped: 큰 mesh에서 초기 component split은 메모리를 많이 사용합니다. "
            f"faces={len(mesh.faces)}, limit={initial_component_face_limit}, "
            f"mode={initial_component_mode}"
        )
    if save_steps:
        save_step(mesh, step_dir, 3, "initial_component", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 3, "initial_component")

    print("4. z_min으로 절단")
    mesh = safe_slice(mesh, [0, 0, 1], [0, 0, z_min])
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 4, "z_min_slice", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 4, "z_min_slice")

    print("5. z_max로 절단")
    mesh = safe_slice(mesh, [0, 0, -1], [0, 0, z_max])
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 5, "z_max_slice", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 5, "z_max_slice")

    print("6. 절단 후 가장 큰 연결 성분만 유지")
    mesh = keep_origin_scored_component(
        mesh,
        origin=component_origin,
        min_vertex_ratio=component_min_vertex_ratio,
        distance_tolerance=component_distance_tolerance,
    )
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 6, "scored_component_after_slices", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 6, "scored_component_after_slices")

    print("7. 아래 면 cap 추가")
    mesh = add_cap_for_plane(mesh, z_min, z_tol=z_tol)
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 7, "bottom_cap_added", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 7, "bottom_cap_added")

    print("8. 위 면 cap 추가")
    mesh = add_cap_for_plane(mesh, z_max, z_tol=z_tol)
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 8, "top_cap_added", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 8, "top_cap_added")

    print("9. cap 이후 최종 clean")
    mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 9, "manual_caps_cleaned", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 9, "manual_caps_cleaned")

    print("10. voxel watertight 변환")
    if watertight_mode == "skip":
        print("   skipped: --watertight-mode skip")
    else:
        final_pitch = watertight_pitch
        dims, voxel_count = estimate_voxel_grid(mesh, final_pitch)
        print(
            "   requested voxel grid: "
            f"pitch={final_pitch:.6f}, dims={dims.tolist()}, voxels={voxel_count}"
        )

        if watertight_mode == "auto":
            final_pitch, dims, voxel_count, adjusted = choose_safe_watertight_pitch(
                mesh,
                requested_pitch=watertight_pitch,
                max_voxels=watertight_max_voxels,
                min_pitch=watertight_min_pitch,
            )
            if adjusted:
                print(
                    "   auto pitch adjusted: "
                    f"pitch={final_pitch:.6f}, dims={dims.tolist()}, "
                    f"voxels={voxel_count}, limit={watertight_max_voxels}"
                )
            else:
                print(
                    "   auto pitch kept: "
                    f"pitch={final_pitch:.6f}, dims={dims.tolist()}, "
                    f"voxels={voxel_count}, limit={watertight_max_voxels}"
                )

        mesh = make_watertight_voxel(
            mesh,
            pitch=final_pitch,
            max_iter=voxel_max_iter,
            fallback_pitch_multipliers=voxel_fallback_pitch_multipliers,
        )
        mesh = clean_mesh(mesh)
    if save_steps:
        save_step(mesh, step_dir, 10, "voxel_watertight", ext=step_ext)
    if save_boundaries:
        save_boundary_loops(mesh, step_dir, 10, "voxel_watertight")

    print("11. 최종 상태")
    print("vertices:", len(mesh.vertices))
    print("faces:", len(mesh.faces))
    print("watertight:", mesh.is_watertight)
    print("bounds:", mesh.bounds)

    mesh.export(output_path)
    print("최종 저장 완료:", output_path)
    print("단계별 저장 폴더:", step_dir)

    return mesh


if __name__ == "__main__":
    start_time = time.perf_counter()

    args = parse_args()

    input_root = Path("2dgs_output")
    output_root = Path("2dgs_post_output") / "postprocessed"
    backup_dir = input_root / "unprocess_backup"

    input_path = resolve_input_path(args.input_path, input_root)
    output_path, step_dir = build_output_paths(input_path, output_root)

    print("Input:", input_path)
    print("Output:", output_path)
    print("Step dir:", step_dir)
    print("Save steps:", args.save_steps)
    print("Save boundaries:", args.save_boundaries)

    archive_existing_outputs(output_path, step_dir)

    process_foot_with_manual_caps(
        input_path=str(input_path),
        output_path=str(output_path),
        z_min=args.z_min,
        z_max=args.z_max,
        z_tol=args.z_tol,
        step_dir=str(step_dir),
        step_ext=args.step_ext,
        save_steps=args.save_steps,
        save_boundaries=args.save_boundaries,
        watertight_pitch=args.watertight_pitch,
        watertight_mode=args.watertight_mode,
        watertight_max_voxels=args.watertight_max_voxels,
        watertight_min_pitch=args.watertight_min_pitch,
        component_distance_tolerance=args.component_distance_tolerance,
        initial_component_mode=args.initial_component,
        initial_component_face_limit=args.initial_component_face_limit,
        voxel_max_iter=args.voxel_max_iter,
        voxel_fallback_pitch_multipliers=(1.0, 1.5, 2.0, 3.0),
    )

    backup_processed_input(input_path, backup_dir)

    end_time = time.perf_counter()
    execution_time = end_time - start_time

    print(f"전체 실행 시간: {execution_time:.6f}초")
