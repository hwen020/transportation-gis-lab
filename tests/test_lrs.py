from copy import deepcopy

import pytest

from lab.data import fixtures
from lab.lrs import RouteLRS


def records():
    return [row for row in fixtures() if row["route_id"] == "LAB-17"]


def test_boundaries_and_metric_units():
    rows = records()
    route = RouteLRS(reversed(rows))
    first = route.locate(0)
    last = route.locate(rows[-1]["to_measure_mi"])
    assert [first["lon"], first["lat"]] == pytest.approx(rows[0]["geometry"]["coordinates"][0], abs=1e-8)
    assert last["along_geometry_m"] == pytest.approx(route.length_m, abs=1e-6)
    assert 16000 < route.length_m < 19000
    assert route.locate(-1, clamp=True) == first
    assert route.locate(-1e-10) == first
    with pytest.raises(ValueError):
        route.locate(-1)


@pytest.mark.parametrize("m", [0, 1, 3.75, 6, 8])
def test_inverse_roundtrip(m):
    route = RouteLRS(records())
    point = route.locate(m)
    inverse = route.project(point["lon"], point["lat"])
    assert inverse["milepoint"] == pytest.approx(m, abs=1e-7)
    assert inverse["offset_m"] < 1e-5


@pytest.mark.parametrize("problem", ["reversed", "duplicate", "overlap", "zero"])
def test_invalid_calibration(problem):
    rows = records()
    if problem == "reversed":
        rows[0]["from_measure_mi"] = rows[0]["to_measure_mi"] + 1
    elif problem == "duplicate":
        rows[1]["from_measure_mi"] = rows[0]["from_measure_mi"]
    elif problem == "overlap":
        rows[1]["from_measure_mi"] -= .2
    else:
        rows[0]["geometry"]["coordinates"] = [rows[0]["geometry"]["coordinates"][0]] * 2
    with pytest.raises(ValueError):
        RouteLRS(rows)


def test_gaps_and_multipart_are_not_bridged():
    rows = deepcopy(records())
    boundary = rows[1]["from_measure_mi"]
    rows[1]["from_measure_mi"] += .1
    with pytest.raises(ValueError, match="gap"):
        RouteLRS(rows).locate(boundary + .05)
    first = rows[0]
    line = first["geometry"]["coordinates"]
    first["geometry"] = {"type": "MultiLineString", "coordinates": [line[:2], rows[1]["geometry"]["coordinates"]]}
    route = RouteLRS([first])
    tie = route.locate(route.legs[0].end)
    assert [tie["lon"], tie["lat"]] == pytest.approx(line[1], abs=1e-8)
