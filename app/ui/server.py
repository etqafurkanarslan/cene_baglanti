"""FastAPI server for the local human-in-the-loop review UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import DEFAULT_OUTPUT_ROOT, PROJECT_ROOT
from app.geometry.mount_assets import build_placeholder_mount_local
from app.geometry.saddle import SaddleConfig
from app.ui.regeneration import regenerate_case
from app.ui.schemas import (
    CaseDetailModel,
    CaseSummaryModel,
    PlacementModel,
    PlacementPayload,
    RegenerateResponseModel,
    SavedSelectionModel,
    SelectionPayload,
    UIReviewModel,
    UIReviewPayload,
)
from app.ui.selection_store import (
    build_selection_from_faces,
    load_placement,
    load_selection,
    load_ui_review,
    save_placement,
    save_selection,
    save_ui_review,
)
from app.ui.services import build_case_detail, get_case, list_case_summaries, resolve_artifact_path

WEBUI_ROOT = PROJECT_ROOT / "webui"


def create_app(output_root: Path = DEFAULT_OUTPUT_ROOT) -> FastAPI:
    """Create the local review UI server."""

    app = FastAPI(title="cene_baglanti review UI")
    app.state.output_root = output_root

    @app.get("/api/cases", response_model=list[CaseSummaryModel])
    def list_cases() -> list[CaseSummaryModel]:
        return list_case_summaries(app.state.output_root)

    @app.get("/api/cases/{case_id}", response_model=CaseDetailModel)
    def get_case_detail(case_id: str) -> CaseDetailModel:
        try:
            case = get_case(case_id, app.state.output_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return build_case_detail(case)

    @app.get("/api/cases/{case_id}/mesh")
    def get_case_mesh(case_id: str) -> FileResponse:
        try:
            case = get_case(case_id, app.state.output_root)
            mesh_path = resolve_artifact_path(case, "aligned_mesh.stl")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(mesh_path, media_type="model/stl", filename=mesh_path.name)

    @app.get("/api/cases/{case_id}/mount-asset-mesh")
    def get_case_mount_asset_mesh(case_id: str) -> FileResponse:
        try:
            case = get_case(case_id, app.state.output_root)
            detail = build_case_detail(case)
            mount_asset = detail.result.get("mount_asset", {})
            if mount_asset.get("type") == "real":
                mesh_path = Path(mount_asset["source"])
            else:
                mesh_path = case.output_dir / "_ui_placeholder_mount.stl"
                if not mesh_path.exists():
                    config = SaddleConfig(
                        footprint_width_mm=float(detail.result["saddle"]["footprint_width_mm"]),
                        footprint_height_mm=float(detail.result["saddle"]["footprint_height_mm"]),
                        wall_thickness_mm=3.0,
                    )
                    build_placeholder_mount_local(config).export(mesh_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(mesh_path, media_type="model/stl", filename=mesh_path.name)

    @app.get("/api/cases/{case_id}/artifacts/{artifact_name}")
    def get_case_artifact(case_id: str, artifact_name: str) -> FileResponse:
        try:
            case = get_case(case_id, app.state.output_root)
            artifact_path = resolve_artifact_path(case, artifact_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(artifact_path, filename=artifact_path.name)

    @app.post("/api/cases/{case_id}/selection", response_model=SavedSelectionModel)
    def save_case_selection(case_id: str, payload: SelectionPayload) -> SavedSelectionModel:
        try:
            case = get_case(case_id, app.state.output_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        selection = build_selection_from_faces(
            case.output_dir,
            payload.included_face_ids,
            payload.excluded_face_ids,
        )
        save_selection(case.output_dir, selection)
        return selection

    @app.post("/api/cases/{case_id}/review", response_model=UIReviewModel)
    def save_case_review(case_id: str, payload: UIReviewPayload) -> UIReviewModel:
        try:
            case = get_case(case_id, app.state.output_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        save_ui_review(case.output_dir, payload)
        stored = load_ui_review(case.output_dir)
        if stored is None:
            raise HTTPException(status_code=500, detail="Failed to persist UI review.")
        return stored

    @app.post("/api/cases/{case_id}/placement", response_model=PlacementModel)
    def save_case_placement(case_id: str, payload: PlacementPayload) -> PlacementModel:
        try:
            case = get_case(case_id, app.state.output_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        save_placement(case.output_dir, payload)
        stored = load_placement(case.output_dir)
        if stored is None:
            raise HTTPException(status_code=500, detail="Failed to persist placement.")
        return stored

    @app.post("/api/cases/{case_id}/regenerate", response_model=RegenerateResponseModel)
    def regenerate_case_endpoint(case_id: str) -> RegenerateResponseModel:
        try:
            case = get_case(case_id, app.state.output_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return regenerate_case(case)

    app.mount("/", StaticFiles(directory=WEBUI_ROOT, html=True), name="webui")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.ui.server:app", host="127.0.0.1", port=8000, reload=False)
