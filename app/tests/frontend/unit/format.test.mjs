// Unit tests for the console's pure formatting helpers.
// Run with pytest, or directly: node --test app/tests/frontend/unit/format.test.mjs
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { format } from "../../../static/js/format.js";

const patient = { first_name: "Miguel", last_name: "O'Connor-Reyes" };
const minutesAgo = (minutes) => new Date(Date.now() - minutes * 60000).toISOString();

describe("names", () => {
  it("joins first and last name", () => assert.equal(format.fullName(patient), "Miguel O'Connor-Reyes"));
  it("builds upper-case initials", () => assert.equal(format.initials({ first_name: "jane", last_name: "doe" }), "JD"));
});

describe("phone", () => {
  it("formats ten digits", () => assert.equal(format.phone("5125550101"), "(512) 555-0101"));
  it("leaves other values as they are", () => assert.equal(format.phone("+15125550101"), "+15125550101"));
  it("returns an empty string for a missing number", () => {
    assert.equal(format.phone(null), "");
    assert.equal(format.phone(undefined), "");
  });
});

describe("percent and count", () => {
  it("rounds to a whole percentage", () => assert.equal(format.percent(2, 6), "33%"));
  it("does not divide by zero", () => assert.equal(format.percent(0, 0), "0%"));
  it("uses the singular for one", () => assert.equal(format.count(1, "patient"), "1 patient"));
  it("adds an s for the plural", () => assert.equal(format.count(3, "patient"), "3 patients"));
  it("accepts an irregular plural", () => assert.equal(format.count(2, "person", "people"), "2 people"));
});

describe("age", () => {
  const birthday = (yearsAgo, dayOffset) => {
    const date = new Date();
    date.setFullYear(date.getFullYear() - yearsAgo);
    date.setDate(date.getDate() + dayOffset);
    const pad = (number) => String(number).padStart(2, "0");
    return `${pad(date.getMonth() + 1)}/${pad(date.getDate())}/${date.getFullYear()}`;
  };
  it("counts a birthday that falls today", () => assert.equal(format.age(birthday(30, 0)), "30 years old"));
  it("does not count a birthday that is tomorrow", () => assert.equal(format.age(birthday(30, 1)), "29 years old"));
  it("describes an infant", () => assert.equal(format.age(birthday(0, -10)), "Under 1 year old"));
});

describe("ago", () => {
  it("says just now under a minute", () => assert.equal(format.ago(minutesAgo(0)), "Just now"));
  it("uses minutes under an hour", () => assert.equal(format.ago(minutesAgo(5)), "5 min ago"));
  it("uses the singular hour", () => assert.equal(format.ago(minutesAgo(60)), "1 hour ago"));
  it("uses hours under a day", () => assert.equal(format.ago(minutesAgo(180)), "3 hours ago"));
  it("uses days after that", () => assert.equal(format.ago(minutesAgo(3 * 24 * 60)), "3 days ago"));
  it("never reports a negative time for a clock that is slightly ahead", () => assert.equal(format.ago(minutesAgo(-2)), "Just now"));
});

describe("dates", () => {
  it("leaves the year out for the current year", () => {
    assert.ok(!format.date(new Date().toISOString()).includes(String(new Date().getFullYear())));
  });
  it("includes the year for earlier years", () => assert.ok(format.date("2001-06-15T12:00:00Z").includes("2001")));
});

describe("endReason", () => {
  it("names the reasons Vapi reports most", () => {
    assert.equal(format.endReason("assistant-said-end-call-phrase"), "Agent ended the call");
    assert.equal(format.endReason("customer-ended-call"), "Caller hung up");
  });
  it("makes an unknown reason readable", () => assert.equal(format.endReason("pipeline-error.openai"), "pipeline error openai"));
  it("handles a missing reason", () => assert.equal(format.endReason(null), "Not reported"));
});

describe("turns", () => {
  it("splits a transcript into agent and caller turns", () => {
    assert.deepEqual(format.turns("AI: Hi there.\nUser: Hello.\nAI: Your name?"), [
      { agent: true, text: "Hi there." }, { agent: false, text: "Hello." }, { agent: true, text: "Your name?" },
    ]);
  });
  it("joins a wrapped line onto the turn before it", () => {
    assert.deepEqual(format.turns("User: My name is\nJane Doe"), [{ agent: false, text: "My name is Jane Doe" }]);
  });
  it("returns nothing for an empty or missing transcript", () => {
    assert.deepEqual(format.turns(""), []);
    assert.deepEqual(format.turns(null), []);
  });
  it("keeps markup in a transcript as plain text", () => {
    assert.equal(format.turns("User: <script>alert(1)</script>")[0].text, "<script>alert(1)</script>");
  });
});
