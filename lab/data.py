from copy import deepcopy
from random import Random

SEED = 544926
VERSION = "synthetic-1"
CLASSES = ("Interstate", "Principal arterial", "Minor arterial", "Collector")
SURFACES = ("Asphalt", "Concrete", "Gravel")
META = {
    "dataset_version": VERSION, "generator_seed": SEED,
    "coordinate_reference_system": "EPSG:4326", "analysis_crs": "EPSG:26912",
    "source": "Deterministic synthetic Arizona-like roadway fixture",
    "license": "CC0-1.0", "schema_version": "1.0",
    "generated_at": "2026-11-23T00:00:00Z",
    "calibration": "Piecewise engineering milepoints with projected metric interpolation",
    "limitations": "Synthetic data. Distances are never calculated in longitude/latitude degrees. HPMS-style exploratory summary. No official integration.",
}

NETWORK = {
    "LAB-17": ([-112.20, 33.44], [(-0.01, .053), (.015, .050), (.024, .045)]),
    "LAB-60": ([-112.34, 33.49], [( .09, -.018), (.11, .012)]),
    "LAB-87": ([-112.07, 33.43], [(.018, .065), (.05, .06)]),
    "LAB-202": ([-112.26, 33.59], [(.18, -.025)]),
}


def fixtures(dirty=False):
    rng = Random(SEED)
    records = []
    for route_index, (route_id, (start, offsets)) in enumerate(NETWORK.items()):
        measure = 1.0 if route_index == 3 else 0.0
        for dx, dy in offsets:
            end = [round(start[0] + dx, 6), round(start[1] + dy, 6)]
            middle = [round(start[0] + dx * .55 + .004, 6), round(start[1] + dy * .50, 6)]
            next_measure = round(measure + rng.randint(27, 57) / 10, 2)
            records.append(dict(
                segment_id=f"SEG-{len(records)+1:03}", route_id=route_id,
                from_measure_mi=measure, to_measure_mi=next_measure,
                geometry={"type": "LineString", "coordinates": [start, middle, end]},
                functional_class=CLASSES[route_index], lanes=4 if route_index < 2 else 2,
                surface="Concrete" if route_index == 0 else "Asphalt",
                aadt=rng.randint(4000, 105000), effective_date="2026-11-23",
                modified_at=META["generated_at"], dataset_version=VERSION,
            ))
            start, measure = end, next_measure
    if dirty:
        records[2]["from_measure_mi"] -= .1
        records[6]["surface"] = None
    return deepcopy(records)


ROUTES = [
    dict(route_id=route_id, display_name=route_id, jurisdiction="Synthetic study area",
         crs="EPSG:4326", source=META["source"], source_license=META["license"],
         synthetic_flag=True, dataset_version=VERSION, continuity_expected=True)
    for route_id in NETWORK
]
