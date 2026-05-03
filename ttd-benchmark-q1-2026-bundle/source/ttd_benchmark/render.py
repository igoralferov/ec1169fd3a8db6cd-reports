"""Render static HTML reports styled after Fiducia's Industry Benchmarks UI.

Two reports (one per TTD statistic view): median and aggregate.

Visual reference: https://ana.fiduciadlt.com/industry-benchmarks
                 https://ana.fiduciadlt.com/explore

Key design elements pulled verbatim from the live site:
  - Fiducia quartile palette:
      #55B376 green, #C4C745 lime, #F2C05F yellow, #E36F4E red-orange
      #98B8C9 neutral blue-gray
  - Bar rendering: horizontal SVG, 12px tall, with pentagonal chevron
    end-caps (paths M4 0H10V12H4L0 6L4 0Z / mirror), internal rects with
    white 1px vertical dividers, ▼ marker (Unicode) above the bar at
    TTD's value position.
  - Roboto font stack (Material UI default).
  - Sticky top filter bar: Benchmark Source / Platform / Environment / Marketplace.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ttd_benchmark.segments import segment_label

ROOT = Path("/Users/igor/dev/fiducia-data-works")
CSV_PATH = ROOT / "data" / "ana_quartiles_NoTTD-6.csv"
TTD_DATA = ROOT / "ttd_benchmark" / "ttd_q1_data.json"
OUT_HTML      = ROOT / "ttd_benchmark_q1_2026.html"
OUT_MEDIAN    = ROOT / "ttd_benchmark_q1_2026_median.html"
OUT_AGGREGATE = ROOT / "ttd_benchmark_q1_2026_aggregate.html"
LOGO_PATH     = ROOT / "data" / "assets" / "fiducia_logo.png"


def _logo_data_uri() -> str:
    import base64
    if not LOGO_PATH.exists():
        return ""
    with LOGO_PATH.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Filter matrix (Platform × Environment × Marketplace) mapped to CSV group_num.
# ---------------------------------------------------------------------------
# Any combination not listed falls back to the nearest precomputed segment.
FILTER_MATRIX = {
    # Platform=all
    ("all", "all",           "all"):  "1",
    ("all", "all",           "open"): "4",
    ("all", "all",           "pmp"):  "6",
    ("all", "web_and_app",   "all"):  "9",
    ("all", "web_and_app",   "open"): "12",
    ("all", "web_and_app",   "pmp"):  "14",
    ("all", "ctv",           "all"):  "17",
    ("all", "ctv",           "open"): "20",
    ("all", "ctv",           "pmp"):  "22",
    ("all", "mobile_in_app", "all"):  "25",
    ("all", "mobile_in_app", "open"): "28",
    ("all", "mobile_in_app", "pmp"):  "30",
    ("all", "other",         "all"):  "33",
    ("all", "other",         "open"): "36",
    ("all", "other",         "pmp"):  "38",
    ("all", "web",           "all"):  "41",
    ("all", "web",           "open"): "44",
    ("all", "web",           "pmp"):  "46",
    # Platform=programmatic (parallel to the above)
    ("programmatic", "all",           "all"):  "2",
    ("programmatic", "all",           "open"): "5",
    ("programmatic", "all",           "pmp"):  "7",
    ("programmatic", "web_and_app",   "all"):  "10",
    ("programmatic", "web_and_app",   "open"): "13",
    ("programmatic", "web_and_app",   "pmp"):  "15",
    ("programmatic", "ctv",           "all"):  "18",
    ("programmatic", "ctv",           "open"): "21",
    ("programmatic", "ctv",           "pmp"):  "23",
    ("programmatic", "mobile_in_app", "all"):  "26",
    ("programmatic", "mobile_in_app", "open"): "29",
    ("programmatic", "mobile_in_app", "pmp"):  "31",
    ("programmatic", "other",         "all"):  "34",
    ("programmatic", "other",         "open"): "37",
    ("programmatic", "other",         "pmp"):  "39",
    ("programmatic", "web",           "all"):  "42",
    ("programmatic", "web",           "open"): "45",
    ("programmatic", "web",           "pmp"):  "47",
}

# Labels for the dropdowns (YouTube dropped — TTD has no YouTube traffic)
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


# ---------------------------------------------------------------------------
# Benchmark table layout — mirrors Fiducia ordering, same metric labels.
# Tuple: (csv_name, display_label, fmt, lower_is_better, true_badge, indent)
# ---------------------------------------------------------------------------
# Only metrics that validate within ±10% of CSV tenant values (per
# validate.py run). Bad-threshold Sincera/DeepSee risk flags and ESG/Privacy
# metrics are omitted pending Fiducia predicate confirmation — they produced
# 40–10000% divergence from CSV reference values.
# Sections mirror Fiducia's /industry-benchmarks layout exactly (verified from
# screenshot). Fiducia's "Data Exchange" is an umbrella header with sub-groups
# Brand Safety & Suitability, Carbon Emissions, Data Integrity, ESG; since our
# renderer supports a single section-level header, those sub-groups are shown
# as separate sections here. Carbon Emissions is omitted (CO2ePM / CO2e/$ are
# not in the CSV). trueCpmOpportunityP omitted (not in the CSV).
SECTIONS = [
    ("TrueKPI Framework", [
        ("avCpm",              "CPM",         "usd", True,  False, 0),
        ("trueCpm",            "CPM",         "usd", True,  True,  0),
        ("cpmDelta",           "CPM Delta",   "usd", True,  True,  0),
        ("cpmIndexP",          "CPM Index",   "pct", True,  True,  0),
        ("trueImpressionsP",   "Impressions", "pct", False, True,  0),
    ]),
    ("Transaction Costs", [
        ("transactionCostsP",  "Transaction Costs", "pct", True,  False, 0),
        ("dspPlatformCostP",   "DSP Platform Fee",  "pct", True,  False, 1),
        ("dspDataCostP",       "DSP Data Cost",     "pct", True,  False, 1),
        ("dspOtherCostP",      "DSP Other Costs",   "pct", True,  False, 1),
        ("exchangeFeeP",       "SSP Fee",           "pct", True,  False, 1),
        ("sellerRevenueP",     "Sellers Revenue",   "pct", False, False, 0),
    ]),
    ("Media Productivity", [
        ("lossOfMediaProductivityP",    "Loss of Media Productivity", "pct",  True,  False, 0),
        ("ivtCostP",                    "IVT",                        "pct2", True,  False, 1),
        ("nonMeasurableCostP",          "Non-Measurable",             "pct",  True,  False, 1),
        ("nonViewableCostP",            "Non-Viewable",               "pct",  True,  False, 1),
        # MFA: use non-waterfall metric so the table row matches the same
        # metric shown in the Ad Experience section below (consistent value).
        ("webAdSpendWithDeepseeMfaP",   "MFA",                        "pct2", True,  False, 1),
        ("trueAdSpendP",                "AdSpend (DSP)",              "pct",  False, True,  0),
    ]),
    ("Supply Chain", [
        ("uniqueExchanges",                     "SSPs",                    "count", None,  False, 0),
        ("uniqueRootDomainsAndAppsCount",       "Domains & Apps",          "count", None,  False, 0),
        ("pmpCostShareP",                       "Private Marketplace",     "pct",   None,  False, 0),
        ("deepseeMetricsAdsTxtVerifiableRateP", "Ads.txt Verifiable Rate", "pct",   False, False, 0),
    ]),
    # ---- Data Exchange (umbrella in Fiducia; subsections below) ----
    # Mobian rows (Medium & High Risk, Negative/Neutral/Positive Sentiment)
    # omitted — Mobian coverage is absent on TTD inventory.
    ("Brand Safety & Suitability", [
        ("deepseeMetricsHighRiskP",               "High Risk [DeepSee]",         "pct", True,  False, 0),
        ("deepseeMetricsPossibleMisinformationP", "Possible Misinformation",     "pct", True,  False, 0),
    ]),
    ("Data Integrity", [
        ("compliantPciScore", "Data Integrity Index Score", "num", False, False, 0),
    ]),
    ("ESG", [
        ("goodNetEsgScore",                "ESG Score",      "num", False, False, 0),
        ("goodNetEsgRiskMediaWebAdSpendP", "ESG Risk Media", "pct", True,  False, 0),
    ]),
    ("Ad Experience", [
        ("webAdSpendWithDeepseeMfaP",         "MFA",                       "pct", True,  False, 0),
        ("deepseeMetricsTemplateP",           "Template Site",             "pct", True,  False, 0),
        ("deepseeMetricsAdClutterP",          "Ad Clutter",                "pct", True,  False, 0),
        ("sinceraAvgAdsToContentRatioP",      "Ads-to-Content Ratio",      "pct", True,  False, 0),
        ("sinceraBadByAvgAdsToContentRatioP", "Ads-to-Content Ratio Risk", "pct", True,  False, 0),
        ("sinceraAvgAdsInViewAds",            "Ads In View",               "num", True,  False, 0),
        ("sinceraBadByAvgAdsInViewP",         "Ads In View Risk",          "pct", True,  False, 0),
        ("sinceraAvgAdRefreshSec",            "Ad Refresh",                "sec", False, False, 0),
        ("sinceraBadByAvgAdRefreshP",         "Ad Refresh Risk",           "pct", True,  False, 0),
    ]),
]


# ---------------------------------------------------------------------------

def load_csv():
    with CSV_PATH.open() as f:
        return list(csv.DictReader(f))


def _float(v):
    if v is None or v == "" or (isinstance(v, str) and v.lower() == "nan"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_payload():
    csv_rows = load_csv()
    with TTD_DATA.open() as f:
        ttd = json.load(f)

    segs = [{
        "group_num": s["group_num"],
        "label": segment_label(s["inv_type"], s["inv_cat"], s["has_deal"], s["dsp"]),
    } for s in ttd["segments"]]

    ttd_med = ttd.get("ttd_median", {})
    ttd_agg = ttd.get("ttd_aggregate", {})

    # ttd_raw = TTD-as-whole volume/scalar values per segment, sourced from
    # ttd_aggregate (whose values are sum-across-marketers, the same concept
    # as Fiducia /explore global). Used for tile headers + segment gating.
    ttd_raw: dict[str, dict] = {}
    for g, metrics in ttd_agg.items():
        ttd_raw[g] = {m: row.get("value") for m, row in metrics.items()}

    dist: dict[str, dict] = {}
    for r in csv_rows:
        g = r["group_num"]
        if g not in ttd_raw and g not in FILTER_MATRIX.values():
            continue
        dist.setdefault(g, {})[r["metric_name"]] = {
            "min": _float(r["min"]),
            "q1":  _float(r["q1"]),
            "q2":  _float(r["q2"]),
            "q3":  _float(r["q3"]),
            "max": _float(r["max"]),
            "avg": _float(r["avg"]),
            # "global" = industry aggregate (sum across marketers, not median).
            # Matches /explore Key Findings values, e.g. trackedAdSpend global
            # = $115.52M industry total; cpmIndexP global = 39.3%;
            # waterfallTrueAdSpendP global = 37.9% (TrueAdSpend Index).
            "global": _float(r.get("global")),
        }

    sections_json = [{
        "name": section_name,
        "metrics": [{
            "name": m[0], "label": m[1], "fmt": m[2],
            "lower_is_better": m[3], "true_badge": m[4], "indent": m[5],
        } for m in metrics],
    } for section_name, metrics in SECTIONS]

    return {
        "segments": segs,
        "ttd_raw": ttd_raw,
        "ttd_median": ttd_med,
        "ttd_aggregate": ttd_agg,
        "dist": dist,
        "sections": sections_json,
        "filters": {
            "platforms":    PLATFORMS,
            "environments": ENVIRONMENTS,
            "marketplaces": MARKETPLACES,
            "matrix":       {"|".join(k): v for k, v in FILTER_MATRIX.items()},
        },
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TTD Programmatic Supply Quality — Q1 2026</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #ffffff;
  --panel: #fafafa;
  --text: #1a1f26;
  --muted: #6b7074;
  --subtle: #9aa0a6;
  --border: #e3e6ea;
  --soft-border: #eff1f3;
  --accent: #151717;
  /* Fiducia uses plain bold black for the "True" badge (inspected from live DOM) */
  --true: #151717;

  /* Fiducia bar palette (sampled from live SVG fills) */
  --q-green:   #55B376;
  --q-lime:    #C4C745;
  --q-yellow:  #F2C05F;
  --q-red:     #E36F4E;
  --q-neutral: #98B8C9;

  /* Explore chart palette */
  --e-truecpm:   #5E8FA9;   /* blue-gray CPM base */
  --e-index:     #E36F4E;   /* orange middle */
  --e-opp:       #C4C745;   /* olive striped top */
  --e-tas:       #7CD4CE;   /* teal TrueAdSpend base */
  --e-mp:        #E36F4E;   /* orange Loss of MP */
  --e-tx:        #5E8FA9;   /* blue Transaction Costs */
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; font-family: "Roboto", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); background: var(--bg); font-size: 14px; line-height: 1.45; -webkit-font-smoothing: antialiased; }

.page { max-width: 1440px; margin: 0 auto; padding: 0 0 80px; }

/* =============== STICKY TOP FILTERS =============== */
.topbar {
  position: sticky; top: 0; z-index: 20;
  background: rgba(255,255,255,0.96);
  backdrop-filter: saturate(180%) blur(10px);
  border-bottom: 1px solid var(--border);
  padding: 12px 32px;
  display: flex; gap: 20px; align-items: center; flex-wrap: wrap;
}
.topbar .brand { display: flex; align-items: center; margin-right: 20px; text-decoration: none; }
.topbar .brand img { height: 52px; width: auto; display: block; }
.filter { display: flex; flex-direction: column; gap: 2px; min-width: 140px; }
.filter label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
.filter select { border: 1px solid var(--border); border-radius: 6px; padding: 6px 26px 6px 10px; font-size: 13px; background: white; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23666' fill='none' stroke-width='1.5'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 8px center; cursor: pointer; color: var(--text); font-family: inherit;
}
.filter select:focus { outline: 2px solid #bfdbfe; outline-offset: 1px; }
.topbar .spacer { flex: 1; }
.topbar .view-tag { font-size: 12px; color: var(--muted); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; background: white; }
.topbar .seg-vol { font-size: 12px; color: var(--muted); }

/* =============== HEADER =============== */
.hdr { padding: 24px 32px 12px; }
.hdr h1 { font-size: 28px; font-weight: 500; margin: 6px 0 4px; letter-spacing: -0.015em; }
.hdr .tag { font-size: 13px; color: var(--muted); }

/* =============== SUMMARY TILES =============== */
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 16px 32px 20px; }
.tile { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
.tile .l { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 8px; display: block; }
.tile .l .true { color: var(--true); font-weight: 700; }
.tile .v { font-size: 26px; font-weight: 500; line-height: 1.1; letter-spacing: -0.015em; }
.tile .sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
.tile .cmp { font-size: 11px; color: var(--muted); margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--soft-border); }
.tile .cmp .delta-good { color: #16a34a; font-weight: 500; }
.tile .cmp .delta-bad  { color: #dc2626; font-weight: 500; }

/* =============== STACKED COMPARISON =============== */
.cmp-section { margin: 20px 32px 28px; }
.cmp-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; }
.cmp-title .help { color: var(--subtle); font-size: 12px; font-weight: 400; margin-left: 12px; }
/* Single flex row — TTD and Industry bars sit side-by-side close together,
   aligned to the same baseline, easier visual comparison. */
.cmp-row { display: flex; gap: 40px; justify-content: center; align-items: flex-end; padding-top: 34px; min-height: 300px; }
.cmp-bar { width: 76px; display: flex; flex-direction: column; justify-content: flex-end; position: relative; }
.cmp-bar .label-top { position: absolute; top: -24px; left: 50%; transform: translateX(-50%); font-size: 13px; font-weight: 600; white-space: nowrap; }
.cmp-bar .seg { position: relative; display: flex; align-items: center; justify-content: center; font-size: 11px; color: white; font-weight: 500; }
.cmp-bar .seg .lbl { text-shadow: 0 1px 1px rgba(0,0,0,0.3); }
/* Fixed height so bars with different axis-label line-wrap still have the
   same bottom-of-segment baseline. */
.cmp-bar .axis { text-align: center; font-size: 11px; color: var(--muted); margin-top: 6px; font-weight: 500; height: 28px; white-space: nowrap; overflow: visible; }
.cmp-legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 14px; font-size: 12px; color: var(--muted); }
.cmp-legend .sw { width: 10px; height: 10px; display: inline-block; margin-right: 5px; vertical-align: -1px; border-radius: 2px; }
.stripe-olive { background: repeating-linear-gradient(45deg, var(--e-opp) 0 6px, #fff8c2 6px 12px); }

/* =============== METHODOLOGY =============== */
.method { background: #f6f9fc; border: 1px solid #e3e8ed; border-radius: 8px; padding: 12px 16px; margin: 0 32px 24px; font-size: 13px; color: #3b4149; line-height: 1.5; }
.method .ttl { font-weight: 600; margin-bottom: 4px; color: #0f172a; }

/* =============== TABLE =============== */
/* Matches the waterfall chart span (32px margins on each side, filling the
   full container width of .page). */
.bm-wrap { margin: 0 32px; }
.bm-head, .bm-row { display: grid; grid-template-columns: minmax(220px, 1.4fr) minmax(140px, 160px) minmax(130px, 150px) minmax(360px, 2.6fr); gap: 24px; align-items: center; }
.bm-head { padding: 12px 0; border-bottom: 1px solid var(--border); font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
.bm-head > div:nth-child(2), .bm-head > div:nth-child(3) { text-align: right; }
.bm-section { font-size: 16px; font-weight: 600; margin: 24px 0 2px; color: var(--text); }
.bm-row { padding: 12px 0; border-bottom: 1px solid var(--soft-border); }
.bm-row:last-child { border-bottom: none; }
.metric { font-size: 14px; color: var(--text); display: block; }
.metric.i1 { padding-left: 18px; color: #474c52; }
.metric .true-label { color: var(--true); font-weight: 700; }
.metric .true-label::after { content: ""; }
.metric-note { font-size: 11px; color: var(--subtle); font-weight: 400; margin-top: 2px; line-height: 1.3; }
.val { text-align: right; font-size: 15px; font-variant-numeric: tabular-nums; font-weight: 400; white-space: nowrap; }
.val.ttd { color: var(--text); font-weight: 500; }
/* Tenant count moved to a discrete tooltip attribute on the value itself; no chip. */
.val.ttd[title] { cursor: help; }
.val.ind { color: var(--muted); font-weight: 400; }
.val.na  { color: var(--subtle); font-style: italic; font-size: 13px; }

/* =============== QUARTILE BAR (SVG) =============== */
/* Bar wrapper reserves a single row below the bar for min + median + max;
   all three render on the same baseline. Min pinned left (0%), max pinned
   right (100%), median absolute-positioned at its true x%. If median sits
   within 6% of either edge the min/max goes 40% opacity so the median stays
   legible (per user request: "use gradient & layers if they overlap"). */
.qbar-wrap { position: relative; padding: 18px 0 6px; min-width: 260px; }
.qbar-svg { width: 100%; height: 12px; overflow: visible; display: block; }
.qmarker { position: absolute; top: 0; transform: translateX(-50%); font-size: 11px; color: #151717; line-height: 1; font-family: "Segoe UI Symbol", "Apple Color Emoji", sans-serif; pointer-events: none; }
.qlabels-row { position: relative; height: 14px; margin-top: 6px; font-size: 11px; color: var(--subtle); font-variant-numeric: tabular-nums; }
.qlabels-row .min, .qlabels-row .max { position: absolute; top: 0; white-space: nowrap; }
.qlabels-row .min { left: 0; }
.qlabels-row .max { right: 0; }
.qlabels-row .med { position: absolute; top: 0; transform: translateX(-50%); white-space: nowrap; color: var(--text); font-weight: 500; background: rgba(255,255,255,0.9); padding: 0 2px; z-index: 2; }
.qlabels-row.med-near-min .min,
.qlabels-row.med-near-max .max { opacity: 0.4; }

/* =============== WATERFALL =============== */
.waterfall { margin: 8px 32px 28px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 18px 22px; }
.wf-ttl { font-size: 14px; font-weight: 600; margin-bottom: 14px; }
.wf-series { margin-bottom: 24px; }
.wf-tag { font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.wf-svg { width: 100%; height: 220px; display: block; }
.wf-legend { display: flex; gap: 18px; flex-wrap: wrap; font-size: 12px; color: var(--muted); margin-top: 8px; }
.wf-legend .sw { width: 10px; height: 10px; display: inline-block; margin-right: 5px; vertical-align: -1px; border-radius: 2px; }

@media (max-width: 1100px) {
  .topbar, .hdr, .summary, .cmp-section, .method, .bm-wrap, .waterfall { margin-left: 20px; margin-right: 20px; padding-left: 20px; padding-right: 20px; }
  .summary { grid-template-columns: repeat(2, 1fr); }
  .cmp-grid { grid-template-columns: 1fr; }
  .bm-head, .bm-row { grid-template-columns: 1.4fr 90px 90px 2fr; gap: 12px; }
}
</style>
</head>
<body>

<header class="topbar">
  <a class="brand" href="https://www.fiducia.eco/" target="_blank">
    <img src="__LOGO_SRC__" alt="fiducia · trust &amp; transparency for advertising" />
  </a>
  <div class="filter">
    <label>Benchmark Source</label>
    <select disabled><option>ANA Q1'26 🚩</option></select>
  </div>
  <div class="filter">
    <label>Platform</label>
    <select id="f-platform"></select>
  </div>
  <div class="filter">
    <label>Environment</label>
    <select id="f-environment"></select>
  </div>
  <div class="filter">
    <label>Marketplace</label>
    <select id="f-marketplace"></select>
  </div>
  <div class="spacer"></div>
  <div class="view-tag" id="view-tag"></div>
  <div class="seg-vol" id="seg-vol"></div>
</header>

<div class="page">

  <div class="hdr">
    <h1>TTD Programmatic Supply Quality</h1>
    <div class="tag">Q1 2026 · The Trade Desk vs ANA industry benchmark (TTD excluded) · <span id="seg-name"></span></div>
  </div>

  <section class="summary" id="summary"></section>

  <section class="cmp-section">
    <div class="cmp-title"><b>True</b>CPM Index — TTD vs Industry <span class="help">Total bar = <b>True</b>CPM ; blue = CPM, orange = lost premium ((TrueCPM − CPM)/TrueCPM)</span></div>
    <div class="cmp-row" id="cmp-truecpm"></div>
    <div class="cmp-legend">
      <span><span class="sw" style="background:var(--e-truecpm)"></span>CPM (base)</span>
      <span><span class="sw" style="background:var(--e-index)"></span><b>True</b>CPM Index (premium paid)</span>
    </div>
  </section>

  <section class="cmp-section">
    <div class="cmp-title"><b>True</b>AdSpend Index — TTD vs Industry <span class="help">100% of Total Ad Spend decomposed (teal + orange + blue = 100%)</span></div>
    <div class="cmp-row" id="cmp-trueadspend"></div>
    <div class="cmp-legend">
      <span><span class="sw" style="background:var(--e-tas)"></span><b>True</b>AdSpend (Seller)</span>
      <span><span class="sw" style="background:var(--e-mp)"></span>Loss of Media Productivity</span>
      <span><span class="sw" style="background:var(--e-tx)"></span>Transaction Costs</span>
    </div>
  </section>

  <section class="waterfall">
    <div class="wf-ttl">Spend Waterfall — how $100 of ad spend flows</div>
    <div class="wf-series">
      <div class="wf-tag">TTD Q1'26</div>
      <div id="wf-ttd"></div>
    </div>
    <div class="wf-series">
      <div class="wf-tag">ANA Q1'26 (industry total)</div>
      <div id="wf-industry"></div>
    </div>
    <div class="wf-legend">
      <span><span class="sw" style="background:var(--e-truecpm)"></span>Transaction fees (DSP + SSP)</span>
      <span><span class="sw" style="background:var(--e-mp)"></span>Media productivity losses (IVT, non-measurable, non-viewable, MFA)</span>
      <span><span class="sw" style="background:var(--e-tas)"></span><b>True</b>AdSpend (seller)</span>
    </div>
  </section>

  <div class="bm-wrap">
    <div class="bm-head">
      <div>Metric</div>
      <div>TTD Q1'26</div>
      <div>ANA Q1'26 median</div>
      <div>Benchmark (min · median · max)</div>
    </div>
    <div id="bm-body"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
// VIEW controls how TTD values are sourced:
//   "combined"  — pre-table uses aggregate, metric table uses median (default)
//   "median"    — both use median across qualifying TTD tenants
//   "aggregate" — both use aggregate (sum-across-marketers, Fiducia /explore style)
const VIEW = "__VIEW__";

// ---------- helpers ----------
function fmt(v, kind) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (isNaN(n)) return "—";
  switch (kind) {
    case "usd":     return "$" + n.toFixed(2);
    case "usd_big": return n>=1e6 ? "$" + (n/1e6).toFixed(1) + "M" : "$" + n.toLocaleString();
    // pct: 1 decimal by default (matches Fiducia), but if the value would
    // round to 0.0 at 1dp, promote to 2dp so we don't show a misleading 0.0%.
    case "pct":     {
      const oneDec = n.toFixed(1);
      if (oneDec === '0.0' && n !== 0) return n.toFixed(2) + "%";
      return oneDec + "%";
    }
    case "pct1":    return n.toFixed(1) + "%";
    case "pct2":    return n.toFixed(2) + "%";
    case "sec":     return n.toFixed(1) + " sec";
    case "count":   return n.toLocaleString(undefined, {maximumFractionDigits: 0});
    case "num":     return n.toFixed(2);
    case "num_big": return n.toLocaleString(undefined, {maximumFractionDigits: 0});
    default:        return n.toLocaleString();
  }
}
function fmtShort(v) {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  if (isNaN(n)) return "";
  if (Math.abs(n) >= 10000) return (n/1000).toFixed(0) + "k";
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, {maximumFractionDigits:0});
  if (Math.abs(n) >= 10) return n.toFixed(1);
  if (Math.abs(n) >= 0.1) return n.toFixed(2);
  return n.toFixed(3);
}

function ttdView(seg, metric) {
  // Returns tenant-level qualification info (used/excluded/predicate) —
  // median-based regardless of VIEW because aggregate has no per-tenant list.
  const row = (DATA.ttd_median[seg] || {})[metric];
  return row || {value: null, used: [], excluded: [], predicate: ''};
}
function _medValue(seg, metric) {
  const row = (DATA.ttd_median[seg] || {})[metric];
  return row ? row.value : null;
}
function _aggValue(seg, metric) {
  const row = (DATA.ttd_aggregate[seg] || {})[metric];
  return row ? row.value : null;
}
// ttdValue = value shown in the metric table.
//   combined/median → median; aggregate → aggregate.
// (Median is computed Python-side from per-tenant cells when Fiducia
// suppresses q2 for small samples, so no JS fallback needed.)
function ttdValue(seg, metric) {
  return VIEW === 'aggregate' ? _aggValue(seg, metric) : _medValue(seg, metric);
}
// ttdAggValue = value shown in tiles / stacked charts / waterfall.
//   combined/aggregate → aggregate; median → median
function ttdAggValue(seg, metric) {
  return VIEW === 'median' ? _medValue(seg, metric) : _aggValue(seg, metric);
}

function classify(val, dist, lower) {
  if (val === null || val === undefined || !dist) return null;
  const {q1, q2, q3} = dist;
  if ([q1,q2,q3].some(x => x === null || x === undefined)) return null;
  if (lower === null || lower === undefined) return null;
  let rank;
  if (val <= q1) rank = 0;
  else if (val <= q2) rank = 1;
  else if (val <= q3) rank = 2;
  else rank = 3;
  if (lower === false) rank = 3 - rank;
  return ["best","good","avg","bad"][rank];
}

// ---------- SVG QUARTILE BAR (matches Fiducia exactly) ----------
function qbarSVG(dist, ttdVal, lowerIsBetter) {
  if (!dist || dist.min === null || dist.max === null) {
    return '<div class="qbar-wrap"><div style="color:#9aa0a6;font-size:12px;text-align:center;padding:10px 0;">No distribution</div></div>';
  }
  const {min, q1, q2, q3, max} = dist;
  const span = max - min;
  if (span <= 0) return qbarSVGneutral(dist, ttdVal);
  const hasQuartiles = (q1 !== null && q2 !== null && q3 !== null);
  const palette = lowerIsBetter === true
                ? ['#55B376','#C4C745','#F2C05F','#E36F4E']
                : lowerIsBetter === false
                ? ['#E36F4E','#F2C05F','#C4C745','#55B376']
                : null;
  if (!palette || !hasQuartiles) return qbarSVGneutral(dist, ttdVal);

  const W = 100;   // fraction coords; CSS scales the SVG to 100% width
  const wQ1 = (q1 - min) / span * W;
  const wQ2 = (q2 - q1) / span * W;
  const wQ3 = (q3 - q2) / span * W;
  const wQ4 = (max - q3) / span * W;

  const CAP = 10;  // cap width in SVG units (for viewBox)
  // Convert to pixel-mapped viewBox (stretched); we use fractional units and
  // then position caps with fixed 10-unit width, middle rects scaled to span.
  // SVG units = 0..100 (full width) mapped via preserveAspectRatio=none.
  // Caps are drawn in 10px local units via their own group with fixed size.

  // Marker %
  let markerPct = null;
  if (ttdVal !== null && ttdVal !== undefined && !isNaN(Number(ttdVal))) {
    const clamped = Math.max(min, Math.min(max, ttdVal));
    markerPct = (clamped - min) / span * 100;
  }
  const medPct = (q2 - min) / span * 100;

  // Render SVG as percentage-positioned segments. The caps use absolute 10px
  // lengths via a separate SVG overlay positioned with CSS.
  const segs = [
    {pct: wQ1, color: palette[0]},
    {pct: wQ2, color: palette[1]},
    {pct: wQ3, color: palette[2]},
    {pct: wQ4, color: palette[3]},
  ];
  return qbarRender(segs, markerPct, medPct, q2, min, max, palette[0], palette[3]);
}

function qbarSVGneutral(dist, ttdVal) {
  if (!dist || dist.min === null || dist.max === null) return '';
  const {min, max, q1, q2, q3} = dist;
  const span = max - min;
  if (span <= 0) return '';
  const segs = (q1 !== null && q2 !== null && q3 !== null)
    ? [{pct: (q1-min)/span*100, color: '#98B8C9'},
       {pct: (q2-q1)/span*100, color: '#98B8C9'},
       {pct: (q3-q2)/span*100, color: '#98B8C9'},
       {pct: (max-q3)/span*100, color: '#98B8C9'}]
    : [{pct: 25, color:'#98B8C9'},{pct:25, color:'#98B8C9'},{pct:25, color:'#98B8C9'},{pct:25, color:'#98B8C9'}];
  let markerPct = null;
  if (ttdVal !== null && ttdVal !== undefined && !isNaN(Number(ttdVal))) {
    markerPct = (Math.max(min, Math.min(max, ttdVal)) - min) / span * 100;
  }
  const medPct = q2 !== null ? (q2 - min) / span * 100 : 50;
  return qbarRender(segs, markerPct, medPct, q2, min, max, '#98B8C9', '#98B8C9');
}

// The bar uses CSS flex: SVG pentagon caps on each side (10px fixed width)
// with a flex container in the middle holding 4 colored segments and 1px
// white dividers. Scales responsively with container width.
function qbarRender(segs, markerPct, medPct, medVal, min, max, leftColor, rightColor) {
  const middleFlex = segs.map((s, i) =>
    (i > 0 ? '<span style="width:1px;background:white;flex-shrink:0"></span>' : '') +
    `<span style="flex:${s.pct};background:${s.color};min-width:0"></span>`
  ).join('');
  const cap = (side, color) => {
    const d = side === 'left' ? 'M4 0H10V12H4L0 6L4 0Z' : 'M6 0H0V12H6L10 6L6 0Z';
    return `<svg viewBox="0 0 10 12" width="10" height="12" style="display:block;flex-shrink:0"><path d="${d}" fill="${color}"/></svg>`;
  };
  const markerSVG = (markerPct === null) ? '' : `
    <div class="qmarker" style="left:calc(10px + (100% - 20px) * ${markerPct/100}); top:2px">
      <svg width="12" height="8" viewBox="0 0 12 8" style="display:block"><path d="M1 1L6 6L11 1" stroke="#151717" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </div>`;
  const medLabel = medVal != null ? fmtShort(medVal) : '';
  // Collision class: fade min/max if median label would overlap.
  let rowCls = 'qlabels-row';
  if (medPct != null && medPct < 12) rowCls += ' med-near-min';
  if (medPct != null && medPct > 88) rowCls += ' med-near-max';
  // The 10px pentagon caps on each side live OUTSIDE the percentage-scaled
  // middle. The median (and marker) must be positioned against the inner
  // drawable range [10px, width-10px], not against the full wrapper width.
  const innerPos = (pct) => `calc(10px + (100% - 20px) * ${pct/100})`;
  return `
  <div class="qbar-wrap">
    ${markerSVG}
    <div style="display:flex; align-items:center; height:12px">
      ${cap('left', leftColor)}
      <div style="display:flex; flex:1; height:12px">${middleFlex}</div>
      ${cap('right', rightColor)}
    </div>
    <div class="${rowCls}">
      <span class="min">${fmtShort(min)}</span>
      ${medLabel ? `<span class="med" style="left:${innerPos(medPct)}">${medLabel}</span>` : ''}
      <span class="max">${fmtShort(max)}</span>
    </div>
  </div>`;
}

// ---------- SUMMARY TILES (mirror Fiducia /explore Key Findings) ----------
// Industry comparison uses the CSV `global` column — total-industry aggregate
// across all marketers, NOT per-marketer median. That's the same value shown
// on /explore: Total Ad Spend $115.52M, TrueCPM Index 39.3%, TrueAdSpend
// Index (seller-side) 37.9%.
function renderSummary(seg) {
  const rawTtd = DATA.ttd_raw[seg] || {};
  const dist = DATA.dist[seg] || {};
  const spend = rawTtd.trackedAdSpend || 0;
  const imps = rawTtd.trackedImpressions || 0;
  // Pre-table: TTD values are aggregates (sum-across-marketers style), same as
  // Fiducia /explore globals. Metric-table below uses medians.
  const cpm = ttdAggValue(seg, 'avCpm');
  const tcpm = ttdAggValue(seg, 'trueCpm');
  const cpmIdx = ttdAggValue(seg, 'cpmIndexP');
  // TrueAdSpend Index = seller-side residual. All components use the same
  // unified AV-gate predicate (post-recompute), so residual is self-consistent.
  // Client-side computation allows graceful NULL handling for segments where
  // a particular bucket has no data (e.g. MFA on CTV with no DeepSee coverage).
  const _sum = (...xs) => xs.reduce((s, x) => s + (x == null ? 0 : x), 0);
  const _tx = _sum(ttdAggValue(seg, 'waterfallDspPlatformCostP'),
                   ttdAggValue(seg, 'waterfallDspDataCostP'),
                   ttdAggValue(seg, 'waterfallDspOtherCostP'),
                   ttdAggValue(seg, 'waterfallExchangeFeeP'));
  const _mp = _sum(ttdAggValue(seg, 'waterfallIvtCostP'),
                   ttdAggValue(seg, 'waterfallNonMeasurableCostP'),
                   ttdAggValue(seg, 'waterfallNonViewableCostP'),
                   ttdAggValue(seg, 'waterfallMfaP'));
  const trueAdSpendIdx = (_tx > 0 || _mp > 0) ? (100 - _tx - _mp) : null;

  function cmp(val, distRow, hint, lower) {
    if (!distRow) return '';
    const ref = distRow.global ?? distRow.q2;
    if (ref == null) return '';
    const c = classify(val, distRow, lower);
    const badge = c==='best' ? '🟢 top quartile'
               : c==='good' ? '🟢 above median'
               : c==='avg'  ? '🟡 below median'
               : c==='bad'  ? '🔴 bottom quartile' : '';
    const delta = (val != null) ? (((val - ref) / Math.abs(ref)) * 100).toFixed(1) : null;
    const deltaHtml = (delta === null) ? '' :
      `<span class="${(lower ? Number(delta) < 0 : Number(delta) > 0) ? 'delta-good' : 'delta-bad'}">${Number(delta) >= 0 ? '+' : ''}${delta}%</span>`;
    return `vs ANA ${fmt(ref, hint)} · ${deltaHtml} ${badge}`;
  }

  const indSpend = dist.trackedAdSpend?.global;
  const indImps  = dist.trackedImpressions?.global;

  const tiles = [
    {
      label: 'Total Ad Spend',
      value: spend ? "$" + (spend/1e6).toFixed(1) + "M" : "—",
      sub: imps ? (imps/1e9).toFixed(2) + "B impressions" : '',
      cmp: indSpend ? `ANA: $${(indSpend/1e6).toFixed(1)}M${indImps ? ' · ' + (indImps/1e9).toFixed(2) + 'B imps' : ''}` : '',
    },
    {
      label: '<span class="true">True</span>CPM',
      value: fmt(tcpm, "usd"),
      cmp: cmp(tcpm, dist.trueCpm, "usd", true),
    },
    {
      label: '<span class="true">True</span>CPM Index',
      value: fmt(cpmIdx, "pct"),
      cmp: cmp(cpmIdx, dist.cpmIndexP, "pct", true),
    },
    (() => {
      // Industry TAS = 100 − (sum of waterfall Tx components) − (sum of
      // waterfall MediaLoss components), using CSV 'global' values.
      const g = (m) => dist[m] ? (dist[m].global ?? dist[m].q2) : null;
      const iTx = _sum(g('waterfallDspPlatformCostP'), g('waterfallDspDataCostP'),
                       g('waterfallDspOtherCostP'),    g('waterfallExchangeFeeP'));
      const iMP = _sum(g('waterfallIvtCostP'), g('waterfallNonMeasurableCostP'),
                       g('waterfallNonViewableCostP'), g('waterfallMfaP'));
      const iTas = (iTx > 0 || iMP > 0) ? (100 - iTx - iMP) : null;
      return {
        label: '<span class="true">True</span>AdSpend Index',
        value: fmt(trueAdSpendIdx, "pct"),
        // Build a synthetic distRow with the residual-industry value so
        // cmp() renders a proper "vs ANA 37.9%" line.
        cmp: cmp(trueAdSpendIdx, {global: iTas, q2: iTas, q1: null, q3: null}, "pct", false),
      };
    })(),
  ];
  return tiles.map(t => `
    <div class="tile">
      <div class="l">${t.label}</div>
      <div class="v">${t.value}</div>
      ${t.sub ? `<div class="sub">${t.sub}</div>` : ''}
      ${t.cmp ? `<div class="cmp">${t.cmp}</div>` : ''}
    </div>`).join('');
}

// ---------- TRUECPM INDEX STACKED COMPARISON ----------
function stackCpmBars(seg) {
  // Fiducia's TrueCPM Index chart uses AV CPM as the blue base segment
  // (/explore shows $4.65 for Q1'26 = avCpm global, not cpm).
  // Uses aggregate TTD values so the stack matches /explore convention.
  const ttdCpm = ttdAggValue(seg, 'avCpm');
  const ttdTcpm = ttdAggValue(seg, 'trueCpm');
  const dist = DATA.dist[seg] || {};
  const indCpm = dist.avCpm?.global ?? dist.avCpm?.q2;
  const indTcpm = dist.trueCpm?.global ?? dist.trueCpm?.q2;

  // Common Y scale across both bars for visual comparability
  const maxVal = Math.max(ttdTcpm || 0, indTcpm || 0, 1);
  const H = 260;
  const scale = H / maxVal;

  function bar(label, cpm, tcpm) {
    if (cpm == null || tcpm == null) {
      return `<div class="cmp-bar" style="height:${H+40}px;justify-content:center;align-items:center;color:#9aa0a6;font-size:12px">${label}<br/><br/>No data</div>`;
    }
    const cpmH = cpm * scale;
    const indexH = Math.max(0, (tcpm - cpm) * scale);
    const total = fmt(tcpm, "usd");
    const ci = cpm ? ((tcpm - cpm) / tcpm * 100).toFixed(1) + '%' : '';
    return `<div class="cmp-bar">
      <div class="label-top">${total}</div>
      <div class="seg" style="height:${indexH}px; background:var(--e-index)"><span class="lbl">${ci}</span></div>
      <div class="seg" style="height:${cpmH}px; background:var(--e-truecpm)"><span class="lbl">${fmt(cpm, "usd")}</span></div>
      <div class="axis">${label}</div>
    </div>`;
  }

  return bar('TTD Q1\'26', ttdCpm, ttdTcpm) +
         bar('ANA Q1\'26', indCpm, indTcpm);
}

// ---------- TRUEADSPEND INDEX STACKED COMPARISON ----------
// The three slices partition 100% of Total Ad Spend by definition
// (TrueAdSpend + Loss of Media Productivity + Transaction Costs = 100%).
// NO normalization is applied — if they don't sum to 100% the formulas or
// data have a problem and we want that visible, not hidden.
function stackTASBars(seg) {
  // Seller-side TrueAdSpend as Fiducia defines it in /explore:
  //   TAS (Seller) = Total Ad Spend − Transaction Costs − Loss of Media Productivity
  // TxCost and MediaLoss are computed as the SUM of their waterfall
  // components so the 3-way stack matches the waterfall chart exactly
  // (medians aren't additive, so using aggregated metrics would drift).
  const sumNonNull = (...xs) => xs.reduce((s, x) => s + (x == null ? 0 : x), 0);
  // Pre-table bars use aggregate TTD values (Fiducia /explore convention).
  const ttdTx = sumNonNull(
    ttdAggValue(seg, 'waterfallDspPlatformCostP'),
    ttdAggValue(seg, 'waterfallDspDataCostP'),
    ttdAggValue(seg, 'waterfallDspOtherCostP'),
    ttdAggValue(seg, 'waterfallExchangeFeeP'),
  );
  const ttdMP = sumNonNull(
    ttdAggValue(seg, 'waterfallIvtCostP'),
    ttdAggValue(seg, 'waterfallNonMeasurableCostP'),
    ttdAggValue(seg, 'waterfallNonViewableCostP'),
    ttdAggValue(seg, 'waterfallMfaP'),
  );
  const ttdTas = (ttdTx > 0 || ttdMP > 0) ? (100 - ttdTx - ttdMP) : null;

  const dist = DATA.dist[seg] || {};
  const g = (m) => dist[m] ? (dist[m].global ?? dist[m].q2) : null;
  const indTx = sumNonNull(g('waterfallDspPlatformCostP'), g('waterfallDspDataCostP'),
                           g('waterfallDspOtherCostP'),    g('waterfallExchangeFeeP'));
  const indMP = sumNonNull(g('waterfallIvtCostP'), g('waterfallNonMeasurableCostP'),
                           g('waterfallNonViewableCostP'), g('waterfallMfaP'));
  const indTas = (indTx > 0 || indMP > 0) ? (100 - indTx - indMP) : null;

  function bar(label, tas, mp, tx) {
    if ([tas, mp, tx].some(v => v == null)) {
      return `<div class="cmp-bar" style="justify-content:center;align-items:center;color:#9aa0a6;font-size:12px;width:100px;height:260px">
        ${label}<br/><br/>No data</div>`;
    }
    const sum = tas + mp + tx;
    const H = 240;
    const pct = x => x * H / 100;
    const note = (Math.abs(sum - 100) > 2)
      ? `<div style="font-size:10px;color:#dc2626;text-align:center;margin-top:4px">sum = ${sum.toFixed(1)}% ≠ 100%</div>`
      : '';
    return `<div class="cmp-bar">
      <div class="label-top">${tas.toFixed(1)}%</div>
      <div class="seg" style="height:${pct(tx)}px; background:var(--e-tx)"><span class="lbl">${tx.toFixed(1)}%</span></div>
      <div class="seg" style="height:${pct(mp)}px; background:var(--e-mp)"><span class="lbl">${mp.toFixed(1)}%</span></div>
      <div class="seg" style="height:${pct(tas)}px; background:var(--e-tas)"><span class="lbl" style="color:#0a3b37">${tas.toFixed(1)}%</span></div>
      <div class="axis">${label}</div>
      ${note}
    </div>`;
  }

  return bar('TTD Q1\'26', ttdTas, ttdMP, ttdTx) +
         bar('ANA Q1\'26', indTas, indMP, indTx);
}

// ---------- WATERFALL (Fiducia-style SVG) ----------
// Fiducia's spend waterfall: a vertical bar-chart where each bar represents
// either an absolute value (total, sellers revenue, trueadspend) or a delta
// (transaction fees, media productivity losses). Running total stairs from
// 100% down to TrueAdSpend%. Dotted connectors link consecutive bar tops.
function waterfallSVG(tag, getPct) {
  const v = (m) => {
    const x = getPct(m);
    return (typeof x === 'number' && !isNaN(x)) ? x : null;
  };
  // Use waterfall-component sums so the staircase is internally consistent;
  // do NOT use sellerRevenueP or aggregated MediaLoss (medians aren't additive
  // so they'd drift from the bar components).
  const txFees = (v('waterfallDspPlatformCostP') || 0) + (v('waterfallDspDataCostP') || 0) +
                 (v('waterfallDspOtherCostP')    || 0) + (v('waterfallExchangeFeeP')   || 0);
  const sellers = 100 - txFees;
  const ivt = v('waterfallIvtCostP') || 0;
  const nonMeas = v('waterfallNonMeasurableCostP') || 0;
  const nonView = v('waterfallNonViewableCostP') || 0;
  const mfa = v('waterfallMfaP') || 0;
  // TrueAdSpend is defined by Fiducia methodology as the residual:
  //   TAS = Total Ad Spend − Transaction Costs − Media Productivity Loss
  // Using this formula keeps the waterfall staircase internally consistent
  // AND makes the TrueAdSpend Index chart's value match the waterfall's
  // final bar. Do NOT use waterfallTrueAdSpendP (TRUE_SPEND/SPEND) here —
  // that's a DIFFERENT metric (buy-side, excludes AV-unmatched spend).
  const trueAs = sellers - ivt - nonMeas - nonView - mfa;

  // Running stair positions (each bar spans [y_low, y_high])
  let running = 100;
  const bars = [
    {lbl: 'Total Ad Spend',  type: 'abs', value: 100,                   color: '#5E8FA9', topVal: 100},
    {lbl: 'DSP Platform Fee',type: 'dec', value: v('dspPlatformCostP'), color: '#5E8FA9'},
    {lbl: 'DSP Data Cost',   type: 'dec', value: v('dspDataCostP'),     color: '#5E8FA9'},
    {lbl: 'DSP Other Costs', type: 'dec', value: v('dspOtherCostP'),    color: '#5E8FA9'},
    {lbl: 'SSP Fee',         type: 'dec', value: v('exchangeFeeP'),     color: '#5E8FA9'},
    {lbl: 'Sellers Revenue', type: 'abs', value: sellers,               color: '#5E8FA9', topVal: sellers},
    {lbl: 'IVT',             type: 'dec', value: ivt,                   color: '#E36F4E'},
    {lbl: 'Non-Measurable',  type: 'dec', value: nonMeas,               color: '#E36F4E'},
    {lbl: 'Non-Viewable',    type: 'dec', value: nonView,               color: '#E36F4E'},
    {lbl: 'MFA',             type: 'dec', value: mfa,                   color: '#E36F4E'},
    {lbl: 'TrueAdSpend',     type: 'abs', value: trueAs,                color: '#7CD4CE', topVal: trueAs},
  ];

  // Compute [lo, hi] for each bar.
  const layout = [];
  let cursor = 100;          // used for type='dec' stair tracking
  bars.forEach((b, i) => {
    if (b.type === 'abs') {
      // Absolute bars reset cursor to their running-total height so stairs
      // connect cleanly. For 'TrueAdSpend', topVal is already the residual
      // (sellers − mediaLoss), which equals the current cursor after the
      // loss decrements have been applied.
      const hi = b.topVal;
      layout.push({lbl: b.lbl, lo: 0, hi, color: b.color, lblPct: hi});
      cursor = hi;
    } else {
      const dec = b.value || 0;
      const hi = cursor;
      const lo = cursor - dec;
      layout.push({lbl: b.lbl, lo, hi, color: b.color, lblPct: dec, isDec: true});
      cursor = lo;
    }
  });

  // SVG geometry
  const W = 900, H = 220;
  const pad = {l: 20, r: 20, t: 30, b: 40};
  const chartW = W - pad.l - pad.r;
  const chartH = H - pad.t - pad.b;
  const n = layout.length;
  const slotW = chartW / n;
  const barW = Math.min(slotW - 10, 55);
  const y = (pct) => pad.t + chartH * (1 - pct/100);

  let svg = `<svg class="wf-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  // y axis grid 0, 50, 100
  [0, 25, 50, 75, 100].forEach(p => {
    const yy = y(p);
    svg += `<line x1="${pad.l}" y1="${yy}" x2="${W - pad.r}" y2="${yy}" stroke="#eef1f3" stroke-width="1"/>`;
    svg += `<text x="${pad.l - 4}" y="${yy + 4}" font-size="10" fill="#9aa0a6" text-anchor="end">${p}</text>`;
  });

  // Bars + labels
  layout.forEach((b, i) => {
    const cx = pad.l + slotW * i + slotW / 2;
    const xL = cx - barW / 2;
    const yTop = y(b.hi);
    const yBot = y(b.lo);
    const barH = Math.max(0.5, yBot - yTop);
    svg += `<rect x="${xL}" y="${yTop}" width="${barW}" height="${barH}" fill="${b.color}" rx="1"/>`;
    // Value label above bar
    const lblTxt = (b.isDec ? '−' : '') + (b.lblPct === null || b.lblPct === undefined ? '—' : b.lblPct.toFixed(1) + '%');
    svg += `<text x="${cx}" y="${yTop - 6}" font-size="11" fill="#151717" text-anchor="middle" font-weight="500">${lblTxt}</text>`;
    // Category label below chart
    const words = b.lbl.split(' ');
    words.forEach((w, wi) => {
      svg += `<text x="${cx}" y="${H - pad.b + 14 + wi * 11}" font-size="10" fill="#6b7074" text-anchor="middle">${w}</text>`;
    });
    // Dashed stair connector to next bar's top
    if (i < layout.length - 1) {
      const next = layout[i + 1];
      const yFrom = y(b.lo);          // for dec we connect bottom of current to top of next
      const yTo   = y(next.hi);
      const xFrom = xL + barW;
      const xTo   = pad.l + slotW * (i + 1) + slotW / 2 - barW / 2;
      svg += `<line x1="${xFrom}" y1="${yFrom}" x2="${xTo}" y2="${yTo}" stroke="#9aa0a6" stroke-width="1" stroke-dasharray="3,3"/>`;
    }
  });

  svg += '</svg>';
  return svg;
}

function renderWaterfallTTD(seg) {
  // Waterfall uses aggregate TTD (matches Fiducia /explore's Spend Waterfall
  // layout where bars compose to 100% of total spend).
  return waterfallSVG('ttd', (m) => {
    const v = ttdAggValue(seg, m);
    return (typeof v === 'number') ? v : null;
  });
}
function renderWaterfallIndustry(seg) {
  const dist = DATA.dist[seg] || {};
  // Industry waterfall uses CSV 'global' (sum over all marketers) — matches
  // the values on Fiducia /explore's Spend Waterfall (e.g. 100% → 75.6%
  // Sellers Revenue → 37.9% TrueAdSpend).
  return waterfallSVG('ana', (m) => (dist[m] ? (dist[m].global ?? dist[m].q2) : null));
}

// ---------- MAIN TABLE ----------
function renderTable(seg) {
  const dist = DATA.dist[seg] || {};
  return DATA.sections.map(section => {
    const rows = section.metrics
      .map(m => {
        const v = ttdValue(seg, m.name);
        const d = dist[m.name];
        if ((v === null || v === undefined) && !d) return '';
        return renderRow(m, v, d, seg);
      })
      .filter(Boolean).join('');
    if (!rows) return '';
    return `<div class="bm-section">${section.name}</div>${rows}`;
  }).join('');
}

function renderRow(m, ttdVal, dist, seg) {
  const bar = qbarSVG(dist, ttdVal, m.lower_is_better);
  const ttdFmt = ttdVal === null || ttdVal === undefined ? "—" : fmt(ttdVal, m.fmt);
  const indFmt = dist && dist.q2 !== null && dist.q2 !== undefined ? fmt(dist.q2, m.fmt) : "—";
  const truePre = m.true_badge ? '<span class="true-label">True</span>' : '';
  const view = ttdView(seg, m.name);
  const used = view.used || [];
  const excluded = view.excluded || [];
  let tipAttr = '';
  if (used.length || excluded.length) {
    const title = `Qualified (${used.length}): ${used.join(', ') || '—'}` + (excluded.length ? `\nExcluded: ${excluded.join(', ')}` : '');
    tipAttr = ` title="${title.replace(/"/g, '&quot;')}"`;
  }
  // Per-metric inline note (small grey subtext under the label). Used to
  // flag methodology caveats — e.g. buy-side TrueAdSpend in the table vs
  // seller-side residual in the TrueAdSpend Index tile at the top.
  const METRIC_NOTES = {
    'trueAdSpendP': 'Buy-side: TRUE_SPEND / AV_SPEND. Tile above uses seller-side residual (100 − Tx − Media Loss).',
  };
  const note = METRIC_NOTES[m.name];
  const noteHtml = note ? `<div class="metric-note">${note}</div>` : '';
  return `
    <div class="bm-row">
      <div class="metric ${m.indent ? 'i1' : ''}">${truePre}${m.label}${noteHtml}</div>
      <div class="val ttd"${tipAttr}>${ttdFmt}</div>
      <div class="val ind">${indFmt}</div>
      <div>${bar}</div>
    </div>`;
}

// ---------- SEGMENT ROUTING ----------
function currentSegment() {
  const p = document.getElementById('f-platform').value;
  const e = document.getElementById('f-environment').value;
  const m = document.getElementById('f-marketplace').value;
  return DATA.filters.matrix[`${p}|${e}|${m}`] || null;
}

function redraw() {
  const seg = currentSegment();
  const raw = DATA.ttd_raw[seg] || {};
  const rawSpend = raw.trackedAdSpend || 0;

  // Distinguish "filter combination not precomputed" from "TTD had no
  // meaningful data in this combination" (< $1000 spend per Fiducia predicate).
  const emptyPayload = () => {
    document.getElementById('summary').innerHTML = '';
    document.getElementById('cmp-truecpm').innerHTML = '';
    document.getElementById('cmp-trueadspend').innerHTML = '';
    document.getElementById('wf-ttd').innerHTML = '';
    document.getElementById('wf-industry').innerHTML = '';
    document.getElementById('seg-vol').textContent = '';
    document.getElementById('seg-name').textContent = '';
  };

  if (!seg) {
    document.getElementById('bm-body').innerHTML =
      '<div style="padding:40px;text-align:center;color:#9aa0a6">This filter combination isn\'t precomputed yet. Pick a different Platform/Environment/Marketplace.</div>';
    emptyPayload();
    return;
  }
  if (!DATA.ttd_raw[seg]) {
    document.getElementById('bm-body').innerHTML =
      `<div style="padding:40px;text-align:center;color:#9aa0a6">Segment <b>${seg}</b> precompute pending (still running).</div>`;
    emptyPayload();
    return;
  }
  if (rawSpend < 1000) {
    document.getElementById('bm-body').innerHTML =
      `<div style="padding:40px;text-align:center;color:#6b7074">
        <b>Insufficient TTD data for this split.</b><br/>
        TTD Q1'26 spend in this filter combination: <b>$${rawSpend.toFixed(2)}</b>
        (threshold: $1,000 — matches Fiducia's predicate).
      </div>`;
    emptyPayload();
    return;
  }
  document.getElementById('summary').innerHTML = renderSummary(seg);
  document.getElementById('cmp-truecpm').innerHTML = stackCpmBars(seg);
  document.getElementById('cmp-trueadspend').innerHTML = stackTASBars(seg);
  document.getElementById('wf-ttd').innerHTML = renderWaterfallTTD(seg);
  document.getElementById('wf-industry').innerHTML = renderWaterfallIndustry(seg);
  document.getElementById('bm-body').innerHTML = renderTable(seg);
  const imps = raw.trackedImpressions || 0;
  document.getElementById('seg-vol').textContent =
    rawSpend && imps ? `$${(rawSpend/1e6).toFixed(1)}M · ${(imps/1e9).toFixed(2)}B imps` : '';
  const segInfo = DATA.segments.find(s => s.group_num === seg);
  document.getElementById('seg-name').textContent = segInfo ? segInfo.label : '';
}

function init() {
  document.getElementById('view-tag').textContent =
    VIEW === 'median'    ? 'TTD = median across qualifying tenants'
  : VIEW === 'aggregate' ? 'TTD = aggregate across qualifying tenants'
  :                        'TTD: aggregate (tiles/stack/waterfall) · median (table)';

  const fP = document.getElementById('f-platform');
  const fE = document.getElementById('f-environment');
  const fM = document.getElementById('f-marketplace');
  DATA.filters.platforms.forEach(([v, l]) => fP.add(new Option(l, v)));
  DATA.filters.environments.forEach(([v, l]) => fE.add(new Option(l, v)));
  DATA.filters.marketplaces.forEach(([v, l]) => fM.add(new Option(l, v)));
  [fP, fE, fM].forEach(s => s.addEventListener('change', redraw));
  redraw();
}

init();
</script>
</body>
</html>
"""


def main():
    payload = build_payload()
    payload_js = json.dumps(payload, default=str)
    logo_uri = _logo_data_uri()
    for view, out_path in [("combined", OUT_HTML),
                           ("median", OUT_MEDIAN),
                           ("aggregate", OUT_AGGREGATE)]:
        html = (HTML_TEMPLATE
                .replace("__DATA_JSON__", payload_js)
                .replace("__VIEW__", view)
                .replace("__LOGO_SRC__", logo_uri))
        out_path.write_text(html)
        print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB) [view={view}]")


if __name__ == "__main__":
    main()
