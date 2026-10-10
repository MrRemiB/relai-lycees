# Business and service integration v1 — installable anonymous pilot

This branch installs the browser business model in Python + shared SQLite. It remains a **fictitious decision-support prototype**, not a national RH system, consolidated legal rules, official appointment, ORS calculation, payroll, SSO, or an existing ministry connector. No real roster connector is present. Source references describe fictitious local rules; do not insert names, contact, home, health or free-text personal records.

## Install / authenticated settings

Follow `PRODUCTION.md` (Python >=3.11, `requirements-production.txt`, one Gunicorn process, authenticated coordinator session, HTTPS except explicit loopback tests, consistent backup). Existing session/CSRF/batch installation is unchanged. SQLite automatically adds `business_config`, `business_events`, `business_idempotency`; backups include them. Do not replace a live database with demo fixtures.

After login: **Paramètres métier** → empty model/current fictitious scenario → edit forms, zone and DEMO profile JSON → **Valider et prévisualiser** (no mutation) → **Appliquer explicitement** → readback from SQLite. Default is historical/draft; the prepared controlled scenario stays draft until explicit simulated validation. These are local rules, not certified administrative data. Individual mission fields and server batch JSON accept `mission_type` and dated `sessions`. Server batch UI remains durable, shared, asynchronous, bounded at **3000 needs**, and never assigns automatically. CSV is historical only; use JSON v1 for sessions/circuit. Server JSON results/CSV preserve these fields and review reasons.

A committed business document atomically increments the server revision and clears routes/proposals of all persisted jobs while increasing job generations. Profile roster append also invalidates jobs. Freshness transitions and assignment changes are included in context hashes and invalidate job read/resume. Single match rejects context changes during routing; assignment re-reads config, effective profile, needs and assignments under `BEGIN IMMEDIATE` after routing, preventing stale network results from committing. UI passes business revision and polls bounded audit events while visible; another client can make the current editor stale, in which case validation/commit returns409 rather than silently overwriting.

## Integration credentials — no default token

On the server (outside repository/web root), generate separate server/client files. No values are printed. For the systemd installation in `PRODUCTION.md`, use a dedicated directory traversable by the service group; the existing root-only `/etc/relai` directory cannot be read by the unprivileged process:

```bash
# Administrator on deployment host; do not run this for local fixture QA.
sudo install -d -o root -g relai -m 0710 /etc/relai-integrations
umask 077
sudo .venv-production/bin/python scripts/setup_integration.py \
  --server-file /etc/relai-integrations/tokens.json \
  --client-file "$HOME/.config/relai/sync-client.env" \
  --id demo-sync --scopes read import
sudo chown "$(id -u):$(id -g)" "$HOME/.config/relai/sync-client.env"
sudo chown relai:relai /etc/relai-integrations/tokens.json
sudo chmod 0600 /etc/relai-integrations/tokens.json
```

The service can read its0600 hash file; `ProtectSystem=strict` keeps `/etc` read-only in the service namespace. Keep the directory administrator-owned and token rotation administrative. For a local non-systemd test, both files can instead live in private directories of the same user running Gunicorn.

The server JSON contains only SHA256 digest, ID and explicit allowed scopes; client file contains a random token. Both files are0600 and exclusive creation refuses overwrite. Keep the client file only on an authorized integration host. Set `RELAI_INTEGRATIONS_FILE=/etc/relai-integrations/tokens.json` in the protected service environment and restart Gunicorn. Alternatively set `RELAI_INTEGRATIONS_JSON` to the same digest-only JSON array using a protected environment loader, never inline a secret in shell history. File mode is checked. Maximum50 configured identities, scopes only `read`, `config`, `import`, no URL/callback/scope requested by caller. An integration cannot grant itself permissions.

Revocation/rotation: remove the configured ID/hash or replace its digest with a newly generated credential and restart the single process. This does not revoke coordinator sessions; use logout/expire sessions separately. Tokens are fixed-scope credentials, not OAuth/SSO. Store encrypted at rest through deployment secret management as appropriate. Do not log Authorization headers, echo credentials, use `set -x`, or put tokens in URLs. Cookie + bearer is rejected; authorization failure never falls back to a session. Exact `Bearer <token>` only, digest checked constant-time against configured identities. Browser settings never receive an integration secret.

## Working push/pull contract

Machine requests use bearer **only**, no Cookie. Humans may use coordinator session on the same v1 endpoints; **all POST and PUT** then require exact configured `Origin` and `X-CSRF-Token`. Bearer is permitted only on the v1 integration routes below, never on assignment, bootstrap, static assets, human business aliases or batches. No CORS access is enabled and no arbitrary server-side URL fetch/callback exists.

| Route | Method | Scope | Result |
|---|---|---|---|
| `/api/v1/config` | GET | read | complete Business v1 document |
| `/api/v1/config` | PUT | config | full document replacement, same transaction/idempotency semantics as imports commit |
| `/api/v1/reference/zones` | GET | read | `{schema_version:1,revision,items:[Zone]}` |
| `/api/v1/reference/profiles` | GET | read | anonymous administrative DEMO dossiers (not roster names) |
| `/api/v1/reference/timetables` | GET | read | `{teacher_id,timetable}` items, same revision |
| `/api/v1/imports/validate` | POST | import | `{valid:true,document,revision}` dry-run; no config/event/job mutation |
| `/api/v1/imports/commit` | POST | import | committed complete document, transactional replace |
| `/api/v1/events?cursor=v1:0&limit=100` | GET | read | `{schema_version:1,revision,events,next_cursor,has_more}` |

`openapi.json` is the repository OpenAPI3.1 contract with strict closed objects. `BUSINESS_BROWSER.md` records the full shared JSON schema/semantics (browser local storage statements do not describe server persistence). The document is `{schema_version:1,revision,config,zones,profiles}`. Revision is an integer0..9007199254740991 (booleans forbidden). Full replacement, **not merge/append/patch**. Server writes `expected_revision+1`, ignoring the imported document revision. Profiles must refer to existing anonymous `DEMO-0000` roster records, official RAD UAI, explicit zones/adjacency/contract/engagement and timestamped timetables. Incoming document keys are strictly the browser schema. Duplicate keys, extra personal/free-text fields, nonexistent IDs/sites/zones, nonfinite or boolean numbers, invalid dates/hours/fuseaux and duplicates are rejected atomically.

Request envelope:

```json
{
  "document": {"schema_version":1,"revision":0,"config":{},"zones":[],"profiles":[]},
  "expected_revision": 0,
  "confirm_demo": true,
  "idempotency_key": "sync_snapshot_001"
}
```

**`config:{}` above is abbreviated, not a valid payload**: obtain and edit a complete GET snapshot or use the UI template. `document` may also be strict JSON text. `idempotency_key` is required for v1 PUT/commit,8..128 `[A-Za-z0-9_-]`. Validate does not accept it. Optional envelope `source_reference` (bounded300) and `observed_at` (real ISO UTC `...Z`, never future) describe observation, but never override dossier/EDT freshness. Audit `observed_at` is server commit time. Missing, future or older-than-`freshness_days` dossier/EDT source timestamps pass schema validation but cause **review**, never executable simulation; exactly the age boundary remains fresh. Future rule validation date also causes review. Source labels are not trusted proof.

Idempotency is scoped to integration actor (or coordinator). Retry same key + same semantic payload returns the **original committed result**, even if the server revision advanced; no event/job mutation repeats. Same key with different payload409. First new key with stale `expected_revision`409; commit validates everything and updates config/jobs/event/key in one SQLite transaction. Dry-run success is not a reservation: commit can409 if another writer wins. Idempotency/event tables are currently retained indefinitely; size/retention quotas require deployment policy and cleanup with explicit recovery planning (no automatic pruning). Do not reuse keys across independent operations.

Safe curl example (TLS origin already configured, client env file generated above; never print token):

```bash
set +x
set -a; . "$HOME/.config/relai/sync-client.env"; set +a
export RELAI_URL=https://relai.example.fr
# Header supplied over stdin rather than token in process argv. Do not use verbose/trace.
printf 'Authorization: Bearer %s\n' "$RELAI_TOKEN" | \
  curl --fail-with-body --silent --show-error --header @- \
  "$RELAI_URL/api/v1/config" --output business.json
# Prepare valid full snapshot + envelope without exposing any credential.
python -c 'import json; b=json.load(open("business.json")); json.dump(dict(document=b,expected_revision=b["revision"],confirm_demo=True),open("validate.json","w"),ensure_ascii=False)'
printf 'Authorization: Bearer %s\n' "$RELAI_TOKEN" | \
  curl --fail-with-body --silent --show-error --header @- \
  --header 'Content-Type: application/json' --data-binary @validate.json \
  "$RELAI_URL/api/v1/imports/validate" --output validation.json
python -c 'import json; p=json.load(open("validate.json")); p["idempotency_key"]="sync_snapshot_001"; json.dump(p,open("commit.json","w"),ensure_ascii=False)'
printf 'Authorization: Bearer %s\n' "$RELAI_TOKEN" | \
  curl --fail-with-body --silent --show-error --header @- \
  --header 'Content-Type: application/json' --data-binary @commit.json \
  "$RELAI_URL/api/v1/imports/commit" --output committed.json
# Repeat commit.json to retry; read config/events for exact current-state confirmation.
printf 'Authorization: Bearer %s\n' "$RELAI_TOKEN" | \
  curl --fail-with-body --silent --show-error --header @- \
  "$RELAI_URL/api/v1/events?cursor=v1:0&limit=100" --output events.json
unset RELAI_TOKEN
```

Generic push means a client creates a full anonymous snapshot, dry-runs, then commits with revision/key. Generic pull means GET config/reference plus incremental events; page until `has_more:false`, saving opaque `next_cursor`. Cursor format is versioned `v1:<last event ID>`; defaultv1:0, limit1..200, ascending IDs, no negative/future-schema cursor. Events contain only ID, revision, actor `coordinator`/`integration:<configured-id>`, kind and timestamp, not dossier content/health. This is a polling/audit scaffold, not an installed external connector. Reference pulls must compare revisions and restart if snapshots disagree. No outgoing notification feed, service-fait log or arbitrary callback.

Errors:400 malformed JSON/schema/IDs/dates/cursor,401 missing/bad auth,403 scope/mixed-cookie/origin/CSRF,404 unknown resource,409 revision/idempotency/race conflict,413 body>3MB,415 media type,503 SQLite unavailable. Full business document≤2.5MB UTF8, profiles≤5000, zones≤500, sessions≤1000/object, needs/batch≤3000. The historical anonymous roster append endpoint remains human/session only,1..200 profiles per request,≤5000 total. No accepted real RH input.

## Honest limitations / verification

Known timetable requires requested sessions and fresh source. Unknown timetable conservatively blocks date-overlapping assignments. Known same-site, non-overlapping sessions may share capacity; weekly capacity and RCD remaining hours include actual local simulations plus batch proposals. A proposed mission is not service done. Intersite transitions stay in review: RAD→mission IGN evidence is **not** site→site transition evidence. Only metropolitan Europe/Paris dates/times execute; other zones/overseas, nonexistent/ambiguous DST times or offset transitions remain in review. No guessed duration, national threshold, mutual adjacency or implicit contract permission.

Run:

```bash
python -m unittest discover -s tests -v
node --test frontend_tests/*.test.mjs
.venv-production/bin/python scripts/smoke_production.py
```

Python/browser parity uses the same JSON fixtures for eligible/draft/unknown/zone/contract/RCD/cumulative capacity/freshness/future/EDT/DST cases and compares full business results. Tests also cover scopes, dry-run, transactions, readback, idempotency/event duplicates/conflict, session PUT CSRF, config assignment race, durable job invalidation, session persistence and3000 historical limits. Real Gunicorn smoke uses random distinct integration credentials and an isolated temporary SQLite database, never the live DB. No fixture/provider output is represented as real IGN traffic or a real roster connector. Review remains required before deployment.
