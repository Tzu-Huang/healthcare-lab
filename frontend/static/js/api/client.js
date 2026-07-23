async function responsePayload(response) {
  return response.json().catch(() => ({}));
}

function errorFrom(response, payload) {
  const detail = payload.error;
  const message = typeof detail === "object"
    ? detail.message || detail.code
    : detail;
  const error = new Error(message || response.statusText || "Request failed");
  error.status = response.status;
  error.payload = payload;
  return error;
}

export async function requestJsonEnvelope(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await responsePayload(response);
  return { response, payload };
}

export async function requestJson(url, options = {}) {
  const { response, payload } = await requestJsonEnvelope(url, options);
  if (!response.ok || payload.success === false) {
    throw errorFrom(response, payload);
  }
  return payload;
}

export async function requestJsonAllowBusinessFailure(url, options = {}) {
  const { response, payload } = await requestJsonEnvelope(url, options);
  if (!response.ok) {
    throw errorFrom(response, payload);
  }
  return payload;
}
