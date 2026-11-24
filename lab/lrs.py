from dataclasses import dataclass
from math import isfinite

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import LineString, Point, shape
from shapely.ops import transform

TO_METRIC = Transformer.from_crs(4326, 26912, always_xy=True)
TO_WGS84 = Transformer.from_crs(26912, 4326, always_xy=True)
EPS_MI = 1e-8
EPS_M = 1e-6


def route_geometry(value):
    if value["type"] not in {"LineString", "MultiLineString"}:
        raise ValueError("Expected a line geometry")
    geometry = shape(value)
    parts = (geometry,) if geometry.geom_type == "LineString" else geometry.geoms
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("Invalid or empty line geometry")
    for part in parts:
        if part.is_empty or len(set(part.coords)) < 2:
            raise ValueError("Zero-length line component")
        for coordinate in part.coords:
            if len(coordinate) != 2 or not all(isfinite(v) for v in coordinate):
                raise ValueError("Expected finite 2D coordinates")
            if not (-180 <= coordinate[0] <= 180 and -90 <= coordinate[1] <= 90):
                raise ValueError("Coordinates are outside WGS84 bounds")
    return geometry


@dataclass(frozen=True)
class Leg:
    start: float
    end: float
    line: LineString
    offset_m: float


class RouteLRS:
    def __init__(self, records):
        records = list(records)
        if not records:
            raise ValueError("Empty calibration")
        for record in records:
            start, end = record["from_measure_mi"], record["to_measure_mi"]
            if not (isfinite(start) and isfinite(end) and 0 <= start < end):
                raise ValueError("Invalid calibration interval")
        records.sort(key=lambda row: row["from_measure_mi"])
        metric = gpd.GeoSeries([route_geometry(row["geometry"]) for row in records],
                               crs=4326).to_crs(26912)
        self.legs = []
        previous_end = None
        offset = 0.0
        for record, geometry in zip(records, metric):
            start, end = record["from_measure_mi"], record["to_measure_mi"]
            if previous_end is not None and start < previous_end - EPS_MI:
                raise ValueError("Overlapping calibration intervals")
            previous_end = end
            parts = [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms)
            lengths = [part.length for part in parts]
            if any(not isfinite(length) or length <= EPS_M for length in lengths):
                raise ValueError("Zero-length or non-finite projected component")
            total = sum(lengths)
            local = 0.0
            for part, length in zip(parts, lengths):
                first = start + (end - start) * local / total
                local += length
                last = start + (end - start) * local / total
                self.legs.append(Leg(first, last, part, offset))
                offset += length
        self.length_m = offset

    def locate(self, measure, clamp=False):
        if not isfinite(measure):
            raise ValueError("Expected a finite milepoint")
        if clamp:
            measure = min(max(measure, self.legs[0].start), self.legs[-1].end)
        for leg in self.legs:
            if leg.start - EPS_MI <= measure <= leg.end + EPS_MI:
                measure = min(max(measure, leg.start), leg.end)
                distance = (measure - leg.start) / (leg.end - leg.start) * leg.line.length
                return self._result(leg, distance, measure)
        raise ValueError("Milepoint outside calibration or in a measure gap")

    def project(self, lon, lat):
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Coordinates are outside WGS84 bounds")
        point = transform(TO_METRIC.transform, Point(lon, lat))
        if point.is_empty or not point.is_valid:
            raise ValueError("Coordinate cannot be projected")
        best = None
        for leg in self.legs:
            along = leg.line.project(point)
            distance = point.distance(leg.line.interpolate(along))
            if best is None or distance < best[0] - EPS_M:
                best = distance, leg, along
        distance, leg, along = best
        measure = leg.start + (leg.end - leg.start) * along / leg.line.length
        return {**self._result(leg, along, measure), "offset_m": distance}

    def _result(self, leg, along, measure):
        point = transform(TO_WGS84.transform, leg.line.interpolate(along))
        return dict(milepoint=measure, lon=point.x, lat=point.y,
                    along_geometry_m=leg.offset_m + along, route_geometry_m=self.length_m)
