# Build Plan — Voice AI Patient Registration Agent

CareCloud take-home. 3-hour limit. Voice agent (Vapi) that registers U.S.
patients over a phone call, persists to a DB, and exposes a REST API.

Strategy: **build + test everything locally first, deploy last.** During dev
the webhook is exposed with a `cloudflared` quick tunnel so Vapi can reach it.
Test each tool with fake POSTs before ever making a voice call — so when
something breaks we know if it's our code or the Vapi wiring.

### Working agreement
- **Incremental loop:** write a small slice → test it together → confirm it
  works → only then build the next slice. Never dump all features at once.
- **Tests are dev-only.** Any test scripts are throwaway for our own
  verification and will be DELETED before submission. Ship clean code only.
- **The voice agent must sound human, not robotic.** Warm, natural intake
  coordinator — contractions, brief acknowledgements ("Got it", "Perfect"),
  no listing fields like a form. This is a graded dimension (20%).

Priority order (from the challenge's own guidance — a working partial system
beats an ambitious broken one):
1. Public URL returning 200 + one tool working end to end
2. Data persisted and visible via a GET endpoint
3. Remaining REST endpoints + validation
4. Prompt quality / conversational polish
5. README + deployment

---

## Checklist

### Phase 0 — Environment
- [x] `carecloud` venv created + deps installed (fastapi, uvicorn, sqlalchemy, ...)
- [x] `cloudflared` downloaded (instant HTTPS tunnel, no account)
- [x] git available

### Phase 1 — Backend skeleton
- [ ] Project structure (`app/`, `tests/`, `vapi/`, `scripts/`, `data/`)
- [ ] `config.py` — env loading, settings
- [ ] `.env.example` + `.gitignore`
- [ ] `main.py` — FastAPI app boots, `GET /health` returns 200

### Phase 2 — Data layer
- [ ] `models.py` — SQLAlchemy `Patient` (18 fields, constraints, soft-delete, timestamps)
- [ ] `database.py` — engine, session, `init_db()`
- [ ] `scripts/seed.py` — 1–2 demo patients

### Phase 3 — Validation + REST API
- [ ] `validators.py` — name, DOB (not future), US phone, state, ZIP, email
- [ ] `schemas.py` — Pydantic request/response models
- [ ] `crud.py` — DB operations (create, list w/ filters, get, update, soft-delete, find-by-phone)
- [ ] `routers/patients.py` — GET/POST/PUT/DELETE with `{data, error}` envelope + status codes
- [ ] Test REST API in isolation (pytest + curl) — **before any Vapi wiring**

### Phase 4 — Vapi webhook
- [ ] `routers/vapi.py` — `/webhook`: `tool-calls` (register_patient, lookup_patient) + `end-of-call-report`
- [ ] Tool handlers return speakable strings, never exceptions
- [ ] Test webhook with fake POSTs (each tool in isolation) — **before voice**

### Phase 5 — Vapi assistant + phone
- [ ] Vapi account + API keys
- [ ] `scripts/vapi_setup.py` — create assistant + tools via Vapi API
- [ ] System prompt (phone-call aware, emergency boundary, confirmation flow)
- [ ] Phone number provisioned + assistant attached
- [ ] cloudflared quick tunnel; wire webhook URL into assistant AND every tool
- [ ] Live voice call test — full registration + second-call persistence

### Phase 6 — Polish + ship
- [ ] Bonus: duplicate detection by phone
- [ ] `README.md` — setup, architecture, tech justification, env vars, limitations, next steps
- [ ] Deploy to Alibaba ECS (cloudflared systemd); fallback = keep local tunnel
- [ ] Final submission: repo URL + phone number + API base URL

---

## Cut-scope order (if time runs short)
Drop from the bottom up: dashboard/UI → multi-language → appointment
scheduling → PUT/DELETE polish. Never cut: one tool working over voice +
persistence + a GET endpoint + README.
