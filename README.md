# Patient Registration Voice Agent

A phone number you can call to register as a new patient. A voice agent collects your
demographics in natural conversation, reads them back, and saves them to PostgreSQL
through a REST API that you can also query directly.

## Live demo

| | |
|---|---|
| Phone number | **+1 (864) 625-5330** |
| API base URL | https://voice-agent-production-ca85.up.railway.app |
| API docs (Swagger) | https://voice-agent-production-ca85.up.railway.app/docs |
| Dashboard | https://voice-agent-production-ca85.up.railway.app/ |

No credentials are needed: the REST API is open for review (see [Known limitations](#known-limitations-and-trade-offs)).

## Architecture

```
Caller's phone
     │  audio
     ▼
┌─────────────────────────── Vapi ───────────────────────────┐
│ phone number → speech-to-text → LLM (prompt + tools)       │
│                               → text-to-speech → caller    │
└───────────────┬────────────────────────────────────────────┘
                │ POST /vapi/webhook  (when the agent calls a tool,
                ▼                      and once when the call ends)
┌──────────────────────── This service ──────────────────────┐
│ routers → services → repositories → PostgreSQL             │
└────────────────────────────────────────────────────────────┘
                ▲
                │ GET / POST / PUT / DELETE /patients
           Reviewer, dashboard
```

Vapi owns telephony, speech and the LLM conversation. This service owns the data: it
validates, stores and returns patients. The two only meet at one webhook.

The voice agent and the REST API call the **same service layer**, so a record saved by
phone passes exactly the same validation as one sent to `POST /patients`.

### Layers

| Layer | Folder | Responsibility |
|---|---|---|
| Routers | `app/routers` | HTTP only: parse the request, call a service, wrap the response |
| Services | `app/services` | Business rules; the voice agent's tool handlers |
| Repositories | `app/repositories` | Call the SQL functions; no SQL is written in Python |
| SQL | `app/sql/functions` | PostgreSQL functions holding every query; soft-deleted rows are hidden here |
| Models | `app/models` | SQLAlchemy tables |
| Schemas | `app/schemas` | Request/response payloads and validation |
| Utilities | `app/utilities` | Field normalisation, response envelope, error formatting |
| Voice | `app/voice_agent` | The agent's prompt, tools and Vapi configuration |
| Interfaces | `app/interfaces` | An abstract class for every service, repository and utility |
| Containers | `app/containers` + one per layer | Dependency injection wiring |
| Database | `app/database` | Engine and transactional sessions |
| Migrations | `alembic` | Schema, generated from the models |

Classes depend on interfaces and receive their collaborators through the constructor.
Each layer has its own container (`app/services/container.py`, and so on), and
`app/containers/container.py` composes them.

### What happens on a call

1. Vapi answers and speaks the greeting. The LLM collects the required fields, guided by the prompt.
2. As soon as it has a phone number, the agent calls `check_existing_patient`. If a record exists it offers to update it instead.
3. The agent reads everything back and asks for confirmation.
4. On confirmation it calls `save_patient`. The server validates, saves, and replies with success or with the exact fields that are invalid.
5. The agent says "You're all set, _first name_" and hangs up; or re-asks for the invalid fields; or, if the save failed, apologises and says so.
6. When the call ends, Vapi sends the transcript, which is stored against the patient.

## Tech stack and why

| Choice | Why |
|---|---|
| **Vapi** for telephony, speech and LLM orchestration | Provides the phone number, speech-to-text, text-to-speech, interruption handling and tool calling, so the effort goes into the prompt and the backend. The assistant is created from code in this repo, not by hand in a dashboard. |
| **FastAPI** | Typed request validation, automatic OpenAPI docs, small surface. |
| **PostgreSQL** | Real column types and constraints (UUID, DATE, CHECK), and data that survives restarts on any host. |
| **SQLAlchemy + Alembic** | The models are the single source of the table schema; the first migration is generated from them. A second migration then loads the SQL functions from `app/sql/functions`, which the repositories call by name. |
| **dependency-injector** | Explicit wiring, so any implementation can be swapped or faked. |
| **Railway** | Always-on process with managed Postgres; no cold start in the middle of a call. |

## The voice agent prompt

The system prompt is in [`app/voice_agent/agent_prompt.py`](app/voice_agent/agent_prompt.py). It is
split into named sections, each with a comment explaining why it exists:

| Section | Purpose |
|---|---|
| Identity | Who the agent is; injects today's date (to catch future birth dates) and the caller ID |
| How to speak | Short turns, one question at a time, no lists or field names, digits read one by one |
| What to collect | Required fields, then a single opt-in offer for the optional ones; out-of-order answers are kept |
| Getting details right | Per-field rules and how to re-ask for just the field that is wrong |
| Corrections and starting over | Spelled corrections are final; "start over" discards everything |
| Reading back before saving | Nothing is saved without an explicit yes |
| Your tools | When to call each tool and what to say for each possible result |
| Staying on task | No medical advice, emergencies go to 911, honest about being a virtual assistant |

Validation rules appear in the prompt so the agent can catch bad input the moment it is
spoken. The server validates again on save; the prompt is for a good conversation, the
server is for correctness.

The tools are defined in [`app/voice_agent/agent_tools.py`](app/voice_agent/agent_tools.py) and
executed by [`app/services/voice_agent_service.py`](app/services/voice_agent_service.py).

## REST API

Every response uses the envelope `{ "data": ..., "error": null }`. On failure `data` is
`null` and `error` is `{ "code", "message", "details": [{ "field", "message" }] }`.

| Method | Endpoint | Description | Success |
|---|---|---|---|
| GET | `/patients` | List patients. Filters: `last_name`, `date_of_birth`, `phone_number`. Paging: `limit` (default 100, max 500), `offset` | 200 |
| GET | `/patients/{id}` | One patient by UUID | 200 |
| POST | `/patients` | Create a patient | 201 |
| PUT | `/patients/{id}` | Update; only the fields sent are changed | 200 |
| DELETE | `/patients/{id}` | Soft delete (sets `deleted_at`) | 200 |
| GET | `/patients/{id}/calls` | Call transcripts linked to the patient | 200 |
| GET | `/health` | Server and database health | 200 |

| Status | When |
|---|---|
| 400 | Malformed JSON, an ID that is not a UUID, an invalid query parameter |
| 404 | No such patient, or the patient was soft-deleted |
| 422 | Well-formed request with one or more invalid fields; every invalid field is listed |
| 500 | Unexpected server error; no internal detail is returned |

```bash
curl -X POST "$API/patients" -H "Content-Type: application/json" -d '{
  "first_name": "Jane", "last_name": "Doe", "date_of_birth": "04/12/1988",
  "sex": "Female", "phone_number": "2025550143",
  "address_line_1": "123 Main Street", "city": "Springfield", "state": "IL", "zip_code": "62704"
}'

curl "$API/patients?last_name=Doe"
curl -X PUT "$API/patients/<id>" -H "Content-Type: application/json" -d '{"city": "Chicago"}'
curl -X DELETE "$API/patients/<id>"
```

## Web console

The page at `/` is a small operations console for front-desk staff, served by the same
application (`app/static`, plain HTML, CSS and JavaScript modules with no build step).

| Page | What it does |
|---|---|
| Overview | Totals, share of patients registered by voice, registrations per day, record completeness, latest registrations and calls |
| Patients | Server-side search, filter by source (voice or API), sorting, paging, CSV export; a side panel to view, edit or remove a record |
| Calls | Every call including those that ended without a registration, searchable by patient, caller number or transcript text, with the conversation shown turn by turn |

It reads through three extra endpoints, `GET /dashboard/summary`, `/dashboard/patients`
and `/dashboard/calls`, and edits or removes patients through the `/patients` API, so it
gets the same validation as every other client. The page is served with a strict
Content-Security-Policy and writes record data as text only.

## Data model

The `patients` table has the fields from the brief with the same names, plus `deleted_at`
for soft delete. A readable copy of the schema is in
[`app/sql/schema_reference.sql`](app/sql/schema_reference.sql).

| Field | Rule |
|---|---|
| `first_name`, `last_name` | 1-50 characters; letters, hyphens, apostrophes |
| `date_of_birth` | Real date, not in the future; accepted and returned as MM/DD/YYYY |
| `sex` | Male, Female, Other, Decline to Answer |
| `phone_number`, `emergency_contact_phone` | 10 digits; formatting and a leading `1` are stripped |
| `email` | Valid format; stored lowercase |
| `state` | Valid 2-letter abbreviation |
| `zip_code` | 5 digits or ZIP+4 |
| `insurance_member_id` | Letters and digits |
| `preferred_language` | Defaults to English |
| `patient_id`, `created_at`, `updated_at` | Generated by the server; ignored if a client sends them |

The database enforces types, NOT NULL, lengths, the four `sex` values and phone, state
and ZIP lengths. Rules that need logic (not-in-the-future, name characters, valid state)
are enforced in the application.

**Where validation is deliberately more forgiving than the brief**, because the input
often comes from speech:

- Names may contain single spaces and accented letters ("De La Cruz", "José").
- A full state name ("Texas") is accepted and stored as `TX`.
- `sex` accepts a few spoken forms (`m`, `f`, "prefer not to say") and stores the canonical value.
- Insurance member IDs have spaces and hyphens removed and are uppercased.
- Birth years before 1900 are rejected.

## Edge cases

| Situation | What happens |
|---|---|
| Invalid date of birth or phone | The agent re-asks for that field only. If something slips through, the server names the invalid fields and the agent re-asks for those. |
| Caller corrects a detail | Only that field changes, at any point including the read-back. A spelled-out correction overrides what was heard. |
| Caller wants to start over | Everything collected is discarded and the agent begins again. |
| Call drops mid-conversation | Nothing is saved, because saving only happens after confirmation. The call is logged with no patient attached. |
| Database write fails | The agent is told nothing was saved; it apologises, retries once, then says honestly that registration failed. The caller never hears silence or a false "you're all set". |
| The agent tries to save without the read-back | The save tool requires a `read_back_confirmed` flag. Without it the server saves nothing and tells the agent to read everything back first. |
| The agent retries a save | The second save updates the record the call already created instead of inserting a duplicate. |
| Returning caller | Recognised by phone number and offered an update. Only the name on file is read out. |

## Setup

Requires Python 3.12 and a PostgreSQL database.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt
```

Create `env/.env` (git-ignored) with the variables below, then:

```bash
alembic upgrade head              # create the tables
python -m app.main                # http://localhost:8000  (docs at /docs)
python -m scripts.setup_vapi      # create/update the Vapi assistant and phone number
```

`setup_vapi` is safe to run again; run it after any change to the prompt or tools.
The repo is the source of truth for the assistant: reload the Vapi dashboard after
running it, because a test call started from a stale dashboard page uses that page's
copy of the prompt, and saving from it overwrites the assistant.

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL URL. Required: the data layer calls PostgreSQL functions, so no other database is supported. |
| `VAPI_WEBHOOK_SECRET` | Yes | Shared secret Vapi sends in `X-Vapi-Secret`; requests without it get 401. |
| `PUBLIC_BASE_URL` | For setup | Public HTTPS URL of this service, given to Vapi as the webhook address. |
| `VAPI_API_KEY` | For setup | Vapi private key, used only by `scripts/setup_vapi.py`. |
| `CLINIC_NAME` | No | Name the agent uses. Default: Lakeside Family Health. |
| `SEED_DEMO_DATA` | No | Insert two demo patients when the table is empty. Default: true. |
| `VAPI_MODEL_PROVIDER`, `VAPI_MODEL` | No | LLM used by the agent. Default: openai / gpt-4.1. |
| `VAPI_VOICE_PROVIDER`, `VAPI_VOICE_ID` | No | Voice. Default: vapi / Clara. |
| `VAPI_AREA_CODE` | No | Preferred area code for a new number. Default: 415. |

### Deployment (Railway)

1. New project from this GitHub repo; add a PostgreSQL database.
2. On the app service set `DATABASE_URL=${{Postgres.DATABASE_URL}}` and `VAPI_WEBHOOK_SECRET`.
3. Generate a public domain.
4. Locally, set `PUBLIC_BASE_URL` to that domain and run `python -m scripts.setup_vapi`.

`railway.json` runs `alembic upgrade head` before starting the server.

## Tests

```bash
pytest                      # everything
pytest app/tests/unit       # no database needed
pytest -m "not browser"     # skip the headless-browser tests
```

| Folder | What it covers | Needs |
|---|---|---|
| `app/tests/unit` | Field rules, schemas, the voice agent's tool handlers (with fakes), dashboard figures, the agent's prompt and tool definitions, the SQL function files | Nothing |
| `app/tests/integration` | The REST API, the Vapi webhook, the console endpoints and the SQL functions | PostgreSQL (`DATABASE_URL`) |
| `app/tests/frontend/unit` | The console's formatting helpers and API client, run with Node's built-in test runner | Node 22+ |
| `app/tests/frontend` | The console in a headless Edge or Chrome: search, editing with validation errors, removal, transcripts, theme, phone layout | PostgreSQL and a browser |

Integration and browser tests run against the database in `DATABASE_URL`. Every row they
create is marked (a last name starting `Pytest`, a call id starting `pytest-`) and removed
before and after the run. Tests that lack Node or a browser are skipped, not failed.

`python -m scripts.verify_live_api` is a separate end-to-end check for a running server,
deployed or local. It confirms each write by reading the row from the database, and also
covers concurrency, database constraints, persistence across a restart and migrations.
The latest run is in [`docs/api_verification.md`](docs/api_verification.md).

Observability: every tool call is logged to stdout with the call id, the payload the
agent collected and the result returned to it.

## Known limitations and trade-offs

- **Voice testing: five browser calls and four phone calls.** The browser calls, made from the Vapi dashboard, covered new registration, invalid input, corrections, starting over, optional fields and a returning caller; the fixes they led to are in the commit history. Four calls then reached the phone number over the phone network. The first full one exposed a fault: the agent said the closing line without saving when the caller's "yes" came with a question. The prompt was tightened (save immediately after the yes; never say "You're all set" without a successful save), and a later phone call with the same kind of answer saved the patient before closing. Hanging up mid-call and a failed database write were tested on the server, not on a live call.
- **Names can be misheard on a phone line.** On one test call "Hannah" was saved as "Anna" and "Birch Lane" as "Berg Lane"; the agent read both back and the caller confirmed. The agent now spells the first and last name back letter by letter as soon as the name is given. On the next phone call it again heard "Anna", spelled it back, and the caller corrected it to "Hannah"; the existing record was then recognised by phone number and updated. Street names are still not spelled back.
- **No authentication on the REST API or the web console.** Anyone with the URL can read, change and remove records, including through the console's edit and remove buttons. Acceptable for an assessment with fictional data; the first thing to add for real use.
- **Not HIPAA compliant.** Demographics are written to logs and stored unencrypted. Do not use real patient data.
- **Synchronous database access.** Endpoints run in FastAPI's thread pool. Simple and correct at this scale; async drivers would be the choice under heavy concurrent load.
- **Duplicate-save protection is an in-process lock.** It holds for one server process; several processes would need a database-level guard.
- **Phone numbers are not unique.** Family members share phones, so the agent asks rather than assuming.
- **A returning caller is identified by phone number alone.** To limit exposure, the agent only ever reads back the name on file.
- **PostgreSQL only.** Queries live in the database as SQL functions (`app/sql/functions`), loaded by `alembic upgrade head`. That keeps SQL out of Python, at the cost of the SQLite option for local development. Changing a function means adding a migration that reloads the files.
- **Some rules live only in the application**, not the database (see [Data model](#data-model)).
- **No rate limiting; CORS allows any origin**, so reviewers can call the API from anywhere.
- **Tests are not wired into CI.** The suite exists (`pytest`) but nothing runs it automatically on push.

## Next steps

- API authentication and per-caller identity verification before updates.
- Run the test suite in CI on every push.
- Spanish support and appointment scheduling.
- Database-level idempotency for saves; async database access.
