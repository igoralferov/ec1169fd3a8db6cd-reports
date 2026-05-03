TTD Q1 2026 Programmatic Supply Quality — Fiducia Benchmark Bundle
===================================================================

CONTENTS

  report/
    ttd_benchmark_q1_2026.html   Standalone HTML — open in any browser.
                                  Self-contained: data, logo, CSS, JS all
                                  embedded. No external files required.
                                  (Google Fonts load if online; graceful
                                  fallback to system sans-serif offline.)

  source/                       Source materials to regenerate the report.
    data/
      ana_quartiles_NoTTD-6.csv       Fiducia industry distribution
                                       (24 ANA marketers, TTD excluded).
      input/ana_quartiles_TTD_Only-2.csv
                                       Fiducia TTD-only snapshot with
                                       bad inventory pre-truncated by
                                       Fiducia (hp & kcc dropped; bad
                                       bayer CTV/Other slices removed).
      assets/fiducia_logo.png         Logo (already embedded in report).
    ttd_benchmark/
      __init__.py                     (empty; makes it a Python package)
      segments.py                     CSV segment-tuple → WHERE clause.
      render.py                       HTML template + SECTIONS registry.
      render_from_csv.py              CSV-based payload builder.
      render_from_csv_fiducia_truncated.py
                                       Main entry point for the final
                                       report (combined view: global
                                       at top, median in table).

REGENERATE (from source/)

  cd source
  python3 -m ttd_benchmark.render_from_csv_fiducia_truncated

  Writes: ../data/output/ttdonly-benchmark-2026q1-final/ttd_benchmark_q1_2026.html

VIEW

  open report/ttd_benchmark_q1_2026.html

DATA SCOPE

  TTD scope after Fiducia truncation: 6 tenants, $77.9M total spend.
  - Has AV:   jnj (DV, $10.0M), dell (DV, $3.25M), bayer (PM, $4.65M)
  - No AV:    gm ($39.75M), popeyes ($10.58M), hershey ($9.72M)
  - Excluded: hp, kcc (IAS CTV regression)

  Industry: ANA Programmatic Transparency Benchmark Q1 2026, NoTTD snapshot
  (24 marketers, TTD excluded from distribution).
