# Frontend verification

## Current routing change — offline tests

Run from the repository root:

```sh
node --check static/app.js
node --check static/utils.js
node frontend_tests/utils.test.mjs
node --test frontend_tests/routing.test.mjs
```

The original utility suite retains 16 assertions. The routing suite has eight test groups: duration formatting (including genuine zero versus missing/invalid values), provider GeoJSON availability/coordinate validation, minute payloads, backend time-order preservation with partial warning/retry, road GeoJSON drawing with no straight-line fallback, persisted assignment audit display, saved-limit assignment consistency, and factual source/privacy/form contract checks.

TDD evidence: the first routing run failed all six initial groups for missing behavior; after implementation all six passed. The two additional assignment groups failed for missing audit display and incorrectly using the form limit rather than the stored need limit; both then passed. Node syntax checks passed for both shipped modules.

Test data in `routing.test.mjs` are explicitly synthetic, hand-authored offline fixtures; their durations and geometry are **not** measured IGN journeys. The VM harness executes the actual frontend functions with minimal DOM/Leaflet transport substitutes; it makes no network calls, starts no server, creates no durable needs and tests no live provider availability. No fixture duration or geometry is shipped in `static/`. Real routing behavior is defined by `ROUTING_CONTRACT.md`; production estimates come only from the backend/IGN response.

Minute limits default to 90, preserve valid zero, and are sent on creation/matching. Assignment uses the stored need limit. Audit facts are read after mutations through `/api/bootstrap` because `/api/needs` does not expose the separate assignments collection. CSV includes the stored/default limit plus assignment seconds and road kilometres when available. Partial comparisons have a separate persistent warning and retry control. Form busy text is “Calcul des itinéraires…”; request timeout is 75 seconds.

CSS preserves the navy/teal map-plus-mission layout and adds shrinkable paired fields, wrapping candidate text/controls, and a one-column source metadata layout below 480px. Current routing desktop/390px/320px browser geometry and visual approval are reserved for parent integration QA; historical viewport results below are not a new certification. No screenshot was taken for this change.

Mechanical Impeccable detector ran once; only advisories appeared, all from incumbent dialog elevation, colors and type sizes. No new palette, typography or redesign was introduced.

## Historical first-version verification (straight-line matching)

The following describes the earlier geodesic build, not current routing verification. The old isolated server helper starts the real backend; with the routing backend it may contact IGN. Do not launch it in offline CI without an injected fixture router.

Run `node --check static/app.js`, `node --check static/utils.js`, and `node frontend_tests/utils.test.mjs` from the repository root. The utility suite asserts date rollover, UTC-to-Europe/Paris vacation boundaries, formula-safe CSV, safe source URLs, missing coordinates, accent-insensitive search and unknown-sector handling.

`python frontend_tests/serve_integration.py` serves the real backend and official data on port 8128 with a disposable SQLite database in the configured scratch directory. It never modifies `runtime/relai.sqlite3`. It is an integration test server, not a mocked API or a production launch command.

Browser integration exercised against this isolated server:
- Official bootstrap: 3,451 public schools, 3,423 geolocated public schools, genuine Leaflet clusters.
- Real public Carnot Dijon scenario: 12 weekly hours of mathematics, today + 7 through today + 21; three eligible synthetic profiles. Preview created no need.
- Save and direct save-and-assign both exercised; saved needs also recomputed successfully. Save → simulated assignment → release → close; each mutation read back through `/api/needs`; final record was closed with no teacher assigned.
- Guadeloupe academy filter: 37 public schools; overseas locations not dropped.
- Calendar advisory: Toussaint Dijon 2026 displayed 2026-10-17 through 2026-11-02 after Europe/Paris conversion, without excluding candidates.
- Desktop 1440px panel measured 400px. At 390px and 320px, document width equalled viewport width; no overflowing controls, stacked map and mission.
- Blocking Leaflet and `/api/calendar`: genuine map failure message, 60 accessible directory results, lycée selection and form still working; unavailable calendar was nonfatal.

Visual screenshot inspection is deliberately reserved for the parent integration QA batch. No visual approval is claimed by these geometry or interaction checks.

Vendored assets: Leaflet 1.9.4 and leaflet.markercluster 1.5.3 from unpkg.com, with their upstream licenses and Leaflet PNG assets. OpenStreetMap tiles are external and attributed in-map; the interface discloses external requests. No synthetic teacher is plotted globally; only a shortlisted candidate's fictional administrative anchor is shown.
