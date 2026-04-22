import { fetchCase, fetchCases, regenerate, savePlacement, saveReview, saveSelection } from "./api.js";
import { MeshViewer } from "./mesh_viewer.js";
import { SelectionState } from "./selection_tools.js";

const state = {
  currentCase: null,
  currentCaseDetail: null,
  selection: new SelectionState(),
  placement: null,
};

const elements = {
  caseList: document.getElementById("caseList"),
  caseSummary: document.getElementById("caseSummary"),
  selectionSummary: document.getElementById("selectionSummary"),
  compareSummary: document.getElementById("compareSummary"),
  selectionMode: document.getElementById("selectionMode"),
  wireframeToggle: document.getElementById("wireframeToggle"),
  approved: document.getElementById("approved"),
  centerX: document.getElementById("centerX"),
  centerY: document.getElementById("centerY"),
  centerZ: document.getElementById("centerZ"),
  yawDeg: document.getElementById("yawDeg"),
  pitchDeg: document.getElementById("pitchDeg"),
  rollDeg: document.getElementById("rollDeg"),
  mountOffset: document.getElementById("mountOffset"),
  footprintMargin: document.getElementById("footprintMargin"),
  wallThickness: document.getElementById("wallThickness"),
  patchRadius: document.getElementById("patchRadius"),
  contactOffset: document.getElementById("contactOffset"),
  footprintWidth: document.getElementById("footprintWidth"),
  footprintHeight: document.getElementById("footprintHeight"),
  saddleHeight: document.getElementById("saddleHeight"),
  reviewNotes: document.getElementById("reviewNotes"),
};

const viewer = new MeshViewer(document.getElementById("viewer"));

document.getElementById("refreshCases").addEventListener("click", loadCases);
document.getElementById("wireframeToggle").addEventListener("change", (event) => {
  viewer.setWireframe(event.target.checked);
});
document.getElementById("clearSelection").addEventListener("click", () => {
  state.selection.clear();
  viewer.setSelection(state.selection);
  updateSelectionSummary();
});
document.getElementById("centerFromSelection").addEventListener("click", async () => {
  if (!state.currentCase) {
    return;
  }
  const saved = await saveSelection(state.currentCase.case_id, state.selection.toPayload());
  if (saved.selection_centroid) {
    setPlacementCenter(saved.selection_centroid);
    updateSelectionSummary(saved);
  }
});
document.getElementById("saveSelection").addEventListener("click", handleSaveSelection);
document.getElementById("savePlacement").addEventListener("click", handleSavePlacement);
document.getElementById("saveReview").addEventListener("click", handleSaveReview);
document.getElementById("regenerate").addEventListener("click", handleRegenerate);

for (const element of [
  elements.centerX,
  elements.centerY,
  elements.centerZ,
  elements.yawDeg,
  elements.pitchDeg,
  elements.rollDeg,
  elements.mountOffset,
  elements.footprintMargin,
]) {
  element.addEventListener("input", () => {
    if (!state.currentCaseDetail) {
      return;
    }
    state.placement = readPlacementForm();
    viewer.updatePlacementPreview(state.placement, state.currentCaseDetail.result);
    updateSelectionSummary();
  });
}

viewer.renderer.domElement.addEventListener("click", (event) => {
  if (!state.currentCaseDetail) {
    return;
  }
  const hit = viewer.pick(event);
  if (!hit) {
    return;
  }
  const mode = elements.selectionMode.value;
  if (mode === "place-adapter") {
    setPlacementCenter(hit.point);
    return;
  }
  state.selection.applyFace(hit.faceId, mode);
  viewer.setSelection(state.selection);
  updateSelectionSummary();
});

loadCases();

async function loadCases() {
  const cases = await fetchCases();
  renderCaseList(cases);
  if (!state.currentCase && cases.length) {
    await loadCase(cases[0].case_id);
  }
}

async function loadCase(caseId) {
  state.currentCaseDetail = await fetchCase(caseId);
  state.currentCase = state.currentCaseDetail;
  state.selection.clear();
  if (state.currentCaseDetail.selection) {
    state.currentCaseDetail.selection.included_face_ids?.forEach((id) => state.selection.includedFaceIds.add(id));
    state.currentCaseDetail.selection.excluded_face_ids?.forEach((id) => state.selection.excludedFaceIds.add(id));
  }
  state.placement = derivePlacement(state.currentCaseDetail);
  renderCaseList(await fetchCases());
  await viewer.loadCase(state.currentCaseDetail, state.placement);
  viewer.setSelection(state.selection);
  updateCaseSummary();
  updateSelectionSummary(state.currentCaseDetail.selection);
  populateForms();
}

function renderCaseList(cases) {
  elements.caseList.innerHTML = "";
  for (const item of cases) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `case-item${state.currentCase?.case_id === item.case_id ? " active" : ""}`;
    button.textContent = `${item.case_id}\n${item.scan_name}\n${item.updated_at}`;
    button.addEventListener("click", () => loadCase(item.case_id));
    elements.caseList.appendChild(button);
  }
}

function updateCaseSummary() {
  const result = state.currentCaseDetail.result;
  elements.caseSummary.textContent = JSON.stringify({
    case_id: state.currentCaseDetail.case_id,
    scan: result.scan.path,
    output_dir: state.currentCaseDetail.output_dir,
    current_mount_frame: result.mount_frame,
    placement: state.placement,
    diagnostics: result.diagnostics,
  }, null, 2);
}

function updateSelectionSummary(savedSelection = null) {
  const payload = savedSelection || {
    included_face_ids: [...state.selection.includedFaceIds],
    excluded_face_ids: [...state.selection.excludedFaceIds],
  };
  elements.selectionSummary.textContent = JSON.stringify({
    interaction: elements.selectionMode.value,
    placement: state.placement,
    included_face_count: payload.included_face_ids?.length ?? state.selection.includedFaceIds.size,
    excluded_face_count: payload.excluded_face_ids?.length ?? state.selection.excludedFaceIds.size,
  }, null, 2);
}

function populateForms() {
  const review = state.currentCaseDetail?.ui_review || {};
  elements.approved.checked = Boolean(review.approved);
  elements.patchRadius.value = review.patch_radius_mm ?? "";
  elements.contactOffset.value = review.contact_offset_mm ?? "";
  elements.footprintWidth.value = review.footprint_width_mm ?? "";
  elements.footprintHeight.value = review.footprint_height_mm ?? "";
  elements.saddleHeight.value = review.saddle_height_mm ?? "";
  elements.reviewNotes.value = review.notes ?? "";

  elements.centerX.value = state.placement.mount_center[0] ?? "";
  elements.centerY.value = state.placement.mount_center[1] ?? "";
  elements.centerZ.value = state.placement.mount_center[2] ?? "";
  elements.pitchDeg.value = state.placement.mount_rotation_euler_deg[0] ?? 0;
  elements.rollDeg.value = state.placement.mount_rotation_euler_deg[1] ?? 0;
  elements.yawDeg.value = state.placement.mount_rotation_euler_deg[2] ?? 0;
  elements.mountOffset.value = state.placement.mount_offset_mm ?? 0;
  elements.footprintMargin.value = state.placement.footprint_margin_mm ?? 2;
  elements.wallThickness.value = state.placement.wall_thickness_mm ?? "";
}

async function handleSaveSelection() {
  if (!state.currentCase) {
    return;
  }
  const saved = await saveSelection(state.currentCase.case_id, state.selection.toPayload());
  updateSelectionSummary(saved);
}

async function handleSavePlacement() {
  if (!state.currentCase) {
    return;
  }
  state.placement = readPlacementForm();
  const payload = {
    case_id: state.currentCase.case_id,
    mount_asset_path: state.currentCaseDetail.result.mount_asset?.source ?? null,
    ...state.placement,
    notes: elements.reviewNotes.value,
  };
  const saved = await savePlacement(state.currentCase.case_id, payload);
  state.currentCaseDetail.placement = saved;
  viewer.updatePlacementPreview(state.placement, state.currentCaseDetail.result);
  updateSelectionSummary();
}

async function handleSaveReview() {
  if (!state.currentCase) {
    return;
  }
  const payload = {
    approved: elements.approved.checked,
    mount_center_override: null,
    selection_file: state.selection.includedFaceIds.size ? "surface_selection.json" : null,
    patch_radius_mm: readNumber(elements.patchRadius.value),
    contact_offset_mm: readNumber(elements.contactOffset.value),
    footprint_width_mm: readNumber(elements.footprintWidth.value),
    footprint_height_mm: readNumber(elements.footprintHeight.value),
    saddle_height_mm: readNumber(elements.saddleHeight.value),
    notes: elements.reviewNotes.value,
  };
  const saved = await saveReview(state.currentCase.case_id, payload);
  state.currentCaseDetail.ui_review = saved;
}

async function handleRegenerate() {
  if (!state.currentCase) {
    return;
  }
  await handleSaveSelection();
  await handleSavePlacement();
  await handleSaveReview();
  const response = await regenerate(state.currentCase.case_id);
  elements.compareSummary.textContent = JSON.stringify(response, null, 2);
  await loadCase(response.new_case_id);
}

function derivePlacement(caseDetail) {
  const placement = caseDetail.placement;
  if (placement) {
    return {
      mount_center: [...placement.mount_center],
      mount_rotation_euler_deg: [...placement.mount_rotation_euler_deg],
      mount_offset_mm: placement.mount_offset_mm,
      projection_direction_mode: placement.projection_direction_mode,
      footprint_margin_mm: placement.footprint_margin_mm,
      contact_offset_mm: placement.contact_offset_mm,
      wall_thickness_mm: placement.wall_thickness_mm,
    };
  }
  return {
    mount_center: [...caseDetail.result.mount_frame.origin],
    mount_rotation_euler_deg: [0, 0, 0],
    mount_offset_mm: 0,
    projection_direction_mode: "frame-z-negative",
    footprint_margin_mm: 2,
    contact_offset_mm: caseDetail.result.saddle.contact_offset_mm,
    wall_thickness_mm: 3,
  };
}

function setPlacementCenter(point) {
  state.placement.mount_center = [...point];
  elements.centerX.value = point[0];
  elements.centerY.value = point[1];
  elements.centerZ.value = point[2];
  viewer.updatePlacementPreview(state.placement, state.currentCaseDetail.result);
  updateSelectionSummary();
}

function readPlacementForm() {
  return {
    mount_center: [
      readNumber(elements.centerX.value) ?? state.placement?.mount_center?.[0] ?? 0,
      readNumber(elements.centerY.value) ?? state.placement?.mount_center?.[1] ?? 0,
      readNumber(elements.centerZ.value) ?? state.placement?.mount_center?.[2] ?? 0,
    ],
    mount_rotation_euler_deg: [
      readNumber(elements.pitchDeg.value) ?? 0,
      readNumber(elements.rollDeg.value) ?? 0,
      readNumber(elements.yawDeg.value) ?? 0,
    ],
    mount_offset_mm: readNumber(elements.mountOffset.value) ?? 0,
    projection_direction_mode: "frame-z-negative",
    footprint_margin_mm: readNumber(elements.footprintMargin.value) ?? 2,
    contact_offset_mm: readNumber(elements.contactOffset.value),
    wall_thickness_mm: readNumber(elements.wallThickness.value),
  };
}

function readNumber(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

