async function responsePayload(response) {
  return response.json().catch(() => ({}));
}

function errorFrom(response, payload) {
  return new Error(payload.error || response.statusText || "Request failed");
}

export async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await responsePayload(response);
  if (!response.ok || payload.success === false) {
    throw errorFrom(response, payload);
  }
  return payload;
}

export async function requestJsonAllowBusinessFailure(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await responsePayload(response);
  if (!response.ok) {
    throw errorFrom(response, payload);
  }
  return payload;
}
