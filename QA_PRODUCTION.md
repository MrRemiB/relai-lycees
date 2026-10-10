# Production pilot — verification actually executed

Scope: `/home/remi/projects/relai-lycees-production`, branch `production`. No commit, push, publication, main-worktree edit, external service activation or real HR data. `app.py`, `matching.py` and `routing.py` remain unchanged; production composes their existing Store/validation/RouteService.

## Commands and results

- `python3 -m venv .venv-production` then `.venv-production/bin/python -m pip install -r requirements-production.txt`: **Gunicorn 26.2.0, packaging 26.3 installed** in isolated venv. `.venv-production/bin/python -m pip check`: **No broken requirements found**.
- `.venv-production/bin/python -m unittest discover -s tests -v`: **58 tests, OK**, latest complete run **36.775 s**, no ResourceWarnings. Existing 41 Python tests plus 17 pilot tests. RED was observed for missing production module, missing helpers, unknown-school deferral and progressive-pass starvation before implementation/fixes.
- `node --test frontend_tests/*.test.mjs`: **45 tests, 45 pass, 0 fail** (includes 16 existing utility assertions). Existing public/demo tests retained. Three new tests check server dispatch and exercise controls creating/re-reading 3,000 needs, run, cancel, list/reopen and export against an isolated API fixture.
- `.venv-production/bin/python scripts/smoke_production.py`: **GUNICORN HTTP SMOKE OK**. Actual native Gunicorn, random non-displayed credentials, ephemeral loopback port and isolated SQLite. Public health200; private API/assets401; login200; CSRF403; missing origin403; batch3,000 created201, read200, run202; exact **0 proposed / 3,000 deferred / 0 unassigned** for an intentionally unlocated official school; cancellation persisted across real process restart/read200; logout revokes access401. Second process on same DB and missing-secrets WSGI startup both actually refused. No IGN network calls or assignments. Smoke-owned process and directory cleaned.
- `python -m compileall -q app.py matching.py routing.py batches.py production.py wsgi.py scripts tests`; `node --check static/app.js`, `static/batch-ui.js`, `static/server-batch-ui.js`: passed.
- `git diff --check`: passed.

## Server batch benchmark (offline, official national snapshot)

Real Python BatchService worker, all 3,000 generated needs from official schools, 1,600 anonymous profiles, existing RouteService with uncached budget explicitly zero (no network): **10.573 s**, phase finished, done3,000/total3,000, 80 route targets/results. Exact counts **0 proposed + 2,845 deferred + 155 unassigned = 3,000**, status partial. This is an offline throughput/check-accounting test, **not** evidence of real routed coverage. Unit routing fixtures separately verify exact route evidence, urgent competition, inclusive conflicts and a 3,000-need job with 1 proposed/2,999 conflicted-unassigned, no automatic assignment.

Pilot tests also cover strict atomic invalid/over-limit import, persistence, signed session tamper/expiry, cookie flags, CSRF/origin, logout, login throttling, private static isolation, context change during a route, competing runs, stale snapshot read/resume, expired route invalidation, deferred unknowns, bounded global pass targets, progressing beyond the first 80 unknown pairs, cancel/restart/resume, masked setup file permissions/no plaintext and SQLite backup integrity.

## Not claimed

Docker and Caddy absent here; Docker optional and skipped. systemd/Caddy files and target install/backup/restore runbooks delivered, not activated or TLS-certified. No authenticated real-browser rendering or national real-IGN3,000 coverage test performed in this change; frontend control tests use a DOM/API fixture, while HTTP tests exercise the actual server. Existing public Pages demo is preserved but not republished. Operator still must create their own credentials, install reverse proxy/certificates and verify the target. No SSO, institution-scoped roles, real HR roster, HR audit/DPO approval or national RH compliance.
