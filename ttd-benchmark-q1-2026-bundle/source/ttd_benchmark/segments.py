"""Parse CSV segment tuples (5 columns) into ClickHouse WHERE clauses.

Segment columns in ana_quartiles_NoTTD-6.csv:
  key_inventory_type_common:  [Audio|Display|Native|Other|Unknown|Video] or [] (any)
  inventory_category:         [CTV|Mobile In-App|Other|Web] | [$WebAndMobileInApp$] | [] (any)
  has_deal:                   [true|false] | [] (any)
  key_dsp_name:               [$Programmatic$] | [$YouTube$] | [] (any)

Aliases (Q1 2026 DSPs: Amazon, Basis, CM360, Dbm, dv360, ttd, ttd2025, viant, yahoo,
plus *-YouTube variants):
  $Programmatic$        -> DSP name does NOT contain 'YouTube'
  $YouTube$             -> DSP name contains 'YouTube'
  $WebAndMobileInApp$   -> inventory_category IN ('Web','Mobile In-App')
"""

def _unwrap(cell: str) -> str | None:
    """Convert '[foo]' -> 'foo'; '[]' -> None."""
    cell = cell.strip()
    if cell == "[]" or cell == "":
        return None
    if cell.startswith("[") and cell.endswith("]"):
        return cell[1:-1]
    return cell


def segment_where(inv_type: str, inv_cat: str, has_deal: str, dsp: str) -> str:
    """Return a SQL WHERE clause (no leading 'WHERE') for a CSV segment tuple.

    All four inputs are the raw CSV cells (still wrapped in brackets).
    """
    clauses: list[str] = []
    t = _unwrap(inv_type)
    c = _unwrap(inv_cat)
    d = _unwrap(has_deal)
    s = _unwrap(dsp)

    if t is not None:
        clauses.append(f"key_inventory_type_common = '{t}'")

    if c is not None:
        if c == "$WebAndMobileInApp$":
            clauses.append("inventory_category IN ('Web','Mobile In-App')")
        else:
            clauses.append(f"inventory_category = '{c}'")

    if d is not None:
        clauses.append(f"has_deal = {d}")

    if s is not None:
        if s == "$Programmatic$":
            clauses.append("key_dsp_name NOT LIKE '%YouTube%'")
        elif s == "$YouTube$":
            clauses.append("key_dsp_name LIKE '%YouTube%'")
        else:
            clauses.append(f"key_dsp_name = '{s}'")

    return " AND ".join(clauses) if clauses else "1"


def segment_label(inv_type: str, inv_cat: str, has_deal: str, dsp: str) -> str:
    """Human-readable segment label for UI."""
    parts = []
    t, c, d, s = _unwrap(inv_type), _unwrap(inv_cat), _unwrap(has_deal), _unwrap(dsp)
    parts.append(t or "All types")
    parts.append({"$WebAndMobileInApp$": "Web+App"}.get(c, c) or "All inventory")
    if d is not None:
        parts.append("Deals" if d == "true" else "Open")
    if s is not None:
        parts.append({"$Programmatic$": "Programmatic",
                      "$YouTube$": "YouTube"}.get(s, s))
    return " · ".join(parts)
