"""Lightweight placement debug image export without external plotting deps."""

from pathlib import Path
import struct
import zlib

import numpy as np
import trimesh

from app.geometry.features import LocalPatch, MountFrame


def export_placement_debug_images(
    output_dir: Path,
    chin_region_points: np.ndarray,
    centerline_band_points: np.ndarray,
    frontier_band_points: np.ndarray,
    local_patch: LocalPatch,
    mount_frame: MountFrame,
    footprint_world: np.ndarray,
    legacy_center: np.ndarray,
    chin_anchor_point: np.ndarray,
    final_center: np.ndarray,
    asset_mesh: trimesh.Trimesh | None = None,
) -> tuple[Path, Path, Path]:
    """Export top and perspective PNG debug views."""

    top_path = output_dir / "placement_debug_top.png"
    perspective_path = output_dir / "placement_debug_perspective.png"
    anchor_path = output_dir / "placement_anchor_plot.png"

    top_scene = _collect_scene_points(
        chin_region_points,
        centerline_band_points,
        frontier_band_points,
        local_patch.points,
        footprint_world,
        asset_mesh,
    )
    perspective_scene = top_scene

    top_image = _render_projection(
        scene_points=top_scene,
        mount_frame=mount_frame,
        projection="top",
        footprint_world=footprint_world,
    )
    perspective_image = _render_projection(
        scene_points=perspective_scene,
        mount_frame=mount_frame,
        projection="perspective",
        footprint_world=footprint_world,
    )
    anchor_image = _render_projection(
        scene_points=top_scene,
        mount_frame=mount_frame,
        projection="top",
        footprint_world=footprint_world,
        legacy_center=legacy_center,
        chin_anchor_point=chin_anchor_point,
        final_center=final_center,
        show_centerline=True,
    )
    _write_png(top_path, top_image)
    _write_png(perspective_path, perspective_image)
    _write_png(anchor_path, anchor_image)
    return top_path, perspective_path, anchor_path


def _collect_scene_points(
    chin_region_points: np.ndarray,
    centerline_band_points: np.ndarray,
    frontier_band_points: np.ndarray,
    patch_points: np.ndarray,
    footprint_world: np.ndarray,
    asset_mesh: trimesh.Trimesh | None,
) -> dict[str, np.ndarray]:
    """Bundle point sets for rendering."""

    asset_points = np.asarray(asset_mesh.vertices, dtype=float) if asset_mesh is not None else np.empty((0, 3))
    return {
        "chin_region": _decimate(chin_region_points, 4000),
        "centerline_band": _decimate(centerline_band_points, 3000),
        "frontier_band": _decimate(frontier_band_points, 2000),
        "patch": _decimate(patch_points, 4000),
        "footprint": footprint_world,
        "asset": _decimate(asset_points, 2000),
    }


def _render_projection(
    scene_points: dict[str, np.ndarray],
    mount_frame: MountFrame,
    projection: str,
    footprint_world: np.ndarray,
    legacy_center: np.ndarray | None = None,
    chin_anchor_point: np.ndarray | None = None,
    final_center: np.ndarray | None = None,
    show_centerline: bool = False,
    width: int = 1400,
    height: int = 1000,
) -> np.ndarray:
    """Render a simple orthographic debug image."""

    canvas = np.full((height, width, 3), 250, dtype=np.uint8)
    points_all = [points for points in scene_points.values() if len(points)]
    points_all.append(np.asarray([mount_frame.origin]))
    stacked = np.vstack(points_all)

    if projection == "top":
        projected = stacked[:, [0, 1]]
        frame_axes = [
            (mount_frame.x_axis[[0, 1]], np.array([220, 60, 60], dtype=np.uint8)),
            (mount_frame.y_axis[[0, 1]], np.array([60, 180, 60], dtype=np.uint8)),
            (mount_frame.z_axis[[0, 1]], np.array([60, 90, 220], dtype=np.uint8)),
        ]
        project_fn = lambda arr: arr[:, [0, 1]]
    else:
        project_fn = _project_perspective
        projected = project_fn(stacked)
        frame_axes = [
            (_project_vector(mount_frame.x_axis), np.array([220, 60, 60], dtype=np.uint8)),
            (_project_vector(mount_frame.y_axis), np.array([60, 180, 60], dtype=np.uint8)),
            (_project_vector(mount_frame.z_axis), np.array([60, 90, 220], dtype=np.uint8)),
        ]

    scale, offset = _fit_projection(projected, width, height)

    for name, color in (
        ("chin_region", np.array([170, 170, 170], dtype=np.uint8)),
        ("centerline_band", np.array([220, 190, 80], dtype=np.uint8)),
        ("frontier_band", np.array([255, 120, 120], dtype=np.uint8)),
        ("patch", np.array([60, 150, 255], dtype=np.uint8)),
        ("asset", np.array([150, 80, 180], dtype=np.uint8)),
    ):
        if len(scene_points[name]):
            _draw_points(canvas, _to_pixels(project_fn(scene_points[name]), scale, offset, height), color, 1)

    footprint_pixels = _to_pixels(project_fn(footprint_world), scale, offset, height)
    _draw_polyline(canvas, footprint_pixels, np.array([30, 30, 30], dtype=np.uint8), closed=True)

    center_pixel = _to_pixels(project_fn(np.asarray([mount_frame.origin])), scale, offset, height)[0]
    _draw_disc(canvas, center_pixel, 6, np.array([255, 120, 0], dtype=np.uint8))
    for vector_2d, color in frame_axes:
        _draw_line(
            canvas,
            center_pixel,
            center_pixel + (vector_2d * 80.0).astype(int),
            color,
        )
    if show_centerline:
        x0 = _to_pixels(np.array([[0.0, projected[:, 1].min()]], dtype=float), scale, offset, height)[0]
        x1 = _to_pixels(np.array([[0.0, projected[:, 1].max()]], dtype=float), scale, offset, height)[0]
        _draw_line(canvas, x0, x1, np.array([90, 90, 90], dtype=np.uint8))
    _draw_marker(canvas, project_fn, scale, offset, height, legacy_center, np.array([220, 60, 60], dtype=np.uint8), 8)
    _draw_marker(canvas, project_fn, scale, offset, height, chin_anchor_point, np.array([255, 0, 200], dtype=np.uint8), 7)
    _draw_marker(canvas, project_fn, scale, offset, height, final_center, np.array([255, 120, 0], dtype=np.uint8), 6)

    return canvas


def _draw_marker(
    canvas: np.ndarray,
    project_fn,
    scale: float,
    offset: np.ndarray,
    height: int,
    point: np.ndarray | None,
    color: np.ndarray,
    radius: int,
) -> None:
    if point is None:
        return
    pixel = _to_pixels(project_fn(np.asarray([point], dtype=float)), scale, offset, height)[0]
    _draw_disc(canvas, pixel, radius, color)
    _draw_line(canvas, pixel + np.array([-radius - 2, 0]), pixel + np.array([radius + 2, 0]), color)
    _draw_line(canvas, pixel + np.array([0, -radius - 2]), pixel + np.array([0, radius + 2]), color)


def _project_perspective(points: np.ndarray) -> np.ndarray:
    """Project 3D points to a fixed pseudo-perspective plane."""

    matrix = np.array(
        [
            [0.9, -0.3, 0.0],
            [0.15, 0.35, -0.8],
        ],
        dtype=float,
    )
    return np.asarray(points, dtype=float) @ matrix.T


def _project_vector(vector: np.ndarray) -> np.ndarray:
    """Project one 3D vector into the pseudo-perspective plane."""

    return _project_perspective(np.asarray([vector], dtype=float))[0]


def _fit_projection(projected: np.ndarray, width: int, height: int) -> tuple[float, np.ndarray]:
    """Return scale and offset to fit projected points into image bounds."""

    mins = projected.min(axis=0)
    maxs = projected.max(axis=0)
    extents = np.maximum(maxs - mins, 1e-6)
    scale = 0.85 * min(width / extents[0], height / extents[1])
    offset = (np.array([width, height], dtype=float) - extents * scale) * 0.5 - mins * scale
    return scale, offset


def _to_pixels(projected: np.ndarray, scale: float, offset: np.ndarray, height: int) -> np.ndarray:
    pixels = projected * scale + offset
    pixels[:, 1] = height - pixels[:, 1]
    return np.round(pixels).astype(int)


def _draw_points(canvas: np.ndarray, pixels: np.ndarray, color: np.ndarray, radius: int) -> None:
    for pixel in pixels:
        _draw_disc(canvas, pixel, radius, color)


def _draw_polyline(canvas: np.ndarray, pixels: np.ndarray, color: np.ndarray, closed: bool) -> None:
    for index in range(len(pixels) - 1):
        _draw_line(canvas, pixels[index], pixels[index + 1], color)
    if closed and len(pixels) > 1:
        _draw_line(canvas, pixels[-1], pixels[0], color)


def _draw_line(canvas: np.ndarray, start: np.ndarray, end: np.ndarray, color: np.ndarray) -> None:
    points = max(abs(int(end[0] - start[0])), abs(int(end[1] - start[1])), 1)
    xs = np.linspace(start[0], end[0], points + 1).astype(int)
    ys = np.linspace(start[1], end[1], points + 1).astype(int)
    valid = (xs >= 0) & (xs < canvas.shape[1]) & (ys >= 0) & (ys < canvas.shape[0])
    canvas[ys[valid], xs[valid]] = color


def _draw_disc(canvas: np.ndarray, center: np.ndarray, radius: int, color: np.ndarray) -> None:
    x0, y0 = int(center[0]), int(center[1])
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            x = x0 + dx
            y = y0 + dy
            if 0 <= x < canvas.shape[1] and 0 <= y < canvas.shape[0]:
                canvas[y, x] = color


def _write_png(path: Path, image: np.ndarray) -> None:
    """Write a PNG image using only the standard library."""

    image_bytes = b"".join(b"\x00" + image[row].tobytes() for row in range(image.shape[0]))
    compressed = zlib.compress(image_bytes, level=9)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", image.shape[1], image.shape[0], 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _decimate(points: np.ndarray, limit: int) -> np.ndarray:
    if len(points) <= limit:
        return np.asarray(points, dtype=float)
    indices = np.linspace(0, len(points) - 1, limit, dtype=int)
    return np.asarray(points, dtype=float)[indices]
