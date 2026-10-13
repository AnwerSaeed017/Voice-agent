// Thin client for the service's JSON API. Every response is { data, error }.

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.status = status;
    this.details = details || [];
  }
}

async function request(method, path, { params, body } = {}) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params || {})) {
    if (value !== null && value !== undefined && value !== "") query.set(name, value);
  }
  const url = query.size ? `${path}?${query}` : path;
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    throw new ApiError("The server could not be reached. Check your connection and try again.", 0);
  }
  let payload = null;
  try { payload = await response.json(); } catch (error) { /* not JSON */ }
  if (!response.ok || !payload || payload.error) {
    const failure = payload && payload.error;
    throw new ApiError(failure ? failure.message : `Request failed (${response.status}).`,
                       response.status, failure && failure.details);
  }
  return payload.data;
}

export const api = {
  health: () => request("GET", "/health"),
  summary: (days) => request("GET", "/dashboard/summary", {
    params: { days, utc_offset_minutes: -new Date().getTimezoneOffset() },
  }),
  patients: (params) => request("GET", "/dashboard/patients", { params }),
  calls: (params) => request("GET", "/dashboard/calls", { params }),
  patient: (id) => request("GET", `/patients/${encodeURIComponent(id)}`),
  patientCalls: (id) => request("GET", `/patients/${encodeURIComponent(id)}/calls`),
  updatePatient: (id, changes) => request("PUT", `/patients/${encodeURIComponent(id)}`, { body: changes }),
  deletePatient: (id) => request("DELETE", `/patients/${encodeURIComponent(id)}`),
};
