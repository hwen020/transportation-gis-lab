import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from lab.api import app
from lab.data import META, fixtures
from lab.inventory import inspect, parse_inventory, serialize_geojson
from lab.store import samples

client = TestClient(app)


def test_exact_fixture_findings():
    assert inspect(fixtures()) == []
    assert [(item["rule_code"], item["segment_ids"]) for item in inspect(fixtures(True))] == [
        ("MISSING_ATTRIBUTE", ["SEG-007"]), ("LRS_OVERLAP", ["SEG-002", "SEG-003"]),
    ]
    assert fixtures() == fixtures()


def test_required_qa_rules():
    rows = fixtures()
    rows[1]["from_measure_mi"] += .1
    rows[4].update(lanes=0, aadt=-1, geometry={"type": "LineString", "coordinates": []},
                   functional_class="Unknown", segment_id=rows[3]["segment_id"])
    rows[6]["to_measure_mi"] = rows[6]["from_measure_mi"]
    assert {item["rule_code"] for item in inspect(rows, crs="EPSG:26912")} >= {
        "LRS_GAP", "DUPLICATE_ID", "INVALID_LANES", "INVALID_AADT", "INVALID_GEOMETRY",
        "INVALID_CLASS", "INVALID_INTERVAL", "BAD_CRS",
    }


def test_sqlite_migration_seed_is_repeatable(tmp_path):
    path = tmp_path / "seed.sqlite3"
    assert samples(path) == samples(path) == {"clean": fixtures(), "dirty": fixtures(True)}


@pytest.mark.parametrize("fmt", ["csv", "geojson"])
def test_export_import_roundtrip(fmt):
    response = client.get(f"/api/v1/exports/segments.{fmt}")
    assert response.status_code == 200
    records = parse_inventory(response.text, fmt, META)
    assert records == fixtures()
    result = client.post("/api/v1/inventory/validate", json={"format": fmt, "body": response.text, "metadata": META})
    assert result.json()["accepted"]
    assert result.json()["segments"]["metadata"]["source"] == META["source"]


def test_stable_import_identifiers():
    collection = serialize_geojson(fixtures())
    for feature in collection["features"]:
        del feature["id"]
        del feature["properties"]["segment_id"]
    body = json.dumps(collection)
    one = parse_inventory(body, "geojson", META)
    two = parse_inventory(body, "geojson", META)
    assert one == two
    assert len({row["segment_id"] for row in one}) == 8


def test_explicit_geometry_derived_stationing():
    collection = serialize_geojson(fixtures()[:2])
    for feature in collection["features"]:
        del feature["properties"]["from_measure_mi"]
        del feature["properties"]["to_measure_mi"]
    body = json.dumps(collection)
    result = client.post("/api/v1/inventory/validate", json={
        "format": "geojson", "body": body, "metadata": META, "derive_measures": True,
    }).json()
    assert result["accepted"]
    assert result["qa"] == []
    first, second = [feature["properties"] for feature in result["segments"]["features"]]
    assert first["from_measure_mi"] == 0
    assert 3 < first["to_measure_mi"] < 4
    assert second["from_measure_mi"] == first["to_measure_mi"]


def test_preview_updates_summary_qa_audit_and_exports_without_shared_writes():
    base = client.post("/api/v1/preview", json={}).json()
    old = next(feature["properties"] for feature in base["segments"]["features"] if feature["id"] == "SEG-007")
    edit = {key: old[key] for key in ("segment_id", "from_measure_mi", "to_measure_mi", "functional_class", "aadt", "lanes")}
    edit.update(surface="Asphalt", lanes=3, timestamp="2026-11-23T12:00:00Z")
    response = client.post("/api/v1/preview", json={"changes": [edit], "route_id": "LAB-87"})
    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["completeness_pct"] == 100
    assert result["qa"] == []
    assert result["audit"][0]["before"]["surface"] is None
    assert result["audit"][0]["after"]["surface"] == "Asphalt"
    assert list(csv.DictReader(io.StringIO(result["csv"])))[-1]["lanes"] == "3"
    assert result["segments"]["features"][-1]["properties"]["lanes"] == 3
    assert client.get("/api/v1/qa").json() == base["qa"]
    assert client.post("/api/v1/preview", json={"changes": [{**edit, "lanes": 99}]}).status_code == 422


def test_health_lrs_and_filter_contract():
    assert client.get("/healthz").json() == {"status": "ok"}
    assert len(client.get("/api/v1/segments", params={"class": "Interstate"}).json()["features"]) == 3
    result = client.post("/api/v1/lrs/locate", json={"route_id": "LAB-17", "milepoint": 1}).json()
    inverse = client.post("/api/v1/lrs/project", json={"route_id": "LAB-17", "lon": result["lon"], "lat": result["lat"]}).json()
    assert inverse["milepoint"] == pytest.approx(1, abs=1e-7)
    assert client.post("/api/v1/lrs/locate", json={"route_id": "LAB-17", "milepoint": 999}).status_code == 422
    assert client.get("/prototype/").status_code == 200
