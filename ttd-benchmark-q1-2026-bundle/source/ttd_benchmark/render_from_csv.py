"""Render TTD benchmark HTMLs sourced directly from Fiducia's two quartile
CSVs — NoTTD (industry distribution) and TTD_Only (TTD's own values).

Advantage over the previous pipeline: no formula implementation on our side.
Both `global` (aggregate across marketers) and `q2` (median) come straight
from Fiducia's pre-computed output, so every value on the page matches the
platform by construction.

Inputs:
  data/ana_quartiles_NoTTD-6.csv          — industry distribution (excludes TTD)
  data/input/ana_quartiles_TTD_Only.csv   — TTD-only (same schema, different
                                            segment numbering, 8 TTD tenants)

Outputs (3 view variants):
  data/output/ttdonly-benchmark-2026q1/ttd_benchmark_q1_2026.html
  data/output/ttdonly-benchmark-2026q1/ttd_benchmark_q1_2026_median.html
  data/output/ttdonly-benchmark-2026q1/ttd_benchmark_q1_2026_aggregate.html
"""
from __future__ import annotations

import base64
import csv
import json
from pathlib import Path

from ttd_benchmark.render import HTML_TEMPLATE, SECTIONS
from ttd_benchmark.segments import segment_label

ROOT = Path("/Users/igor/dev/fiducia-data-works")
NOTTD_CSV = ROOT / "data" / "ana_quartiles_NoTTD-6.csv"
TTD_CSV   = ROOT / "data" / "input" / "ana_quartiles_TTD_Only.csv"
OUT_DIR   = ROOT / "data" / "output" / "ttdonly-benchmark-2026q1"
LOGO_PATH = ROOT / "data" / "assets" / "fiducia_logo.png"

# TTD_Only CSV per-tenant columns (8 TTD marketers for Q1 2026).
TTD_TENANTS = ["bayer", "dell", "gm", "hershey", "hp", "jnj", "kcc", "popeyes"]

# UI filter layout — same as the live Fiducia page.
PLATFORMS = [
    ("all",          "All platforms"),
    ("programmatic", "Programmatic"),
]
ENVIRONMENTS = [
    ("all",           "All environments"),
    ("web",           "Web"),
    ("ctv",           "CTV"),
    ("mobile_in_app", "Mobile In-App"),
    ("other",         "Other"),
    ("web_and_app",   "Web + Mobile In-App"),
]
MARKETPLACES = [
    ("all",  "All marketplaces"),
    ("pmp",  "Private Marketplace"),
    ("open", "Open Market"),
]

# UI value → raw CSV-cell form for each column of the 4-tuple
# (key_inventory_type_common, inventory_category, has_deal, key_dsp_name).
_PLATFORM_DSP = {"all": "[]", "programmatic": "[$Programmatic$]"}
_ENV_CAT = {
    "all":           "[]",
    "web":           "[Web]",
    "ctv":           "[CTV]",
    "mobile_in_app": "[Mobile In-App]",
    "other":         "[Other]",
    "web_and_app":   "[$WebAndMobileInApp$]",
}
_MKT_DEAL = {"all": "[]", "open": "[false]", "pmp": "[true]"}


def _logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    with LOGO_PATH.open("rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


# ---------------------------------------------------------------------------
# CSV parsing

def _load(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _seg_tuple(row: dict) -> tuple[str, str, str, str]:
    return (row["key_inventory_type_common"], row["inventory_category"],
            row["has_deal"], row["key_dsp_name"])


def _index(rows: list[dict]) -> dict[tuple, dict]:
    """Group CSV rows by segment tuple → {group_num, metrics: {metric → row}}."""
    out: dict[tuple, dict] = {}
    for r in rows:
        t = _seg_tuple(r)
        seg = out.setdefault(t, {"group_num": r["group_num"], "metrics": {}})
        seg["metrics"][r["metric_name"]] = r
    return out


def _float(v) -> float | None:
    """Parse a numeric CSV cell, returning None for blank / NaN / [!] outliers
    in the distribution columns (min/max/q1-q3/global)."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    if s.startswith("[!]"):
        s = s[3:].strip()
    try:
        return float(s)
    except ValueError:
        return None


def _tenant_val(raw: str | None) -> tuple[float | None, bool]:
    """Parse a tenant-column cell: (value_or_None, is_outlier).

    Outliers ([!] prefix) are treated as "excluded from the distribution" —
    the tenant had data but was flagged as an outlier.
    """
    if raw is None:
        return None, False
    s = raw.strip()
    if not s or s.lower() == "nan":
        return None, False
    outlier = s.startswith("[!]")
    if outlier:
        s = s[3:].strip()
    if s.lower() == "nan":
        return None, outlier
    try:
        return float(s), outlier
    except ValueError:
        return None, outlier


def _qualified_tenants(ttd_metric_row: dict) -> tuple[list[str], list[str]]:
    """For a TTD CSV row, split the 8 tenants into used / excluded."""
    used, excl = [], []
    for tenant in TTD_TENANTS:
        v, outlier = _tenant_val(ttd_metric_row.get(tenant))
        if v is None or outlier:
            excl.append(tenant)
        else:
            used.append(tenant)
    return used, excl


# ---------------------------------------------------------------------------
# Payload assembly

def build_payload() -> dict:
    nottd_idx = _index(_load(NOTTD_CSV))
    ttd_idx   = _index(_load(TTD_CSV))

    segs: list[dict] = []
    dist: dict[str, dict] = {}
    ttd_raw: dict[str, dict] = {}
    ttd_median: dict[str, dict] = {}
    ttd_aggregate: dict[str, dict] = {}

    # Key = TTD CSV's group_num (stable identifier for this payload).
    for tup, ttd_seg in ttd_idx.items():
        seg_id = ttd_seg["group_num"]
        segs.append({
            "group_num": seg_id,
            "label": segment_label(*tup),
        })

        # Distribution from the NoTTD CSV matched on segment tuple.
        nottd_seg = nottd_idx.get(tup)
        dist_row: dict[str, dict] = {}
        if nottd_seg:
            for mname, r in nottd_seg["metrics"].items():
                dist_row[mname] = {
                    "min":    _float(r.get("min")),
                    "q1":     _float(r.get("q1")),
                    "q2":     _float(r.get("q2")),
                    "q3":     _float(r.get("q3")),
                    "max":    _float(r.get("max")),
                    "avg":    _float(r.get("avg")),
                    "global": _float(r.get("global")),
                }
        dist[seg_id] = dist_row

        # TTD values come straight from the TTD_Only CSV.
        raw_row: dict[str, float | None] = {}
        med_row: dict[str, dict] = {}
        agg_row: dict[str, dict] = {}
        for mname, r in ttd_seg["metrics"].items():
            used, excl = _qualified_tenants(r)
            predicate = r.get("metric_predicate", "") or ""
            # Aggregate = Fiducia `global` column (sum / weighted aggregate
            # across the qualifying TTD marketers for this metric × segment).
            g = _float(r.get("global"))
            # Median = Fiducia `q2` (median across qualifying TTD marketers).
            q2 = _float(r.get("q2"))
            raw_row[mname] = g
            agg_row[mname] = {"value": g,  "used": used, "excluded": excl, "predicate": predicate}
            med_row[mname] = {"value": q2, "used": used, "excluded": excl, "predicate": predicate}
        ttd_raw[seg_id] = raw_row
        ttd_aggregate[seg_id] = agg_row
        ttd_median[seg_id] = med_row

    # Build UI filter matrix: (platform, env, marketplace) → TTD group_num.
    # The filter combos only vary three of the four tuple dimensions
    # (inv_type is always "[]" here — per-inv_type breakdowns aren't exposed
    # in the top filter bar, same as the live Fiducia /industry-benchmarks).
    matrix: dict[str, str] = {}
    for p_ui, p_cell in _PLATFORM_DSP.items():
        for e_ui, e_cell in _ENV_CAT.items():
            for m_ui, m_cell in _MKT_DEAL.items():
                tup = ("[]", e_cell, m_cell, p_cell)
                seg = ttd_idx.get(tup)
                if seg:
                    matrix[f"{p_ui}|{e_ui}|{m_ui}"] = seg["group_num"]

    sections_json = [{
        "name": name,
        "metrics": [{
            "name": m[0], "label": m[1], "fmt": m[2],
            "lower_is_better": m[3], "true_badge": m[4], "indent": m[5],
        } for m in metrics],
    } for name, metrics in SECTIONS]

    return {
        "segments": segs,
        "ttd_raw": ttd_raw,
        "ttd_median": ttd_median,
        "ttd_aggregate": ttd_aggregate,
        "dist": dist,
        "sections": sections_json,
        "filters": {
            "platforms":    PLATFORMS,
            "environments": ENVIRONMENTS,
            "marketplaces": MARKETPLACES,
            "matrix":       matrix,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    payload_js = json.dumps(payload, default=str)
    logo_uri = _logo_data_uri()

    outputs = [
        ("combined",  OUT_DIR / "ttd_benchmark_q1_2026.html"),
        ("median",    OUT_DIR / "ttd_benchmark_q1_2026_median.html"),
        ("aggregate", OUT_DIR / "ttd_benchmark_q1_2026_aggregate.html"),
    ]
    for view, path in outputs:
        html = (HTML_TEMPLATE
                .replace("__DATA_JSON__", payload_js)
                .replace("__VIEW__", view)
                .replace("__LOGO_SRC__", logo_uri))
        path.write_text(html)
        print(f"Wrote {path} ({path.stat().st_size / 1024:.1f} KB) [view={view}]")


if __name__ == "__main__":
    main()
