import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat
from shapely.errors import GEOSException

from .analytics import summarize
from .data import META, ROUTES
from .inventory import inspect, parse_inventory, serialize_csv, serialize_geojson
from .lrs import RouteLRS
from .store import samples

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = samples(Path(os.environ.get("LAB_DB", ROOT / "lab.sqlite3")))
LRS = {route["route_id"]: RouteLRS(row for row in FIXTURES["clean"] if row["route_id"] == route["route_id"])
       for route in ROUTES}
Fixture = Literal["clean", "dirty"]
app = FastAPI(title="Transportation GIS & Roadway Analytics Lab", version="1.0.0")
API = "/api/v1"


class Edit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_id: str
    functional_class: Literal["Interstate", "Principal arterial", "Minor arterial", "Collector"]
    lanes: int = Field(strict=True, ge=1, le=12)
    surface: Literal["Asphalt", "Concrete", "Gravel"]
    aadt: int = Field(strict=True, ge=0)
    from_measure_mi: FiniteFloat = Field(ge=0)
    to_measure_mi: FiniteFloat
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Preview(BaseModel):
    fixture: Fixture = "dirty"
    changes: list[Edit] = Field(default_factory=list, max_length=250)
    route_id: str | None = None
    functional_class: str | None = None


class Import(BaseModel):
    format: Literal["geojson", "csv"]
    body: str = Field(max_length=500_000)
    metadata: dict[str, str | int]
    derive_measures: bool = False


class Locate(BaseModel):
    route_id: str
    milepoint: FiniteFloat
    clamp: bool = False


class Project(BaseModel):
    route_id: str
    lon: FiniteFloat = Field(ge=-180, le=180)
    lat: FiniteFloat = Field(ge=-90, le=90)


def subset(rows, route_id=None, functional_class=None):
    return [row for row in rows if (not route_id or row["route_id"] == route_id)
            and (not functional_class or row["functional_class"] == functional_class)]


def bundle(rows, route_id=None, functional_class=None, audit=None, metadata=None):
    metadata = metadata or META
    findings = inspect(rows, metadata=metadata)
    visible = subset(rows, route_id, functional_class)
    ids = {row["segment_id"] for row in visible}
    scoped = [item for item in findings if not item["segment_ids"] or ids.intersection(item["segment_ids"])]
    return dict(segments=serialize_geojson(visible, metadata), qa=scoped,
                summary={**summarize(visible, scoped), "metadata": metadata}, audit=audit or [],
                csv=serialize_csv(visible))


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get(API + "/datasets")
def datasets():
    return [{**META, "synthetic_flag": True, "fixtures": list(FIXTURES)}]


@app.get(API + "/routes")
def routes():
    return [{**route, "geometry_length_m": LRS[route["route_id"]].length_m,
             "first_milepoint": LRS[route["route_id"]].legs[0].start,
             "last_milepoint": LRS[route["route_id"]].legs[-1].end} for route in ROUTES]


@app.get(API + "/segments")
def segments(fixture: Fixture = "dirty", route_id: str | None = None,
             functional_class: str | None = Query(None, alias="class")):
    return serialize_geojson(subset(FIXTURES[fixture], route_id, functional_class))


@app.get(API + "/qa")
def qa(fixture: Fixture = "dirty"):
    return inspect(FIXTURES[fixture])


@app.get(API + "/reports/summary")
def report(fixture: Fixture = "dirty"):
    rows = FIXTURES[fixture]
    return summarize(rows, inspect(rows))


@app.get(API + "/exports/segments.geojson")
def export_geojson(fixture: Fixture = "clean"):
    return Response(json.dumps(serialize_geojson(FIXTURES[fixture])), media_type="application/geo+json",
                    headers={"Content-Disposition": 'attachment; filename="synthetic-segments.geojson"'})


@app.get(API + "/exports/segments.csv")
def export_csv(fixture: Fixture = "clean"):
    return Response(serialize_csv(FIXTURES[fixture]), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="synthetic-segments.csv"'})


@app.post(API + "/preview")
def preview(payload: Preview):
    rows = {row["segment_id"]: row for row in FIXTURES[payload.fixture]}
    audit = []
    for change in payload.changes:
        before = rows.get(change.segment_id)
        if before is None or change.to_measure_mi <= change.from_measure_mi:
            raise HTTPException(422, "Expected a known segment and a positive measure interval")
        timestamp = change.timestamp.isoformat()
        after = {**before, **change.model_dump(exclude={"timestamp"}), "modified_at": timestamp}
        rows[change.segment_id] = after
        audit.append(dict(id=len(audit) + 1, segment_id=change.segment_id, before=before,
                          after=after, timestamp=timestamp, action="edit", actor="demo"))
    return bundle(list(rows.values()), payload.route_id, payload.functional_class, audit)


@app.post(API + "/inventory/validate")
def validate_inventory(payload: Import):
    try:
        rows = parse_inventory(payload.body, payload.format, payload.metadata, payload.derive_measures)
        metadata = {**payload.metadata, "calibration": (
            "Geometry-derived stationing in file order per route using EPSG:26912"
            if payload.derive_measures else "Inventory milepoints supplied by importer")}
        findings = inspect(rows, metadata=metadata)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, csv.Error, GEOSException) as exc:
        raise HTTPException(422, str(exc)) from exc
    if any(item["severity"] == "error" for item in findings):
        return {"qa": findings, "accepted": False}
    return {"accepted": True, **bundle(rows, metadata=metadata)}


def lrs_for(route_id):
    if route_id not in LRS:
        raise HTTPException(404, "Unknown calibrated route")
    return LRS[route_id]


@app.post(API + "/lrs/locate")
def locate(payload: Locate):
    try:
        return lrs_for(payload.route_id).locate(payload.milepoint, payload.clamp)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post(API + "/lrs/project")
def project(payload: Project):
    try:
        return lrs_for(payload.route_id).project(payload.lon, payload.lat)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


app.mount("/prototype", StaticFiles(directory=ROOT / "prototype", html=True), name="prototype")
if (ROOT / "frontend" / "dist").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="dashboard")
