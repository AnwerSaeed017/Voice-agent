// Unit tests for the console's API client, with fetch replaced by a recorder.
import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";

import { api, ApiError } from "../../../static/js/api.js";

let requests;
let reply;
const realFetch = globalThis.fetch;

function respond(status, payload) {
  reply = { ok: status >= 200 && status < 300, status, json: async () => payload };
}

beforeEach(() => {
  requests = [];
  respond(200, { data: { ok: true }, error: null });
  globalThis.fetch = async (url, options) => {
    requests.push({ url, ...options });
    if (reply instanceof Error) throw reply;
    return reply;
  };
});
afterEach(() => { globalThis.fetch = realFetch; });

describe("requests", () => {
  it("returns the data from the envelope", async () => {
    respond(200, { data: { items: [1], total: 1 }, error: null });
    assert.deepEqual(await api.patients({}), { items: [1], total: 1 });
  });

  it("leaves out empty filters and encodes the rest", async () => {
    await api.patients({ q: "o'neil & co", source: "", sort: null, limit: 25, offset: 0 });
    assert.equal(requests[0].url, "/dashboard/patients?q=o%27neil+%26+co&limit=25&offset=0");
    assert.equal(requests[0].method, "GET");
  });

  it("sends the viewer's UTC offset with the summary request", async () => {
    await api.summary(14);
    const params = new URL(requests[0].url, "http://localhost").searchParams;
    assert.equal(params.get("days"), "14");
    assert.equal(Number(params.get("utc_offset_minutes")), -new Date().getTimezoneOffset());
  });

  it("sends changes as JSON on an update", async () => {
    await api.updatePatient("abc", { city: "Dallas", email: null });
    assert.equal(requests[0].url, "/patients/abc");
    assert.equal(requests[0].method, "PUT");
    assert.equal(requests[0].headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(requests[0].body), { city: "Dallas", email: null });
  });

  it("escapes an id that is not a plain UUID", async () => {
    await api.patient("../health?x=1");
    assert.equal(requests[0].url, "/patients/..%2Fhealth%3Fx%3D1");
  });

  it("uses DELETE to remove a patient", async () => {
    await api.deletePatient("abc");
    assert.equal(requests[0].method, "DELETE");
  });
});

describe("failures", () => {
  it("raises the server's message and field details", async () => {
    respond(422, { data: null, error: { code: "validation_error", message: "One or more fields are invalid.",
                                         details: [{ field: "phone_number", message: "Must be 10 digits" }] } });
    await assert.rejects(api.updatePatient("abc", { phone_number: "1" }), (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 422);
      assert.equal(error.message, "One or more fields are invalid.");
      assert.deepEqual(error.details, [{ field: "phone_number", message: "Must be 10 digits" }]);
      return true;
    });
  });

  it("reports a response that is not JSON", async () => {
    reply = { ok: false, status: 502, json: async () => { throw new Error("not json"); } };
    await assert.rejects(api.health(), (error) => error.status === 502 && error.message.includes("502"));
  });

  it("explains a network failure in plain words", async () => {
    reply = new TypeError("Failed to fetch");
    await assert.rejects(api.health(), (error) => error.status === 0 && error.message.includes("could not be reached"));
  });

  it("treats an error envelope as a failure even with a 200 status", async () => {
    respond(200, { data: null, error: { code: "x", message: "Nope." } });
    await assert.rejects(api.calls({}), (error) => error.message === "Nope." && error.details.length === 0);
  });
});
