# Codex implementation instructions — Transportation GIS & Roadway Analytics Lab

## Project mission
Build an independently branded, honest, production-quality **transportation geospatial data engineering portfolio project**, using `index.html` as a functional interaction prototype, tailored to the skills assessed for Arizona Department of Transportation GIS Analyst Sr #544926. Preserve the user's original technical intent: demonstrate real linear referencing, repeatable data quality validation, roadway inventory processing, geospatial analysis, and reproducible reporting — not merely a pretty map. The project must also be reusable for university, municipal, GIS developer, spatial data analyst and transportation research roles.

## Nonnegotiables
1. Do not claim to be an ADOT, FHWA, Esri, HPMS or government product; clearly mark synthetic/illustrative data.
2. Do not claim Esri Roads & Highways or ArcGIS licensing/integration unless actually used and verified.
3. Do not invent official HPMS compliance: call outputs 'HPMS-style exploratory summary' until validated against a documented specification.
4. Preserve the provided HTML demo as a reference in `/prototype/index.html`; retain working interactions in rebuilt UI.
5. Do not overwrite or modify existing `wearable-mobility-research-pipeline` repository/deployment or other projects. This is a separate portfolio project. If reusable components are adapted, attribute and document provenance.
6. No secrets in git, no actual government datasets with uncertain licenses, no personal data. No fake benchmarks, test results or deployments.
7. Favor pragmatic incremental delivery and tests over complexity; do not install ArcGIS proprietary software as a dependency.

## Suggested architecture
- Frontend: React + TypeScript + Vite, responsive dashboard; MapLibre GL JS with public or locally served map base tiles **only if license and network access permit**, otherwise an offline GeoJSON/SVG vector fallback. Add accessible table, selected-route editor, QA panel, provenance/metadata view and report export.
- Backend: FastAPI + Pydantic; GeoPandas/Shapely/PyProj for geometry processing, Pandas for summaries, pytest for algorithms. SQLite for local/dev; optional PostgreSQL/PostGIS behind a feature flag if installation available. Use migrations and seeds.
- Data: explicitly synthetic test roads in geographic WGS84 (EPSG:4326), transform geometry to suitable metric projected CRS before any distance measurement, and store milepoints in miles. Never infer mileage from SVG pixels or raw longitude degrees.
- Deploy: Render Free-compatible web demo with documented sleeping/cold-start limits; synthetic read-only public demo, with edit operations in isolated ephemeral browser/session copy or disabled globally. No credential requirement for viewing.
- CI: GitHub Actions run pytest, frontend typecheck/build and smoke test; use Playwright when available.

## Data model
Route(route_id, display_name, jurisdiction, crs, source, source_license, synthetic_flag, dataset_version)
RoadSegment(segment_id, route_id, from_measure_mi, to_measure_mi, geometry, functional_class, lanes, surface, aadt, effective_date, modified_at, dataset_version)
QAFinding(id, dataset_version, segment_ids, rule_code, severity, details, created_at)
AuditEvent(id, segment_id, before, after, timestamp, action, actor='demo')
DatasetMetadata(dataset_version, generator_seed, coordinate_reference_system, source, license, schema_version, generated_at)

## Core science and engineering requirements
### A — Actual route linear referencing
- Build an ordered route polyline, calculate cumulative geodesic or projected segment lengths, and map a milepoint to an interpolated location with reproducible CRS handling.
- Support measure-to-coordinate and coordinate-to-nearest-measure, deterministic ties, boundary clamping/explicit out-of-range errors, and multipart/geometric discontinuity handling.
- Clearly distinguish **engineering route milepoint calibration** from physically measured geometry length; do not silently assert they are identical.
- Include tests for reversed endpoints, duplicate measures, zero-length segments, overlaps, gaps, boundary precision and CRS units.

### B — Roadway Characteristics Inventory
- Import and validate GeoJSON/CSV; assign stable IDs and route milepoint intervals; edit class/lanes/AADT/surface; log changes and export clean GeoJSON/CSV.
- Implement strict schema: finite numerical fields, `to_measure > from_measure`, valid class enumeration, nonnegative traffic, lanes 1–12, required metadata.
- Compute completeness and class-based segment miles; explain that overlapping intervals can inflate summed totals.

### C — QA/QC workflow
- Flag: interval overlap, measure gaps when continuity expected, invalid/negative lengths, missing fields, invalid class, bad lanes/AADT, invalid/empty geometry, duplicate IDs, bad CRS.
- Report severity, affected IDs, rule name, and reproducible fixture. Recompute findings after edits.
- Include clean and deliberately dirty fixture datasets.

### D — HPMS-style analytics (not certified HPMS)
- Group by route, functional class, segment-mile and traffic bands; produce frequency summaries, completeness statistics and downloadable technical report.
- Clearly distinguish exploratory metrics from federally required HPMS submission fields and official roadway inventory.

### E — Map and usability
- Route class legend, select segment on map or table, filters, hover details, bounded performance on mobile 390px, clear loading/error/empty states, accessible labels, reproducible synthetic seed, reset button, export current filtered/full data with clear wording.
- Add metadata/provenance panel indicating synthetic generation, CRS, route calibration, version and known limitations.

## Suggested FastAPI endpoints
GET /healthz; GET /api/v1/datasets; GET /api/v1/routes; GET /api/v1/segments?route_id=&class=; GET /api/v1/qa; GET /api/v1/reports/summary; GET /api/v1/exports/segments.geojson; GET /api/v1/exports/segments.csv; POST /api/v1/lrs/locate {route_id, milepoint}; POST /api/v1/lrs/project {route_id, lon, lat}. For demo edits use browser-local state unless authorization is implemented; never expose public writes to shared backend data.

## Mandatory acceptance checks
1. Initial dashboard loads offline-safe synthetic sample and displays the same IDs/metrics in map/table/QA.
2. Selecting a road in map/table opens same record; changing an inventory field recalculates completeness, QA and reports.
3. At least one seeded overlap and one missing required field produce exact expected QA rule codes; clean fixture has zero findings.
4. Boundary measure interpolation matches expected tolerance in projected units; inverse projection round-trip is accurate on test fixtures.
5. Correct CRS conversions; explicit warning against distance calculations on lon/lat degrees.
6. Downloaded GeoJSON parses to valid FeatureCollection; CSV parses and reflects edits; metadata carries synthetic disclaimer.
7. Automated backend tests, frontend typecheck/build and public demo smoke test pass with captured actual results. Responsive check at 390px.
8. All docs have real instructions, no invented benchmark numbers, fake deployment badges or unsupported government compliance claims.
9. On each phase produce `IMPLEMENTATION_REPORT.md` with changed files, commands executed, test result counts, unresolved issues, links only if actually deployed.

## Execution phases
Phase 0: inspect prototype, initialize clean git repo, README explaining purpose, boundaries and how to run.
Phase 1: backend data model, deterministic synthetic dataset, CRS-aware LRS algorithms and tests.
Phase 2: GeoJSON map React UI, filters, map/table synced selection, editing, QA, CSV and GeoJSON exports.
Phase 3: metadata/versioning, summary reports, documented API, regression and edge-case tests.
Phase 4: CI + public demo deployment if credentials already configured; otherwise provide exact manual deployment instructions without claiming success.

## Suggested project name and resume-safe claims
Name: `Transportation GIS & Roadway Analytics Lab`.
Only after actual implementation/testing, possible resume bullet: "Developed a reproducible transportation GIS pipeline with route-based linear referencing, roadway inventory validation, spatial visualization, and versioned GeoJSON/CSV reporting using Python, FastAPI, and React." Adapt claim strictly to observed completed scope.

## First Codex request
"Read CODEX_SPEC.md and prototype/index.html completely. Implement phases 0 and 1 first, including unit tests, while retaining all prototype interactions for future phases. Then proceed through phases 2–4 only if tests pass. Do not overwrite any existing repository. For each phase show evidence from actual command output; preserve honest technical limitations."
