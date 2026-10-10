# Production business / integration QA — uncommitted handoff

## Verified execution

- `python3 -m unittest discover -s tests -q`: **73 tests passed**, including existing production/security/3000 tests and business persistence, scoped auth, human PUT CSRF, dry-run, strict imports, config CAS race, full readback, idempotency/events, assignment config race, actual simulation sessions/RAD and conservative intersite/fuseau review.
- `node --test frontend_tests/*.test.mjs`: **72 tests passed**, no skips. Historical eligibility parity remains. Shared JSON business fixtures compare full Python/browser status, reasons and review flags, including source age boundaries/future dates, cumulative capacity/RCD, actual local simulation collisions, unknown EDT, intersite review and DST gaps/ambiguity/offset crossings.
- Python compilation, JS syntax checks, `git diff --check`: passed.
- Runtime installation: `tzdata==2026.5` installed in existing isolated `.venv-production`; `pip check` passed. Standard zoneinfo now has an explicit IANA fallback dependency.
- Repository `openapi.json` validated as OpenAPI3.1 with `openapi-spec-validator` in a scratch-only QA venv; shared Business documents validate against published JSON Schema with `jsonschema`. Neither QA validator is a runtime dependency.
- Real `.venv-production/bin/python scripts/smoke_production.py`: Gunicorn started with isolated temporary SQLite and random non-displayed coordinator/integration credentials. Legacy health/private routes/login/origin/CSRF, durable3000 deferred jobs, cancellation/restart, logout and single-process/missing-credential startup protection remain verified. Added actual HTTP scoped read/import/config, dry-run revision0/no event, commit/retry/readback, conflict409/no duplicate event, reference routes, malformed cursor, bearer denial on bootstrap, controlled draft match and durable job review, manual server settings revision2 and atomic job invalidation. Config PUT is exercised through real HTTP, including session CSRF403, readscope403, stale409, config revision3 and idempotent retry. Credential-safe curl header stdin GET readback is exercised. SQLite backup integrity/foreign keys + stopped-process restore + restart config/events readback verified. No IGN calls or actual assignments in the HTTP smoke; successful route assertions in unit tests use explicitly injected fixtures.

## Authenticated browser QA actually performed

Temporary loopback Gunicorn with generated coordinator credential; a real HTTP login created the session before opening the browser. No password/token displayed or typed in chat/browser helpers. In the authenticated interface:

1. Opened **Paramètres métier**, prepared current fictitious Dijon scenario, validated preview, explicitly applied and reread **revision1**, controlled/draft,72 UAI,1 zone,25 anonymous dossiers.
2. Opened scenario mission and searched through the **server** API: **0 executable candidates,3 review dossiers** with draft reason. No need or assignment was saved and no route was invented.
3. Reloaded actual page: revision1/rules/dossiers persisted from SQLite.
4. Existing **Plan serveur** pane and mission circuit/session controls remained mounted. At390px mobile: document width390, no business input/select/textarea/button overflow. Screenshot inspected.

The QA process was stopped. Its database/session file and screenshot are scratch/browser-harness artifacts, not repository files, not live pilot data. Browser QA did **not** certify RGAA, exercise every contract/RCD field manually, or make validated real IGN assignments; these constraints have unit/shared-fixture coverage only. Independent review remains with the parent before any commit/deploy.

## Exact worktree files

New:
- `business.py`, `business_store.py`
- `scripts/setup_integration.py`
- `static/business-core.js`, `static/business-context.js`, `static/business-ui.js`
- `tests/test_business.py`, `tests/fixtures/business-parity.json`, `frontend_tests/business-parity.test.mjs`
- `openapi.json`, `BUSINESS_SERVER.md`, `QA_BUSINESS_SERVER.md`
- `BUSINESS_BROWSER.md`, `EVOLUTION_METIER.md` (copied schema/port references from published main6d0eba8, not altered on main)

Modified:
- `app.py`, `matching.py`, `batches.py`, `production.py`, `wsgi.py`
- `static/app.js` (curated wiring, retained auth dispatcher), `static/server-batch-ui.js` (retained durable UI plus JSON import/export/review), `static/browser-api.js`, `static/batch-core.js`, `static/batch.css`
- `scripts/smoke_production.py`, `requirements-production.txt`, `.env.example`, `README.md`, `PRODUCTION.md`

## Limits / remaining review

- No real RH connector, SSO, establishment-scoped roles, certified national legal rules, official assignment or payroll. Anonymous DEMO profiles only.
- Site→site transition proof is not wired into routes or persisted: reviews stay non-executable, even if RAD→mission is known. Outside Europe/Paris/overseas and ambiguous/nonexistent/offset-changing session clocks stay in review.
- Existing IGN route/cache bounds and one-process/single-job admission remain; no multi-worker distributed regulator, global optimizer or guaranteed CPU/runtime SLA. Controlled proposals use current rules and bounded one-hop augmentation, but not an optimal assignment algorithm.
- Events/idempotency entries retain indefinitely; bounded pages and body/object limits exist, but production retention/quota policy and operational token management remain deployment responsibilities. Optional envelope observation never overrides source timestamps.
- The Python/server context fingerprint and browser fingerprint are both SHA256 invalidation mechanisms, but their canonical serialization is **not asserted to be byte-identical**. Shared parity concerns business decisions, not interchangeability of cross-runtime snapshot tokens.
- No git commit/push, main code change, deployment or public mutation. Production remains on its original branch head with these uncommitted changes. Main tracked files remain unchanged; pre-existing untracked research/impeccable folders were not touched.
