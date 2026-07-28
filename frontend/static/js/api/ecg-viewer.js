function normalizeResultId(resultId) {
  const value = String(resultId ?? "");
  if (!/^[1-9]\d*$/.test(value)) {
    throw new Error("A valid ECG result ID is required.");
  }
  return value;
}

export function ecgMetadataUrl(resultId) {
  return `/api/dcm4chee/results/${normalizeResultId(resultId)}/ecg`;
}

export function ecgRenderSvgUrl(resultId) {
  return `/api/dcm4chee/results/${normalizeResultId(resultId)}/ecg/render.svg`;
}

export async function fetchEcgMetadata(resultId) {
  const response = await fetch(ecgMetadataUrl(resultId), {
    headers: { Accept: "application/json" },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    const error = new Error("ECG metadata request failed.");
    error.status = response.status;
    error.code = payload?.error?.code || "";
    throw error;
  }
  return payload.item;
}
