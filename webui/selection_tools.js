export class SelectionState {
  constructor() {
    this.includedFaceIds = new Set();
    this.excludedFaceIds = new Set();
    this.manualCenter = null;
  }

  clear() {
    this.includedFaceIds.clear();
    this.excludedFaceIds.clear();
    this.manualCenter = null;
  }

  applyFace(faceId, mode) {
    if (mode === "include") {
      this.excludedFaceIds.delete(faceId);
      this.includedFaceIds.add(faceId);
      return;
    }
    if (mode === "exclude") {
      this.includedFaceIds.delete(faceId);
      this.excludedFaceIds.add(faceId);
    }
  }

  setManualCenter(point) {
    this.manualCenter = point ? [...point] : null;
  }

  toPayload() {
    return {
      included_face_ids: [...this.includedFaceIds].sort((a, b) => a - b),
      excluded_face_ids: [...this.excludedFaceIds].sort((a, b) => a - b),
    };
  }
}

