# Transportation GIS & Roadway Analytics Lab

Independent transportation geospatial engineering project. All roadway records are synthetic, reproducible and released under CC0-1.0. The original standalone demo is available in [prototype/index.html](prototype/index.html). Its schematic coordinates are separate from the lab's WGS84 fixture.

[GitHub repository](https://github.com/hwen020/transportation-gis-lab) · [Live demo](https://transportation-gis-roadway-analytics-lab.onrender.com)

## Development

Use Python 3.12 and Node.js 20 or later. From the repository root:

```sh
python -m venv .venv
# Activate .venv before continuing
python -m pip install -r requirements.txt
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run build
python -m uvicorn lab.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` for the dashboard, `/prototype/` for the original demo, and `/docs` for OpenAPI. On Windows PowerShell, activate the environment with `./.venv/Scripts/Activate.ps1` or call its Python executable directly. To develop with Vite, start FastAPI on port 8000 and run `npm --prefix frontend run dev` in a second terminal.

## Data and methods

GeoPandas transforms route geometry from EPSG:4326 to NAD83 / UTM zone 12N (EPSG:26912). Shapely interpolates engineering milepoints by proportional projected distance within each calibrated segment. Converting a coordinate to a milepoint uses the closest projected point, with ties resolved by earliest calibrated component. Geometry lengths are in meters. Engineering milepoints are in miles. Never compute distance using longitude/latitude degrees.

- Eight synthetic segments across four routes are generated with seed `544926`. SQLite migration 1 seeds the clean and training fixtures by dataset version. The training fixture has a missing surface and same-route measure overlap.
- Line coordinates run in increasing measure direction. Multipart components follow their supplied order. Gaps between geometric components are never filled with artificial lines. At a shared measure, the earlier component wins. Calibration measure gaps and out-of-range values return 422 unless `clamp` is requested for values outside the full route range. Projection accuracy is intended for the regional study area.
- Preview edits and their audit trail live in page memory and clear on reload or reset. FastAPI recomputes a local copy of the fixture for each request. Editing inventory intervals changes QA and reporting. The LRS endpoints use a separate, fixed clean engineering calibration.
- CSV geometry uses a JSON-encoded GeoJSON geometry column. GeoJSON is RFC 7946 WGS84 (longitude, latitude). Both formats carry versioned segment records. GeoJSON and technical reports include dataset metadata. For CSV imports, provide metadata separately.
- Imports validate up to 250 synthetic segments. Missing segment IDs are derived from route, measure interval and canonical geometry. File-order geometry-derived stationing is opt-in for imports that omit both milepoints on all rows. It starts at zero per route and uses UTM projected centerline miles within the study region. It does not establish engineering control points or add imported routes to the fixed LRS.
- Completeness is the percent of seven core fields present. QA also validates values, geometry, ID uniqueness and measure continuity. When filtered, findings are evaluated on the full working fixture and included if they touch a visible segment. Summed segment miles double-count overlapping measures. Traffic bands use AADT counts. Summaries are **HPMS-style exploratory** and contain illustrative fields.
- The vector map renders from API GeoJSON and needs no online basemap. SVG display coordinates are only used for rendering. No ADOT roadway data, ArcGIS integration, or official FHWA submission is used.

## API

| Method and path | Purpose |
| --- | --- |
| GET `/healthz` | Deployment health check |
| GET `/api/v1/datasets`, `/api/v1/routes` | Provenance and route calibration ranges |
| GET `/api/v1/segments?fixture=clean&route_id=LAB-17&class=Interstate` | Filtered FeatureCollection |
| GET `/api/v1/qa?fixture=dirty`, `/api/v1/reports/summary` | Quality findings and aggregate metrics |
| GET `/api/v1/exports/segments.geojson`, `/api/v1/exports/segments.csv` | Seed downloads, clean by default |
| POST `/api/v1/preview` | Stateless edit, filter, audit, QA, summary and CSV |
| POST `/api/v1/inventory/validate` | Parse and validate an isolated GeoJSON or CSV import |
| POST `/api/v1/lrs/locate`, `/api/v1/lrs/project` | Convert a route milepoint and a WGS84 coordinate |

Example request body for `/api/v1/lrs/locate` is `{"route_id":"LAB-17","milepoint":1}`. For `/api/v1/lrs/project`, use `{"route_id":"LAB-17","lon":-112.2,"lat":33.44}`.

## Test and deploy

GitHub Actions runs backend pytest, frontend typecheck/build, a Playwright browser smoke test at 390px, and a Docker build and health check. It uploads JUnit test artifacts. To run locally after building with an activated Python environment:

```sh
cd frontend
npx playwright install chromium
npm test
```

For a published service, use the workflow's **Run workflow** action with `demo_url`, or set `LAB_BASE_URL` to the actual service URL and run the same Playwright test. Cold starts may take about a minute. Use the observed results in [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md).

1. Grant the Render GitHub App access to the dedicated private repository only. In the Render dashboard, select **New → Web Service** and connect that repository on branch `main`. [Render's Git provider setup](https://render.com/docs/git-provider)
2. Choose runtime **Docker**, Dockerfile path `./Dockerfile` and instance type **Free**. Under Advanced, set health check path to `/healthz`. Leave the root directory and Docker Command at their defaults. Alternatively, import `render.yaml` as a new Blueprint and ensure the service name is unused in the target workspace before applying.
3. Create the service and wait for the deploy to become Live. The Docker command binds to `0.0.0.0:$PORT`. Render provides the public URL, which requires no application login.
4. Verify the published URL with the Playwright workflow above. Render Free sleeps after 15 minutes of inactivity. Its filesystem is ephemeral, and the service recreates its fixed SQLite sample on startup. [Render Free documentation](https://render.com/docs/free)

## Résumé

> Developed a transportation GIS application using Python, FastAPI, GeoPandas, Shapely, React, and TypeScript. Implemented CRS-aware linear referencing, roadway inventory validation, auditable session edits, and versioned GeoJSON/CSV reporting on reproducible synthetic data.
