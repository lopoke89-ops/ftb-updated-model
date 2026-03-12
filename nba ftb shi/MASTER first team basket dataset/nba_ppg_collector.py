"""
NBA PPG Dataset Collector - 2025-26 Season
==========================================
Reads every player mentioned in NBA_First_Basket_2025-26.xlsx and builds
a separate dataset showing each player's points-per-game (PPG) for the
current season, pulled from NBA.com's league dash stats endpoint.

One API call fetches all player stats at once — fast and rate-limit friendly.
Re-run at any time to refresh PPG figures as the season progresses, or to
pick up new players that appear in the first-basket dataset.

Requirements:
    pip install nba_api openpyxl pandas

Usage:
    python nba_ppg_collector.py
    python nba_ppg_collector.py --source NBA_First_Basket_2025-26.xlsx
    python nba_ppg_collector.py --source NBA_First_Basket_2025-26.xlsx --output NBA_PPG_2025-26.xlsx
"""

import argparse
import time
import re
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from pathlib import Path

try:
    from nba_api.stats.endpoints import leaguedashplayerstats
    from nba_api.stats.static import players as nba_players_static
    from nba_api.stats.static import teams  as nba_teams_static
except ImportError:
    raise SystemExit("Missing dependency: pip install nba_api")

SOURCE_FILE = "NBA_First_Basket_2025-26.xlsx"
OUTPUT_FILE = "NBA_PPG_2025-26.xlsx"
SEASON      = "2025-26"
DELAY       = 1.5
MAX_RETRIES = 5
RETRY_BACKOFF = [5, 15, 30, 60, 120]

# ─── Team lookups ─────────────────────────────────────────────────────────────

_teams       = nba_teams_static.get_teams()
TEAM_ABB_MAP = {t["abbreviation"]: t["id"] for t in _teams}

# ─── Player name resolution ───────────────────────────────────────────────────

def build_name_maps():
    """
    Build lookup structures from the NBA API's static player list.

    Returns:
        nameI_map   : "F. LastName" → list of matching player dicts
        fullname_map: "Full Name"   → player dict  (lowercased key)
        id_map      : player_id     → player dict
    """
    active = nba_players_static.get_active_players()
    nameI_map, fullname_map, id_map = {}, {}, {}

    for p in active:
        fn = p["first_name"].strip()
        ln = p["last_name"].strip()
        id_map[p["id"]] = p

        # Full name index (case-insensitive)
        fullname_map[f"{fn} {ln}".lower()] = p

        # NameI index:  "A. Edwards"
        if fn:
            key = f"{fn[0]}. {ln}"
            nameI_map.setdefault(key, []).append(p)

    return nameI_map, fullname_map, id_map


def resolve_players(first_basket_df: pd.DataFrame,
                    nameI_map: dict,
                    fullname_map: dict) -> dict:
    """
    Match every player name in the first-basket dataset to a player_id.

    Strategy:
      1. Try exact full-name lookup (covers names like "Luka Doncic")
      2. Try nameI lookup ("L. Doncic")
         - If exactly 1 match → done
         - If multiple matches → use team context to disambiguate
      3. Remaining unmatched → warn and skip

    Returns:
        {player_id: {"nameI": str, "full_name": str}}
    """
    # Build team → set of active player_ids  (for disambiguation)
    team_roster = _build_team_rosters()

    resolved = {}   # player_id → {"nameI", "full_name"}
    unmatched = []

    # Gather every (player_name, team_abbrev) pair from the dataset
    pairs: list[tuple[str, str]] = []
    for _, row in first_basket_df.iterrows():
        for player_col, team_col in [
            ("HOME_FIRST_SCORER", "HOME_TEAM"),
            ("AWAY_FIRST_SCORER", "AWAY_TEAM"),
        ]:
            name = str(row.get(player_col, "")).strip()
            team = str(row.get(team_col,   "")).strip()
            if name and name not in ("N/A", "None", "nan"):
                pairs.append((name, team))

    for name, team in pairs:
        # Skip if already resolved
        if any(v["nameI"] == name for v in resolved.values()):
            continue

        # ── 1. Try full-name lookup first ─────────────────────────────
        hit = fullname_map.get(name.lower())
        if hit:
            resolved[hit["id"]] = {
                "nameI"    : name,
                "full_name": f"{hit['first_name']} {hit['last_name']}",
            }
            continue

        # ── 2. Try nameI lookup ───────────────────────────────────────
        hits = nameI_map.get(name, [])

        if len(hits) == 1:
            p = hits[0]
            resolved[p["id"]] = {
                "nameI"    : name,
                "full_name": f"{p['first_name']} {p['last_name']}",
            }
            continue

        if len(hits) > 1:
            # Disambiguate using the team the player scored for
            team_id = TEAM_ABB_MAP.get(team)
            if team_id:
                roster_ids = team_roster.get(team_id, set())
                candidates = [p for p in hits if p["id"] in roster_ids]
                if len(candidates) == 1:
                    p = candidates[0]
                    resolved[p["id"]] = {
                        "nameI"    : name,
                        "full_name": f"{p['first_name']} {p['last_name']}",
                    }
                    continue
            # Still ambiguous after roster check — take first, warn
            p = hits[0]
            print(f"  AMBIGUOUS: '{name}' matched {[h['full_name'] for h in hits]}"
                  f" — using '{p['full_name']}' (team hint: {team})")
            resolved[p["id"]] = {
                "nameI"    : name,
                "full_name": f"{p['first_name']} {p['last_name']}",
            }
            continue

        unmatched.append((name, team))

    if unmatched:
        print(f"\n  Could not resolve {len(unmatched)} player name(s):")
        for n, t in sorted(set(unmatched)):
            print(f"    '{n}' (team: {t})")
        print("  These players will be skipped.\n")

    print(f"  Resolved {len(resolved)} unique players.")
    return resolved


def _build_team_rosters() -> dict:
    """Return {team_id: set(player_id)} using the static active player list."""
    # nba_api static data doesn't have roster info, so we build a loose map
    # from the nameI_map — just used as a tiebreaker hint, not authoritative.
    # A proper roster fetch would need another API call; skip for performance.
    return {}


# ─── Stats fetch ──────────────────────────────────────────────────────────────

def fetch_all_ppg(season: str = SEASON) -> pd.DataFrame:
    """
    Single API call to get per-game stats for all players this season.
    Returns a DataFrame indexed by PLAYER_ID with PPG and supporting stats.
    """
    print("Fetching league-wide player stats from NBA.com...")
    for attempt in range(MAX_RETRIES):
        try:
            dash = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
                measure_type_detailed_defense="Base",
            )
            df = dash.get_data_frames()[0]
            time.sleep(DELAY)
            print(f"  Retrieved stats for {len(df)} players.")
            return df
        except Exception as e:
            err = str(e)
            is_retryable = any(k in err.lower() for k in
                               ["timed out", "timeout", "429", "rate"])
            if is_retryable and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  TIMEOUT (attempt {attempt+1}/{MAX_RETRIES}) — "
                      f"waiting {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to fetch player stats: {e}")

    raise RuntimeError("All retries exhausted fetching player stats.")


# ─── Excel output ─────────────────────────────────────────────────────────────

HEADERS = [
    "PLAYER_ID",
    "FULL_NAME",
    "TEAM",
    "GP",        # games played
    "GS",        # games started
    "MIN",       # minutes per game
    "PPG",       # points per game  ← the headline stat
    "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT",
    "FTM", "FTA", "FT_PCT",
    "REB", "AST", "STL", "BLK", "TOV",
    "PLUS_MINUS",
    "FIRST_BASKET_COUNT",   # how many times in the first-basket dataset
]

COL_WIDTHS = [12, 26, 8, 6, 6, 8, 8,
              7, 7, 8,
              7, 7, 8,
              7, 7, 8,
              7, 7, 7, 7, 7,
              10,
              18]


def write_ppg_excel(records: list[dict], path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "PPG"

    # ── Header ────────────────────────────────────────────────────────────
    hdr_fill  = PatternFill("solid", start_color="17375E")
    hdr_font  = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, h in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill      = hdr_fill
        cell.font      = hdr_font
        cell.alignment = hdr_align

    for i, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}1"

    # ── Data rows ─────────────────────────────────────────────────────────
    fill_a    = PatternFill("solid", start_color="DCE6F1")
    fill_b    = PatternFill("solid", start_color="FFFFFF")
    base_font = Font(name="Arial", size=10)
    center    = Alignment(horizontal="center")
    left      = Alignment(horizontal="left")

    # Highlight top-10 PPG scorers with a gold tint
    ppg_vals  = sorted([r["PPG"] for r in records if r["PPG"] is not None],
                       reverse=True)
    top10_thresh = ppg_vals[9] if len(ppg_vals) >= 10 else 0
    gold_fill = PatternFill("solid", start_color="FFF2CC")

    for row_num, rec in enumerate(records, start=2):
        is_top10 = rec.get("PPG") is not None and rec["PPG"] >= top10_thresh
        fill = gold_fill if is_top10 else (fill_a if row_num % 2 == 0 else fill_b)

        values = [
            rec.get("PLAYER_ID"),
            rec.get("FULL_NAME"),
            rec.get("TEAM"),
            rec.get("GP"),
            rec.get("GS"),
            rec.get("MIN"),
            rec.get("PPG"),
            rec.get("FGM"), rec.get("FGA"), rec.get("FG_PCT"),
            rec.get("FG3M"), rec.get("FG3A"), rec.get("FG3_PCT"),
            rec.get("FTM"), rec.get("FTA"), rec.get("FT_PCT"),
            rec.get("REB"), rec.get("AST"), rec.get("STL"),
            rec.get("BLK"), rec.get("TOV"),
            rec.get("PLUS_MINUS"),
            rec.get("FIRST_BASKET_COUNT"),
        ]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.fill      = fill
            cell.font      = base_font
            cell.alignment = left if col_idx == 2 else center

            # Bold the PPG cell
            if col_idx == 7:
                cell.font = Font(name="Arial", size=10, bold=True)

    wb.save(path)
    print(f"  Saved {len(records)} player rows → {path}")


def add_summary_sheet(path: str, records: list[dict]):
    """Add a Summary tab: PPG leaderboard + first-basket frequency leaders."""
    wb = load_workbook(path)
    if "Summary" in wb.sheetnames:
        del wb["Summary"]
    ws = wb.create_sheet("Summary")

    title_font = Font(name="Arial", bold=True, size=12, color="FFFFFF")
    hdr_fill   = PatternFill("solid", start_color="17375E")
    sub_fill   = PatternFill("solid", start_color="2E74B5")
    sub_font   = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    normal     = Font(name="Arial", size=10)
    bold_f     = Font(name="Arial", bold=True, size=10)
    center     = Alignment(horizontal="center")
    left       = Alignment(horizontal="left")
    fill_a     = PatternFill("solid", start_color="DCE6F1")
    fill_b     = PatternFill("solid", start_color="FFFFFF")
    gold       = PatternFill("solid", start_color="FFF2CC")

    def title_row(col, val, end_col):
        c = ws.cell(row=1, column=col, value=val)
        c.fill = hdr_fill; c.font = title_font; c.alignment = center
        ws.merge_cells(start_row=1, start_column=col,
                       end_row=1, end_column=end_col)

    def sub_row(row, col, val):
        c = ws.cell(row=row, column=col, value=val)
        c.fill = sub_fill; c.font = sub_font; c.alignment = center

    # ── Section A: PPG leaderboard (cols A-C) ────────────────────────────
    title_row(1, "PPG Leaderboard — First Basket Scorers", 3)
    for col, lbl in [(1,"Rank"),(2,"Player"),(3,"PPG")]:
        sub_row(2, col, lbl)

    sorted_by_ppg = sorted(
        [r for r in records if r.get("PPG") is not None],
        key=lambda x: -x["PPG"]
    )
    for rank, rec in enumerate(sorted_by_ppg, 1):
        r = rank + 2
        fill = gold if rank <= 10 else (fill_a if r % 2 == 0 else fill_b)
        ws.cell(row=r, column=1, value=rank).fill = fill
        ws.cell(row=r, column=1).font  = bold_f
        ws.cell(row=r, column=1).alignment = center
        ws.cell(row=r, column=2, value=rec["FULL_NAME"]).fill = fill
        ws.cell(row=r, column=2).font  = normal
        ws.cell(row=r, column=2).alignment = left
        ws.cell(row=r, column=3, value=rec["PPG"]).fill = fill
        ws.cell(row=r, column=3).font  = bold_f
        ws.cell(row=r, column=3).alignment = center

    ws.column_dimensions["A"].width = 7
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 8

    # ── Section B: First basket frequency leaders (cols E-G) ─────────────
    title_row(5, "First Basket Frequency Leaders", 7)
    for col, lbl in [(5,"Rank"),(6,"Player"),(7,"First Baskets")]:
        sub_row(2, col, lbl)

    sorted_by_fb = sorted(
        [r for r in records if r.get("FIRST_BASKET_COUNT", 0) > 0],
        key=lambda x: -x["FIRST_BASKET_COUNT"]
    )
    for rank, rec in enumerate(sorted_by_fb, 1):
        r = rank + 2
        fill = gold if rank <= 10 else (fill_a if r % 2 == 0 else fill_b)
        ws.cell(row=r, column=5, value=rank).fill = fill
        ws.cell(row=r, column=5).font = bold_f; ws.cell(row=r, column=5).alignment = center
        ws.cell(row=r, column=6, value=rec["FULL_NAME"]).fill = fill
        ws.cell(row=r, column=6).font = normal; ws.cell(row=r, column=6).alignment = left
        ws.cell(row=r, column=7, value=rec["FIRST_BASKET_COUNT"]).fill = fill
        ws.cell(row=r, column=7).font = bold_f; ws.cell(row=r, column=7).alignment = center

    ws.column_dimensions["E"].width = 7
    ws.column_dimensions["F"].width = 26
    ws.column_dimensions["G"].width = 14

    ws.freeze_panes = "A3"
    wb.save(path)
    print("  Summary sheet written.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NBA PPG Dataset Builder — pulls season PPG for every "
                    "player mentioned in the first-basket dataset.")
    parser.add_argument("--source", default=SOURCE_FILE,
                        help="First-basket Excel file to read players from")
    parser.add_argument("--output", default=OUTPUT_FILE,
                        help="Output Excel file path")
    args = parser.parse_args()

    # ── 1. Load first-basket dataset ──────────────────────────────────────
    print(f"Reading first-basket dataset: {args.source}")
    if not Path(args.source).exists():
        raise SystemExit(f"Source file not found: {args.source}")
    fb_df = pd.read_excel(args.source, sheet_name="First Baskets")
    print(f"  Loaded {len(fb_df)} game rows.")

    # Count first baskets per player for the bonus column
    fb_counts: dict[str, int] = {}
    for col in ("HOME_FIRST_SCORER", "AWAY_FIRST_SCORER"):
        for name in fb_df[col].dropna():
            name = str(name).strip()
            if name not in ("N/A", "None", "nan", ""):
                fb_counts[name] = fb_counts.get(name, 0) + 1

    # ── 2. Resolve player names → IDs ────────────────────────────────────
    print("\nResolving player names...")
    nameI_map, fullname_map, id_map = build_name_maps()
    resolved = resolve_players(fb_df, nameI_map, fullname_map)
    # resolved: {player_id: {"nameI": str, "full_name": str}}

    # ── 3. Fetch all PPG stats in one API call ────────────────────────────
    print("\nFetching 2025-26 per-game stats...")
    stats_df = fetch_all_ppg(SEASON)

    # Index by player ID for fast lookup
    stats_by_id = {int(row["PLAYER_ID"]): row
                   for _, row in stats_df.iterrows()}

    # ── 4. Build records ──────────────────────────────────────────────────
    print("\nBuilding output records...")
    records = []
    missing_stats = []

    for pid, meta in sorted(resolved.items(),
                             key=lambda kv: kv[1]["full_name"]):
        row = stats_by_id.get(int(pid))
        if row is None:
            missing_stats.append(meta["full_name"])
            # Still include the player, just with null stats
            records.append({
                "PLAYER_ID"          : pid,
                "FULL_NAME"          : meta["full_name"],
                "TEAM"               : None,
                "GP"                 : None,
                "GS"                 : None,
                "MIN"                : None,
                "PPG"                : None,
                "FGM"                : None, "FGA": None, "FG_PCT": None,
                "FG3M"               : None, "FG3A": None, "FG3_PCT": None,
                "FTM"                : None, "FTA": None, "FT_PCT": None,
                "REB"                : None, "AST": None,
                "STL"                : None, "BLK": None, "TOV": None,
                "PLUS_MINUS"         : None,
                "FIRST_BASKET_COUNT" : fb_counts.get(meta["nameI"], 0),
            })
            continue

        def _round(col, digits=1):
            v = row.get(col)
            try:
                return round(float(v), digits)
            except (TypeError, ValueError):
                return v

        records.append({
            "PLAYER_ID"          : pid,
            "FULL_NAME"          : meta["full_name"],
            "TEAM"               : row.get("TEAM_ABBREVIATION"),
            "GP"                 : row.get("GP"),
            "GS"                 : row.get("GS"),
            "MIN"                : _round("MIN"),
            "PPG"                : _round("PTS"),
            "FGM"                : _round("FGM"),
            "FGA"                : _round("FGA"),
            "FG_PCT"             : _round("FG_PCT", 3),
            "FG3M"               : _round("FG3M"),
            "FG3A"               : _round("FG3A"),
            "FG3_PCT"            : _round("FG3_PCT", 3),
            "FTM"                : _round("FTM"),
            "FTA"                : _round("FTA"),
            "FT_PCT"             : _round("FT_PCT", 3),
            "REB"                : _round("REB"),
            "AST"                : _round("AST"),
            "STL"                : _round("STL"),
            "BLK"                : _round("BLK"),
            "TOV"                : _round("TOV"),
            "PLUS_MINUS"         : _round("PLUS_MINUS"),
            "FIRST_BASKET_COUNT" : fb_counts.get(meta["nameI"], 0),
        })

    if missing_stats:
        print(f"\n  Note: {len(missing_stats)} player(s) had no stats entry "
              f"(may be two-way / inactive this season):")
        for n in missing_stats:
            print(f"    {n}")

    # Sort by PPG descending (nulls last)
    records.sort(key=lambda r: (r["PPG"] is None, -(r["PPG"] or 0)))

    # ── 5. Write Excel ────────────────────────────────────────────────────
    print(f"\nWriting Excel → {args.output}")
    write_ppg_excel(records, args.output)
    add_summary_sheet(args.output, records)

    print(f"\n✅  Done!  {len(records)} players written to: {args.output}")
    print(f"    Top 5 PPG: " + ", ".join(
        f"{r['FULL_NAME']} ({r['PPG']})" for r in records[:5] if r['PPG']
    ))


if __name__ == "__main__":
    main()
