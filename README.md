# CareCloud — Voice AI Patient Registration

A voice AI agent you can call on a real phone number to register as a new
patient. The agent collects standard U.S. patient demographics through natural
conversation, validates them, persists them to a database, and exposes the
records through a REST API. Call back later and your data is still there.

Built for the CareCloud "Voice AI / Conversational AI Engineer" take-home.

---

## Live demo

| | |
|---|---|
| **Phone number (call this)** | **+1 (346) 292-9312** |
| **API base URL** | `https://eng-reasonable-can-breathing.trycloudflare.com` |
| **Health check** | `GET /health` |
| **View patients** | `GET /patients` &middot; **Dashboard:** `/dashboard` |

> The phone number (hosted by Vapi) is the stable entry point and always works.
> The REST API is served through an HTTPS Cloudflare tunnel (outbound-only, no
> inbound ports); the tunnel host can rotate, so if the API URL above is stale,
> the number still works and the current URL can be re-pointed in one command:
> `scripts/vapi_setup.py --assistant-id <id> --webhook-url <new>/webhook`.

---

## Architecture

```
  Caller ──dials──> Vapi ───────────> our FastAPI server ──> SQLite
                 (telephony,          (webhook: tools +      (persistent)
                  STT, LLM, TTS)       validation + data)         │
                                            │                     │
                                            └──> REST API <────────┘
                                        GET/POST/PUT/DELETE /patients
```

**Separation of concerns is the core design idea:**

- **Vapi = ears and mouth.** It owns telephony, speech-to-text (Deepgram),
  the LLM (GPT-4.1), and text-to-speech. Our server never touches audio and
  never calls an LLM directly. This is the fastest, lowest-latency path to a
  working voice agent — the conversation stays on Vapi's optimised pipeline.
- **Our server = the brain's data.** It receives JSON webhooks from Vapi,
  validates fields, reads/writes the database, and returns short spoken
  strings. The exact same validation and data layer also backs the public
  REST API, so a patient created by voice is identical to one created by API.

### Layers (each in its own module)

| Concern | File |
|---|---|
| Config / secrets (env) | `app/config.py` |
| ORM model + schema/constraints | `app/models.py` |
| DB engine + session | `app/database.py` |
| Field validation (shared) | `app/validators.py` |
| API request/response contracts | `app/schemas.py` |
| Data access (CRUD, soft-delete) | `app/crud.py` |
| Response envelope | `app/responses.py` |
| REST endpoints | `app/routers/patients.py` |
| Vapi webhook (tool-calls, reports) | `app/routers/vapi.py` |
| Voice tool handlers | `app/vapi_tools.py` |
| App wiring + error handling | `app/main.py` |
| Assistant/tools provisioning | `scripts/vapi_setup.py` |
| Voice system prompt | `vapi/system_prompt.md` |
| Seed data | `scripts/seed.py` |

---

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Telephony + STT/TTS | **Vapi** | Abstracts telephony/STT/TTS; provisions a real U.S. number; lets us focus on prompt + tools. Fastest path to a working call. |
| LLM | **GPT-4.1** (via Vapi) | Handles accented / partly mis-transcribed speech gracefully and follows the intake flow without getting stuck. |
| STT | **Deepgram nova-3, `multi`** | Multilingual model handles South-Asian / Hinglish accented English and code-switching noticeably better than generic English. `numerals` + endpointing tuned for phone/DOB digits. |
| Backend | **Python 3.12 + FastAPI** | Async, typed, minimal boilerplate; Pydantic gives server-side validation for free. |
| DB | **SQLite + SQLAlchemy 2.0** | Zero-config and file-backed — satisfies the only hard storage requirement (persistence across restarts). ORM gives clean constraints, timestamps, and soft-delete. Swappable to Postgres via `DATABASE_URL`. |
| Hosting | **Cloudflare tunnel** | Outbound-only HTTPS with no inbound ports opened and no TLS certs to manage. Vapi requires HTTPS; the tunnel provides it instantly. |

---

## Data model

Table `patients` (see `app/models.py`). Required unless noted.

`patient_id` (UUID, auto) · `first_name` · `last_name` · `date_of_birth`
(DATE, not future) · `sex` (CHECK: Male/Female/Other/Decline to Answer) ·
`phone_number` (10 digits) · `address_line_1` · `address_line_2` (optional) ·
`city` · `state` (2-letter) · `zip_code` (5 or ZIP+4) · `email` (optional) ·
`insurance_provider` / `insurance_member_id` (optional) ·
`preferred_language` (default English) · `emergency_contact_name` /
`emergency_contact_phone` (optional) · `created_at` / `updated_at` (UTC, auto)
· `deleted_at` (soft-delete marker).

Validation lives in `app/validators.py` and is shared by the API and the voice
tools, so a 3-digit phone or a future DOB is rejected the same way whether it
arrives by phone or HTTP.

---

## REST API

All responses use the envelope `{ "data": <payload|null>, "error": <null|{code,message,field?}> }`.

| Method | Endpoint | Notes |
|---|---|---|
| `GET` | `/patients` | List. Filters: `?last_name=`, `?date_of_birth=MM/DD/YYYY`, `?phone_number=` |
| `GET` | `/patients/{id}` | Fetch one by UUID (404 if missing/deleted) |
| `POST` | `/patients` | Create (201). Full server-side validation (422 on bad field) |
| `PUT` | `/patients/{id}` | Partial update — only supplied fields change |
| `DELETE` | `/patients/{id}` | Soft delete (sets `deleted_at`; row is never hard-deleted) |

Status codes: 200 / 201 / 400 / 404 / 422 / 500.

---

## Voice agent design

- **System prompt:** `vapi/system_prompt.md` — fully commented and version
  controlled. Key ideas:
  - "You are on a phone call; everything you say is spoken" → no markdown, say
    numbers naturally.
  - **HARD RULES** at the top: one thing at a time, never loop more than twice
    on a field, make a best guess and fix everything at the **end-of-call
    read-back confirmation** (required before saving).
  - Warm, human intake-coordinator persona (contractions, brief acknowledgements).
  - **Emergency boundary:** if the caller describes an emergency, tell them to
    hang up and call 911 — do not continue registration.
- **Tools** (function calls → our `/webhook`, defined in `scripts/vapi_setup.py`):
  - `lookup_patient(phone)` — recognises returning callers.
  - `register_patient(...)` — validates + saves; returns a spoken confirmation
    or a field-specific re-prompt.
  - `update_patient(...)` — updates an existing record.
- **Duplicate detection (bonus):** on a phone match, the agent offers to update
  instead of creating a second record.
- **Identity guard:** because a phone number is not proof of identity, when a
  record is found the agent confirms the name on file belongs to the caller
  before updating; otherwise it registers a new patient.
- **Tools return speakable strings, never exceptions.** Every handler is wrapped
  so a failure becomes a sentence a receptionist could say, never silence.

---

## Setup (local)

```bash
# 1. Create the venv and install deps
python -m venv carecloud
carecloud/Scripts/activate           # Windows
# source carecloud/bin/activate      # macOS/Linux
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
#   edit .env -> set VAPI_PRIVATE_KEY (from Vapi dashboard -> API Keys)

# 3. Seed demo patients (optional) and run the API
python -m scripts.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. Expose it over HTTPS (new terminal)
cloudflared tunnel --url http://127.0.0.1:8000
#   -> copy the https://<name>.trycloudflare.com URL

# 5. Provision / update the Vapi assistant + tools
python -m scripts.vapi_setup --webhook-url https://<name>.trycloudflare.com/webhook
#   first run prints an assistant id; later runs (when the URL changes) add
#   --assistant-id <id> to update the assistant AND all tool URLs together.
```

Then, in the Vapi dashboard, attach a phone number to the assistant (or use the
API), and call it.

### Environment variables (`.env`)

| Var | Required | Purpose |
|---|---|---|
| `VAPI_PRIVATE_KEY` | yes (for setup) | Server key to create the assistant/tools |
| `VAPI_WEBHOOK_SECRET` | no | If set, webhooks must carry a matching `x-vapi-secret` header |
| `DATABASE_URL` | no | Defaults to `sqlite:///data/patients.db` |
| `LOG_LEVEL` | no | Defaults to `INFO` |

---

## Deployment (production)

Runs on an Alibaba Cloud ECS instance (Ubuntu 22.04) as two systemd services,
so both survive reboots and restart on crash. The app binds to `127.0.0.1`
only and is reached exclusively through an outbound Cloudflare tunnel — **no
inbound ports are opened and nothing else on the host is touched** (an existing
service on ports 80/8086 was left untouched).

```
/opt/carecloud                     # git clone of this repo
  ├─ venv/                         # isolated Python env
  ├─ .env                          # secrets (not in git)
  └─ cloudflared                   # tunnel binary

carecloud-api.service    -> venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
carecloud-tunnel.service -> cloudflared tunnel --url http://127.0.0.1:8000
```

Update flow:

- **Server code change** → `cd /opt/carecloud && git pull && systemctl restart carecloud-api`
- **Prompt / model / STT / voice / tool signature change** → just re-run
  `scripts/vapi_setup.py --assistant-id <id> --webhook-url <url>/webhook`
  (updates Vapi directly; no server redeploy needed).

---

## Testing without a phone

Every tool can be exercised with a fake Vapi payload — ~10× faster than
placing a call and it isolates our code from the telephony wiring:

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"message":{"type":"tool-calls","call":{"id":"t1"},
       "toolCallList":[{"id":"tc1","name":"register_patient",
       "arguments":{"first_name":"Jane","last_name":"Doe",
       "date_of_birth":"04/12/1985","sex":"female","phone_number":"4155550142",
       "address_line_1":"123 Market St","city":"San Francisco","state":"CA",
       "zip_code":"94103"}}]}}'
```

---

## Observability

All conversations and the final collected payload are logged to stdout
(`carecloud.*` loggers), including every tool call, the registered patient id,
and each end-of-call report (duration, ended-reason, transcript).

---

## Known limitations & trade-offs

- **Identity = phone number.** There is no OTP / identity verification. The
  agent confirms the name on file before updating, but a determined caller who
  supplies someone else's number is not cryptographically stopped. A real
  system would verify via OTP or knowledge questions.
- **Accented STT is imperfect.** nova-3 `multi` improves South-Asian accents,
  but names and digits can still be mis-heard; the end-of-call confirmation is
  the safety net. (U.S.-accented callers get near-perfect capture.)
- **The agent sometimes still asks callers to spell a name** despite prompt
  instructions — being addressed; ironically spelling can worsen accuracy.
- **Barge-in / interruptions** are not yet tuned — the caller should let the
  agent finish a sentence before replying.
- **Cloudflare quick tunnel** URLs are ephemeral. For a stable deployment the
  tunnel runs as a systemd service (see Next steps).
- **Not HIPAA-compliant / not for real patient data** — this is an assessment.

---

## Next steps

- Stop the residual spelling behaviour and tune barge-in for a smoother call.
- Add identity verification (DOB/name match, or OTP) before updates.
- Move from the quick tunnel to a named Cloudflare tunnel as a systemd service
  for a permanent URL.
- Automated API tests; a small dashboard UI to browse patients.
- Appointment scheduling and multi-language (Spanish) flows (bonus).
