import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime
from math import isfinite

from pydantic import ValidationError
from shapely.errors import GEOSException
from shapely.ops import transform

from .data import META
from .lrs import EPS_MI, TO_METRIC, route_geometry
from .models import Segment

RULES = {
    "segment_id": "MISSING_ATTRIBUTE", "route_id": "MISSING_ATTRIBUTE",
    "geometry": "INVALID_GEOMETRY", "functional_class": "INVALID_CLASS",
    "lanes": "INVALID_LANES", "surface": "INVALID_SURFACE", "aadt": "INVALID_AADT",
    "from_measure_mi": "INVALID_INTERVAL", "to_measure_mi": "INVALID_INTERVAL",
}


def inspect(rows, crs="EPSG:4326", continuity=True, metadata=META):
    findings = []
    groups = defaultdict(list)
    counts = Counter(row.get("segment_id") for row in rows)

    def add(code, ids, message, severity="error"):
        ids = list(ids)
        key = json.dumps([metadata["dataset_version"], code, ids, message])
        findings.append(dict(id=hashlib.sha256(key.encode()).hexdigest()[:16],
                             dataset_version=metadata["dataset_version"], segment_ids=ids,
                             rule_code=code, severity=severity, details=message,
                             created_at=metadata["generated_at"]))

    if crs != "EPSG:4326":
        add("BAD_CRS", [], "Expected EPSG:4326 with longitude first")
    for identity, count in counts.items():
        if identity and count > 1:
            add("DUPLICATE_ID", [identity], f"ID occurs {count} times")
    for row in rows:
        identity = row.get("segment_id") or "(unassigned)"
        try:
            Segment.model_validate(row)
        except ValidationError as exc:
            for error in exc.errors(include_input=False, include_url=False):
                field = error["loc"][0] if error["loc"] else "from_measure_mi"
                code = RULES.get(field, "INVALID_METADATA")
                if row.get(field) in (None, ""):
                    code = "MISSING_ATTRIBUTE"
                add(code, [identity], f"{field}: {error['msg']}")
        if row.get("geometry") is not None:
            try:
                route_geometry(row["geometry"])
            except (GEOSException, KeyError, TypeError, ValueError, IndexError):
                add("INVALID_GEOMETRY", [identity], "Expected a valid nonzero WGS84 line")
        start, end = row.get("from_measure_mi"), row.get("to_measure_mi")
        if all(type(value) in (int, float) and isfinite(value) for value in (start, end)) and 0 <= start < end:
            groups[row.get("route_id")].append((start, end, identity))
    for route, intervals in groups.items():
        active = []
        for start, end, identity in sorted(intervals):
            if continuity and active and start > max(item[0] for item in active) + EPS_MI:
                prior_end, prior_id = max(active)
                add("LRS_GAP", [prior_id, identity], f"{route}: {prior_end:g} to {start:g} mi", "warning")
            active = [(last, other) for last, other in active if last > start + EPS_MI]
            for last, other in active:
                add("LRS_OVERLAP", [other, identity], f"{route}: {start:g} to {min(last, end):g} mi")
            active.append((end, identity))
    return findings


def serialize_geojson(rows, metadata=META):
    return {"type": "FeatureCollection", "metadata": metadata, "features": [
        {"type": "Feature", "id": row["segment_id"], "geometry": row["geometry"],
         "properties": {key: value for key, value in row.items() if key != "geometry"}}
        for row in rows
    ]}


def serialize_csv(rows, fields=None):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields or list(Segment.model_fields))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list))
                         else value for key, value in row.items()})
    return output.getvalue()


def parse_inventory(body, format, metadata, derive_measures=False):
    for key in ("dataset_version", "source", "license", "schema_version", "generated_at", "coordinate_reference_system"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"Missing dataset metadata: {key}")
    if metadata["coordinate_reference_system"] != "EPSG:4326":
        raise ValueError("Imports must use EPSG:4326 longitude/latitude")
    if datetime.fromisoformat(metadata["generated_at"]).tzinfo is None:
        raise ValueError("Dataset generated_at must include a time zone")
    if format == "geojson":
        collection = json.loads(body)
        if collection["type"] != "FeatureCollection" or "crs" in collection or not isinstance(collection["features"], list):
            raise ValueError("Expected RFC 7946 FeatureCollection")
        rows = []
        for feature in collection["features"]:
            if feature["type"] != "Feature":
                raise ValueError("Expected a GeoJSON Feature")
            row = {**feature["properties"], "geometry": feature["geometry"]}
            if feature.get("id") and row.get("segment_id") and feature["id"] != row["segment_id"]:
                raise ValueError("Feature ID differs from segment ID")
            if feature.get("id"):
                row.setdefault("segment_id", str(feature["id"]))
            rows.append(row)
    elif format == "csv":
        reader = csv.DictReader(io.StringIO(body), strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Expected unique CSV column names")
        rows = list(reader)
        for row in rows:
            for key in ("from_measure_mi", "to_measure_mi"):
                row[key] = float(row[key]) if row.get(key) else None
            for key in ("lanes", "aadt"):
                row[key] = int(row[key]) if row.get(key) else None
            row["geometry"] = json.loads(row["geometry"])
    else:
        raise ValueError("Expected csv or geojson")
    if not 1 <= len(rows) <= 250:
        raise ValueError("Expected between 1 and 250 segments")
    if derive_measures:
        if any(row.get(key) is not None for row in rows for key in ("from_measure_mi", "to_measure_mi")):
            raise ValueError("For geometry-derived intervals, omit both measures from all records")
        offsets = defaultdict(float)
        for row in rows:
            route = row["route_id"]
            line = route_geometry(row["geometry"])
            bounds = line.bounds
            if not (-114 <= bounds[0] <= bounds[2] <= -108 and 31 <= bounds[1] <= bounds[3] <= 38):
                raise ValueError("Geometry-derived measures are limited to the regional UTM study area")
            meters = transform(TO_METRIC.transform, line).length
            row["from_measure_mi"] = offsets[route]
            offsets[route] += meters / 1609.344
            row["to_measure_mi"] = offsets[route]
    for row in rows:
        if not row.get("segment_id"):
            identity = json.dumps([row.get(key) for key in
                                   ("route_id", "from_measure_mi", "to_measure_mi", "geometry")], sort_keys=True)
            row["segment_id"] = "SEG-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        row.setdefault("dataset_version", metadata["dataset_version"])
        if row["dataset_version"] != metadata["dataset_version"]:
            raise ValueError("Segment dataset version mismatch")
    return rows
