export async function fetchCases() {
  return fetchJson("/api/cases");
}

export async function fetchCase(caseId) {
  return fetchJson(`/api/cases/${encodeURIComponent(caseId)}`);
}

export async function saveSelection(caseId, payload) {
  return fetchJson(`/api/cases/${encodeURIComponent(caseId)}/selection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveReview(caseId, payload) {
  return fetchJson(`/api/cases/${encodeURIComponent(caseId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function savePlacement(caseId, payload) {
  return fetchJson(`/api/cases/${encodeURIComponent(caseId)}/placement`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function regenerate(caseId) {
  return fetchJson(`/api/cases/${encodeURIComponent(caseId)}/regenerate`, {
    method: "POST",
  });
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json();
}
