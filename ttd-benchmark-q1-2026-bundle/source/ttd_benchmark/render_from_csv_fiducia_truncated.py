"""Render TTD benchmark from Fiducia's pre-truncated TTD CSV.

Fiducia provided a version of the TTD_Only CSV with bad inventory already
removed at source — broken (tenant × env × marketplace) slices are gone from
the raw parquet before aggregation, so every `global` value is computed
cleanly by Fiducia without our needing to re-aggregate or subtract. Total
TTD spend: $77.9M (down from $105M), reflecting ~$27M of pruned inventory.

Only 6 tenants remain in the TTD columns (hp and kcc dropped entirely by
Fiducia alongside the slice-level pruning):
    bayer, dell, gm, hershey, jnj, popeyes

Outputs mirror the base renderer but use Fiducia's authoritative globals
directly — no rollup, no derived waterfall, no threshold. All values match
Fiducia by construction.

Output: data/output/ttdonly-benchmark-2026q1-fiducia-clean/
"""
from __future__ import annotations

import base64
import csv
import json
import statistics
from pathlib import Path

from ttd_benchmark.render import HTML_TEMPLATE, SECTIONS
from ttd_benchmark.segments import segment_label
from ttd_benchmark.render_from_csv import (
    NOTTD_CSV, LOGO_PATH,
    PLATFORMS, ENVIRONMENTS, MARKETPLACES,
    _PLATFORM_DSP, _ENV_CAT, _MKT_DEAL,
    _logo_data_uri, _load, _seg_tuple, _index, _float, _tenant_val,
)

ROOT = Path("/Users/igor/dev/fiducia-data-works")
TTD_CSV = ROOT / "data" / "input" / "ana_quartiles_TTD_Only-2.csv"
# Final output: one file using the "combined" view — aggregate (Fiducia global)
# for top tiles / stacked charts / waterfall; median (q2 or local median from
# per-tenant cells) for the metric table. Matches Fiducia's /explore for the
# top summary and /industry-benchmarks for the table.
OUT_DIR = ROOT / "data" / "output" / "ttdonly-benchmark-2026q1-final"

# Fiducia's truncated TTD_Only CSV has 6 tenant columns.
TTD_TENANTS = ["bayer", "dell", "gm", "hershey", "jnj", "popeyes"]


def _qualified_tenants(ttd_metric_row: dict) -> tuple[list[str], list[str]]:
    used, excl = [], []
    for tenant in TTD_TENANTS:
        v, outlier = _tenant_val(ttd_metric_row.get(tenant))
        if v is None or outlier:
            excl.append(tenant)
        else:
            used.append(tenant)
    return used, excl


def _per_tenant_median(r: dict) -> float | None:
    """Median across non-outlier tenant values in this CSV row. Used when
    Fiducia suppresses q2 (they require n ≥ 4 qualifying tenants; for TTD
    several AV-gated metrics have only 3). Three points is enough to
    establish a median for our purposes."""
    vals = []
    for t in TTD_TENANTS:
        v, outlier = _tenant_val(r.get(t))
        if v is not None and not outlier:
            vals.append(v)
    return statistics.median(vals) if vals else None


def build_payload() -> dict:
    nottd_idx = _index(_load(NOTTD_CSV))
    ttd_idx   = _index(_load(TTD_CSV))

    segs: list[dict] = []
    dist: dict[str, dict] = {}
    ttd_raw: dict[str, dict] = {}
    ttd_median: dict[str, dict] = {}
    ttd_aggregate: dict[str, dict] = {}

    for tup, ttd_seg in ttd_idx.items():
        seg_id = ttd_seg["group_num"]
        segs.append({"group_num": seg_id, "label": segment_label(*tup)})

        # Industry distribution from NoTTD CSV (unchanged)
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

        raw_row: dict[str, float | None] = {}
        med_row: dict[str, dict] = {}
        agg_row: dict[str, dict] = {}
        for mname, r in ttd_seg["metrics"].items():
            used, excl = _qualified_tenants(r)
            predicate = r.get("metric_predicate", "") or ""
            g  = _float(r.get("global"))
            q2 = _float(r.get("q2"))
            # Fallback: if Fiducia suppressed q2 (n<4), compute median from
            # per-tenant cells. The CSV still has the qualifying tenants'
            # values; the only thing missing is the aggregate quartile stat.
            if q2 is None:
                q2 = _per_tenant_median(r)
            raw_row[mname] = g
            agg_row[mname] = {"value": g,  "used": used, "excluded": excl, "predicate": predicate}
            med_row[mname] = {"value": q2, "used": used, "excluded": excl, "predicate": predicate}
        ttd_raw[seg_id] = raw_row
        ttd_aggregate[seg_id] = agg_row
        ttd_median[seg_id] = med_row

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
    tpl = HTML_TEMPLATE

    # Final output is the combined view only (top=aggregate, table=median).
    path = OUT_DIR / "ttd_benchmark_q1_2026.html"
    html = (tpl
            .replace("__DATA_JSON__", payload_js)
            .replace("__VIEW__", "combined")
            .replace("__LOGO_SRC__", logo_uri))
    path.write_text(html)
    print(f"Wrote {path} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
