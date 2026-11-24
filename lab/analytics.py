import pandas as pd

from .data import META

REQUIRED = ("route_id", "from_measure_mi", "to_measure_mi", "functional_class", "lanes", "surface", "aadt")


def summarize(rows, findings):
    frame = pd.DataFrame(rows, columns=REQUIRED)
    start = pd.to_numeric(frame["from_measure_mi"], errors="coerce")
    end = pd.to_numeric(frame["to_measure_mi"], errors="coerce")
    frame["miles"] = (end - start).where((start >= 0) & (end > start), 0).fillna(0)
    traffic = pd.to_numeric(frame["aadt"], errors="coerce")
    frame["traffic_band"] = pd.cut(traffic, [-1, 9999, 49999, float("inf")],
                                   labels=["0–9,999", "10,000–49,999", "50,000+"]).astype(object)
    frame["mile_band"] = pd.cut(frame["miles"], [0, 2, 5, float("inf")], right=False,
                                labels=["0–<2 mi", "2–<5 mi", "5+ mi"]).astype(object)
    counts = {key: int(frame[key].replace("", None).notna().sum()) for key in REQUIRED}
    grouped = {}
    for column in ("route_id", "functional_class", "traffic_band", "mile_band"):
        grouped[column] = [
            dict(group=str(label), segments=int(len(group)), segment_miles=round(float(group["miles"].sum()), 6))
            for label, group in frame.groupby(frame[column].fillna("Unknown"), sort=True)
        ]
    return dict(
        title="HPMS-style exploratory summary", metadata=META, segment_count=len(rows),
        segment_miles=round(float(frame["miles"].sum()), 6),
        completeness_pct=round(100 * sum(counts.values()) / (len(rows) * len(REQUIRED)), 2) if rows else None,
        field_present=counts, groups=grouped, findings_count=len(findings),
        limitations="Completeness measures field presence. Overlapping intervals can inflate summed segment miles. "
                    "These fields are illustrative and do not establish official HPMS submission compliance.",
    )
