import { fetchCase, fetchCases, regenerate, saveReview, saveSelection } from "./api.js";
import { MeshViewer } from "./mesh_viewer.js";
import { SelectionState } from "./selection_tools.js";

const state = {
  currentCase: null,
  currentCaseDetail: null,
  selection: new SelectionState(),
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
  populateReviewForm();
});
document.getElementById("centerFromSelection").addEventListener("click", async () => {
  if (!state.currentCase) {
    return;
  }
  const saved = await saveSelection(state.currentCase.case_id, state.selection.toPayload());
  if (saved.selection_centroid) {
    state.selection.setManualCenter(saved.selection_centroid);
    viewer.setSelection(state.selection);
    populateReviewForm();
    updateSelectionSummary(saved);
  }
});
document.getElementById("saveSelection").addEventListener("click", handleSaveSelection);
document.getElementById("saveReview").addEventListener("click", handleSaveReview);
document.getElementById("regenerate").addEventListener("click", handleRegenerate);

viewer.renderer.domElement.addEventListener("click", (event) => {
  if (!state.currentCaseDetail) {
    return;
  }
  const hit = viewer.pick(event);
  if (!hit) {
    return;
  }
  const mode = elements.selectionMode.value;
  if (mode === "move-center") {
    state.selection.setManualCenter(hit.point);
    populateReviewForm();
  } else {
    state.selection.applyFace(hit.faceId, mode);
  }
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
  if (state.currentCaseDetail.ui_review?.mount_center_override) {
    state.selection.setManualCenter(state.currentCaseDetail.ui_review.mount_center_override);
  }
  renderCaseList(await fetchCases());
  await viewer.loadCase(state.currentCaseDetail);
  viewer.setSelection(state.selection);
  updateCaseSummary();
  updateSelectionSummary(state.currentCaseDetail.selection);
  populateReviewForm();
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
    auto_center: result.mount_frame.origin,
    anchor: result.placement,
    diagnostics: result.diagnostics,
  }, null, 2);
}

function updateSelectionSummary(savedSelection = null) {
  const payload = savedSelection || {
    included_face_ids: [...state.selection.includedFaceIds],
    excluded_face_ids: [...state.selection.excludedFaceIds],
    selection_centroid: state.selection.manualCenter,
  };
  elements.selectionSummary.textContent = JSON.stringify({
    included_face_count: payload.included_face_ids?.length ?? state.selection.includedFaceIds.size,
    excluded_face_count: payload.excluded_face_ids?.length ?? state.selection.excludedFaceIds.size,
    selection_centroid: payload.selection_centroid ?? null,
    manual_center: state.selection.manualCenter,
  }, null, 2);
}

function populateReviewForm() {
  const review = state.currentCaseDetail?.ui_review || {};
  elements.approved.checked = Boolean(review.approved);
  const center = state.selection.manualCenter || review.mount_center_override || [];
  elements.centerX.value = center[0] ?? "";
  elements.centerY.value = center[1] ?? "";
  elements.centerZ.value = center[2] ?? "";
  elements.patchRadius.value = review.patch_radius_mm ?? "";
  elements.contactOffset.value = review.contact_offset_mm ?? "";
  elements.footprintWidth.value = review.footprint_width_mm ?? "";
  elements.footprintHeight.value = review.footprint_height_mm ?? "";
  elements.saddleHeight.value = review.saddle_height_mm ?? "";
  elements.reviewNotes.value = review.notes ?? "";
}

async function handleSaveSelection() {
  if (!state.currentCase) {
    return;
  }
  const saved = await saveSelection(state.currentCase.case_id, state.selection.toPayload());
  updateSelectionSummary(saved);
}

async function handleSaveReview() {
  if (!state.currentCase) {
    return;
  }
  const payload = {
    approved: elements.approved.checked,
    mount_center_override: readManualCenter(),
    selection_file: "surface_selection.json",
    patch_radius_mm: readNumber(elements.patchRadius.value),
    contact_offset_mm: readNumber(elements.contactOffset.value),
    footprint_width_mm: readNumber(elements.footprintWidth.value),
    footprint_height_mm: readNumber(elements.footprintHeight.value),
    saddle_height_mm: readNumber(elements.saddleHeight.value),
    notes: elements.reviewNotes.value,
  };
  const saved = await saveReview(state.currentCase.case_id, payload);
  state.currentCaseDetail.ui_review = saved;
  populateReviewForm();
}

async function handleRegenerate() {
  if (!state.currentCase) {
    return;
  }
  await handleSaveSelection();
  await handleSaveReview();
  const response = await regenerate(state.currentCase.case_id);
  elements.compareSummary.textContent = JSON.stringify(response, null, 2);
  await loadCase(response.new_case_id);
}

function readManualCenter() {
  const values = [elements.centerX.value, elements.centerY.value, elements.centerZ.value].map(readNumber);
  return values.every((value) => value !== null) ? values : null;
}

function readNumber(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

