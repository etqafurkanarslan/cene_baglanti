"""Tests for the local review UI API."""

import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import trimesh

from app.pipeline import process_scan
from app.ui.server import create_app


def test_ui_lists_and_loads_cases() -> None:
    """The UI API should list processed cases and load case detail."""

    output_root = _build_case_root("list_case")
    app = create_app(output_root=output_root)
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200

    cases = client.get("/api/cases")
    assert cases.status_code == 200
    payload = cases.json()
    assert len(payload) == 1

    case_id = payload[0]["case_id"]
    detail = client.get(f"/api/cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["case_id"] == case_id

    mesh = client.get(f"/api/cases/{case_id}/mesh")
    assert mesh.status_code == 200
    mount_asset = client.get(f"/api/cases/{case_id}/mount-asset-mesh")
    assert mount_asset.status_code == 200


def test_ui_selection_review_and_regenerate() -> None:
    """The UI API should persist placement/review and regenerate outputs."""

    output_root = _build_case_root("regenerate_case")
    app = create_app(output_root=output_root)
    client = TestClient(app)
    case_id = client.get("/api/cases").json()[0]["case_id"]

    placement_response = client.post(
        f"/api/cases/{case_id}/placement",
        json={
            "case_id": case_id,
            "mount_center": [0.0, 2.0, -1.0],
            "mount_rotation_euler_deg": [0.0, 0.0, 15.0],
            "mount_offset_mm": 1.5,
            "footprint_margin_mm": 3.0,
            "contact_offset_mm": 0.8,
            "wall_thickness_mm": 2.5,
            "notes": "ui placement",
        },
    )
    assert placement_response.status_code == 200
    assert placement_response.json()["mount_offset_mm"] == 1.5
    assert Path(output_root / case_id / "placement.json").exists()

    review_response = client.post(
        f"/api/cases/{case_id}/review",
        json={
            "approved": True,
            "patch_radius_mm": 5.0,
            "notes": "ui review",
        },
    )
    assert review_response.status_code == 200
    assert review_response.json()["approved"] is True
    assert Path(output_root / case_id / "ui_review.json").exists()

    regenerate_response = client.post(f"/api/cases/{case_id}/regenerate")
    assert regenerate_response.status_code == 200
    regenerate_payload = regenerate_response.json()
    assert regenerate_payload["previous_case_id"] == case_id
    assert Path(regenerate_payload["generated_files"]["result_json"]).exists()
    new_case_id = regenerate_payload["new_case_id"]
    new_result = json.loads((output_root / new_case_id / "result.json").read_text(encoding="utf-8"))
    assert new_result["mount_center_source"] == "ui_placement"
    assert new_result["mount_frame"]["source"] == "ui_placement"
    assert (output_root / new_case_id / "placement.json").exists()


def _build_case_root(name: str) -> Path:
    root = Path("outputs") / "test_ui" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    scan_path = root / "sample_box.stl"
    trimesh.creation.box(extents=(10.0, 8.0, 6.0)).export(scan_path)
    process_scan(
        scan_path=scan_path,
        mount_id="gopro_low_profile_v1",
        output_root=root,
    )
    return root
