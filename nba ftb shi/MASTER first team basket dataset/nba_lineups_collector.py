"""
NBA Starting Lineup Dataset Collector - 2025-26 Season
=======================================================
Pulls box score data from NBA.com for every completed game in the
2025-26 regular season and records the official 5-man starting lineup
for both teams, including each player's listed position.

Two rows are written per game (one per team), giving a full picture of
every lineup combination used across the season.

Run once to build the full dataset, then re-run nightly to append new
games automatically. Already-collected game IDs are skipped.
Any rows with missing/incomplete lineup data are re-attempted on every run.

Requirements:
    pip install nba_api openpyxl pandas

Usage:
    python nba_lineups_collector.py
    python nba_lineups_collector.py --output my_file.xlsx
"""

import argparse
import time
import re
import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from pathlib import Path

try:
    from nba_api.stats.endpoints import leaguegamelog, boxscoretraditionalv3
    from nba_api.stats.static import teams as nba_teams_static
except ImportError:
    raise SystemExit("Missing dependency: pip install nba_api")

OUTPUT_FILE  = "NBA_Lineups_2025-26.xlsx"
SEASON       = "2025-26"
DELAY        = 1.5
MAX_RETRIES  = 5
RETRY_BACKOFF = [5, 15, 30, 60, 120]

# ─── Team lookup maps ─────────────────────────────────────────────────────────

_teams           = nba_teams_static.get_teams()
TEAM_ID_MAP      = {t["id"]: t["abbreviation"] for t in _teams}
TEAM_FULL_MAP    = {t["id"]: t["full_name"]    for t in _teams}
TEAM_ABB_MAP     = {t["abbreviation"]: t["id"] for t in _teams}

# ─── Excel column layout (1-based) ────────────────────────────────────────────

HEADERS = [
    "GAME_ID", "GAME_DATE", "TEAM", "OPPONENT", "HOME_AWAY",
    "STARTER_1", "POS_1",
    "STARTER_2", "POS_2",
    "STARTER_3", "POS_3",
    "STARTER_4", "POS_4",
    "STARTER_5", "POS_5",
]

COL = {h: i for i, h in enumerate(HEADERS, 1)}   # name → 1-based col index

COL_WIDTHS = [14, 12, 8, 8, 10,
              24, 6,
              24, 6,
              24, 6,
              24, 6,
              24, 6]

# ─── API helpers ──────────────────────────────────────────────────────────────

def get_all_completed_games() -> pd.DataFrame:
    """Return a de-duplicated DataFrame of all completed 2025-26 games."""
    print("Fetching season game log...")
    gl = leaguegamelog.LeagueGameLog(
        season=SEASON,
        season_type_all_star="Regular Season",
        player_or_team_abbreviation="T",
    )
    df = gl.get_data_frames()[0]
    time.sleep(DELAY)

    games = df[["GAME_ID", "GAME_DATE", "MATCHUP", "TEAM_ID", "TEAM_ABBREVIATION"]].copy()
    games["IS_HOME"] = games["MATCHUP"].str.contains(r" vs\. ")

    home = games[games["IS_HOME"]].rename(columns={
        "TEAM_ID": "HOME_TEAM_ID", "TEAM_ABBREVIATION": "HOME_TEAM"})
    away = games[~games["IS_HOME"]].rename(columns={
        "TEAM_ID": "AWAY_TEAM_ID", "TEAM_ABBREVIATION": "AWAY_TEAM"})

    merged = home.merge(
        away[["GAME_ID", "AWAY_TEAM_ID", "AWAY_TEAM"]], on="GAME_ID"
    )[["GAME_ID", "GAME_DATE", "HOME_TEAM_ID", "HOME_TEAM",
       "AWAY_TEAM_ID", "AWAY_TEAM"]]
    merged = (merged.drop_duplicates("GAME_ID")
                    .sort_values("GAME_DATE")
                    .reset_index(drop=True))
    print(f"  Found {len(merged)} completed games.")
    return merged


def get_starters(game_id: str) -> dict:
    """
    Fetch BoxScoreTraditionalV3 and return starters for both teams.

    Returns:
        {
          team_tricode: [{"name": str, "pos": str}, ...],   # list of 5
          ...
        }
        Empty dict on failure.
    """
    players_df = None
    for attempt in range(MAX_RETRIES):
        try:
            bs = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            # PlayerStats is the first data frame
            players_df = bs.get_data_frames()[0]
            time.sleep(DELAY)
            break
        except Exception as e:
            err = str(e)
            is_retryable = any(k in err.lower() for k in
                               ["timed out", "timeout", "429", "rate"])
            if is_retryable and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"    TIMEOUT/RATE-LIMIT (attempt {attempt+1}/{MAX_RETRIES})"
                      f" — waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    ERROR fetching box score for {game_id}: {e}")
                return {}

    if players_df is None or players_df.empty:
        print(f"    WARNING: empty box score for {game_id}")
        return {}

    # Starters have a non-empty 'position' field (G, F, C, G-F, F-C …)
    starters = players_df[players_df["position"].notna() &
                          (players_df["position"].str.strip() != "")].copy()

    result = {}
    for tricode, group in starters.groupby("teamTricode"):
        # Sort by jersey number for a consistent ordering
        group = group.sort_values("jerseyNum")
        lineup = [
            {
                "name": f"{row['firstName']} {row['familyName']}".strip(),
                "pos" : row["position"].strip(),
            }
            for _, row in group.iterrows()
        ]
        if len(lineup) == 5:
            result[tricode] = lineup
        elif lineup:
            # Partial — still store what we have, padded with blanks
            while len(lineup) < 5:
                lineup.append({"name": "", "pos": ""})
            result[tricode] = lineup

    return result


# ─── Excel I/O ────────────────────────────────────────────────────────────────

def load_existing_ids(path: str) -> set:
    """Return the set of GAME_IDs already present in the file (any row)."""
    p = Path(path)
    if not p.exists():
        return set()
    wb = load_workbook(p, read_only=True)
    ws = wb.active
    hdrs = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    if "GAME_ID" not in hdrs:
        wb.close()
        return set()
    idx = hdrs.index("GAME_ID")
    ids = {row[idx].value for row in ws.iter_rows(min_row=2) if row[idx].value}
    wb.close()
    return ids


def load_incomplete_rows(path: str) -> list[dict]:
    """
    Scan for rows where STARTER_1 is blank / None — meaning the lineup
    fetch failed previously and should be retried.
    Returns list of dicts with row_num, game_id, team, opponent, home_away.
    """
    p = Path(path)
    if not p.exists():
        return []
    wb = load_workbook(p, read_only=True)
    ws  = wb.active
    hdrs = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    col  = {h: i for i, h in enumerate(hdrs)}

    needed = {"GAME_ID", "TEAM", "OPPONENT", "HOME_AWAY", "STARTER_1"}
    if not needed.issubset(col):
        wb.close()
        return []

    incomplete = []
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        def v(key):
            val = row[col[key]]
            return str(val).strip() if val is not None else ""

        s1 = v("STARTER_1")
        if s1 in ("", "N/A", "None"):
            incomplete.append({
                "row_num"  : row_num,
                "game_id"  : v("GAME_ID"),
                "game_date": v("GAME_DATE"),
                "team"     : v("TEAM"),
                "opponent" : v("OPPONENT"),
                "home_away": v("HOME_AWAY"),
            })
    wb.close()
    return incomplete


def _row_fill(row_num: int) -> PatternFill:
    c = "DCE6F1" if row_num % 2 == 0 else "FFFFFF"
    return PatternFill("solid", start_color=c)


def _build_row_values(game_id, game_date, team, opponent,
                      home_away, lineup: list) -> list:
    """Build the 15-element list matching HEADERS order."""
    row = [game_id, game_date, team, opponent, home_away]
    for i in range(5):
        if i < len(lineup):
            row.append(lineup[i]["name"])
            row.append(lineup[i]["pos"])
        else:
            row.append("")
            row.append("")
    return row


def _write_cells(ws, row_num: int, values: list):
    fill      = _row_fill(row_num)
    base_font = Font(name="Arial", size=10)
    center    = Alignment(horizontal="center", wrap_text=False)
    left      = Alignment(horizontal="left")

    for col_idx, val in enumerate(values, 1):
        c = ws.cell(row=row_num, column=col_idx, value=val)
        c.fill      = fill
        c.font      = base_font
        # Player name columns get left-aligned; everything else centered
        c.alignment = left if col_idx in (6, 8, 10, 12, 14) else center


def create_or_open_workbook(path: str):
    """Return (wb, ws, next_row). Creates headers if file is new."""
    p = Path(path)
    if p.exists():
        wb = load_workbook(p)
        ws = wb["Lineups"]
        return wb, ws, ws.max_row + 1

    wb = Workbook()
    ws = wb.active
    ws.title = "Lineups"

    hdr_fill = PatternFill("solid", start_color="17375E")
    hdr_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, h in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill      = hdr_fill
        cell.font      = hdr_font
        cell.alignment = hdr_align

    for i, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}1"

    return wb, ws, 2


def write_records(records: list[dict], path: str):
    """Append a batch of lineup records to the Excel file."""
    if not records:
        return
    wb, ws, start_row = create_or_open_workbook(path)

    for i, rec in enumerate(records):
        row_num = start_row + i
        values  = _build_row_values(
            rec["game_id"], rec["game_date"],
            rec["team"],    rec["opponent"], rec["home_away"],
            rec.get("lineup", []),
        )
        _write_cells(ws, row_num, values)

    wb.save(path)
    print(f"  Saved {len(records)} rows → {path}")


def patch_row(path: str, row_num: int, lineup: list):
    """Overwrite starter columns in an existing row."""
    wb = load_workbook(path)
    ws = wb["Lineups"]
    fill      = _row_fill(row_num)
    base_font = Font(name="Arial", size=10)
    center    = Alignment(horizontal="center")
    left      = Alignment(horizontal="left")

    for i, starter in enumerate(lineup[:5]):
        name_col = COL[f"STARTER_{i+1}"]
        pos_col  = COL[f"POS_{i+1}"]
        cn = ws.cell(row=row_num, column=name_col, value=starter["name"])
        cn.fill = fill; cn.font = base_font; cn.alignment = left
        cp = ws.cell(row=row_num, column=pos_col,  value=starter["pos"])
        cp.fill = fill; cp.font = base_font; cp.alignment = center

    wb.save(path)


# ─── Summary sheet ────────────────────────────────────────────────────────────

def refresh_summary(path: str):
    """
    Rebuild the Summary sheet with:
      - Most-used starting lineup per team
      - Player appearance counts as a starter
    """
    wb = load_workbook(path)
    if "Summary" in wb.sheetnames:
        del wb["Summary"]

    data_ws = wb["Lineups"]
    rows = list(data_ws.iter_rows(min_row=2, values_only=True))

    # ── per-team lineup frequency ──────────────────────────────────────────
    team_lineups: dict[str, dict[str, int]] = {}   # team → {lineup_str: count}
    player_starts: dict[str, dict[str, int]] = {}  # team → {player: count}

    for row in rows:
        team = str(row[COL["TEAM"] - 1]).strip()
        if not team or team == "None":
            continue

        starters = []
        for i in range(1, 6):
            s = row[COL[f"STARTER_{i}"] - 1]
            starters.append(str(s).strip() if s else "")

        if all(starters):
            lineup_key = " | ".join(sorted(starters))
            team_lineups.setdefault(team, {})
            team_lineups[team][lineup_key] = \
                team_lineups[team].get(lineup_key, 0) + 1

        team_starts = player_starts.setdefault(team, {})
        for s in starters:
            if s:
                team_starts[s] = team_starts.get(s, 0) + 1

    ws = wb.create_sheet("Summary")

    # ── Styles ────────────────────────────────────────────────────────────
    title_font  = Font(name="Arial", bold=True, size=12, color="FFFFFF")
    hdr_fill    = PatternFill("solid", start_color="17375E")
    sub_fill    = PatternFill("solid", start_color="2E74B5")
    sub_font    = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    normal      = Font(name="Arial", size=10)
    bold        = Font(name="Arial", bold=True, size=10)
    center      = Alignment(horizontal="center")
    left        = Alignment(horizontal="left")
    fill_a      = PatternFill("solid", start_color="DCE6F1")
    fill_b      = PatternFill("solid", start_color="FFFFFF")

    def hdr_cell(ws, r, c, val, span_end=None):
        cell = ws.cell(row=r, column=c, value=val)
        cell.fill = hdr_fill; cell.font = title_font; cell.alignment = center
        if span_end:
            ws.merge_cells(
                start_row=r, start_column=c, end_row=r, end_column=span_end)
        return cell

    def sub_cell(ws, r, c, val):
        cell = ws.cell(row=r, column=c, value=val)
        cell.fill = sub_fill; cell.font = sub_font; cell.alignment = center

    # ── Section 1: Most common starting 5 per team  (cols A–C) ───────────
    hdr_cell(ws, 1, 1, "Most Common Starting Lineup Per Team", span_end=3)
    sub_cell(ws, 2, 1, "Team")
    sub_cell(ws, 2, 2, "Lineup (sorted alphabetically)")
    sub_cell(ws, 2, 3, "Times Used")

    sorted_teams = sorted(team_lineups.keys())
    for r_off, team in enumerate(sorted_teams, start=3):
        if team_lineups[team]:
            top_lineup, count = max(
                team_lineups[team].items(), key=lambda x: x[1])
        else:
            top_lineup, count = "—", 0
        fill = fill_a if r_off % 2 == 0 else fill_b
        c1 = ws.cell(row=r_off, column=1, value=team)
        c1.font = bold; c1.fill = fill; c1.alignment = center
        c2 = ws.cell(row=r_off, column=2, value=top_lineup)
        c2.font = normal; c2.fill = fill; c2.alignment = left
        c3 = ws.cell(row=r_off, column=3, value=count)
        c3.font = normal; c3.fill = fill; c3.alignment = center

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 80
    ws.column_dimensions["C"].width = 12

    # ── Section 2: Player starter appearance counts (cols E–G) ───────────
    hdr_cell(ws, 1, 5, "Player Starting Appearances", span_end=7)
    sub_cell(ws, 2, 5, "Team")
    sub_cell(ws, 2, 6, "Player")
    sub_cell(ws, 2, 7, "Games Started")

    r = 3
    for team in sorted_teams:
        if team not in player_starts:
            continue
        sorted_players = sorted(
            player_starts[team].items(), key=lambda x: -x[1])
        for player, cnt in sorted_players:
            fill = fill_a if r % 2 == 0 else fill_b
            c5 = ws.cell(row=r, column=5, value=team)
            c5.font = bold; c5.fill = fill; c5.alignment = center
            c6 = ws.cell(row=r, column=6, value=player)
            c6.font = normal; c6.fill = fill; c6.alignment = left
            c7 = ws.cell(row=r, column=7, value=cnt)
            c7.font = normal; c7.fill = fill; c7.alignment = center
            r += 1

    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 28
    ws.column_dimensions["G"].width = 16

    ws.freeze_panes = "A3"
    wb.save(path)
    print("  Summary sheet refreshed.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NBA Starting Lineup Dataset Builder — 2025-26")
    parser.add_argument("--output", default=OUTPUT_FILE,
                        help="Output Excel file path")
    args   = parser.parse_args()
    output = args.output

    # ── Step 1: Collect new games ──────────────────────────────────────────
    existing_ids = load_existing_ids(output)
    print(f"Already collected: {len(existing_ids)} games ({len(existing_ids) * 2} rows).")

    games_df  = get_all_completed_games()
    new_games = games_df[~games_df["GAME_ID"].isin(existing_ids)]
    print(f"New games to process: {len(new_games)}")

    if not new_games.empty:
        new_records = []

        for i, (_, game) in enumerate(new_games.iterrows(), 1):
            gid      = game["GAME_ID"]
            date     = game["GAME_DATE"]
            home_abb = game["HOME_TEAM"]
            away_abb = game["AWAY_TEAM"]
            print(f"  [{i}/{len(new_games)}] {date} | "
                  f"{away_abb} @ {home_abb}  (ID: {gid})")

            starters = get_starters(gid)

            # Build one record per team (2 per game)
            for team_abb, opp_abb, ha in [
                (home_abb, away_abb, "HOME"),
                (away_abb, home_abb, "AWAY"),
            ]:
                lineup = starters.get(team_abb, [])
                if not lineup:
                    print(f"    WARNING: no starters found for {team_abb}")
                new_records.append({
                    "game_id"  : gid,
                    "game_date": date,
                    "team"     : team_abb,
                    "opponent" : opp_abb,
                    "home_away": ha,
                    "lineup"   : lineup,
                })

            # Crash-safe: flush every 25 games (50 rows)
            if len(new_records) >= 50:
                write_records(new_records, output)
                new_records = []

        if new_records:
            write_records(new_records, output)
    else:
        print("No new games to add.")

    # ── Step 2: Backfill any rows with missing lineup data ────────────────
    incomplete = load_incomplete_rows(output)
    if incomplete:
        # Group by game_id so we only fetch each game's box score once
        by_game: dict[str, list] = {}
        for inc in incomplete:
            by_game.setdefault(inc["game_id"], []).append(inc)

        print(f"\nFound {len(incomplete)} rows with missing lineups "
              f"across {len(by_game)} games — backfilling...")
        filled = 0

        for j, (gid, rows) in enumerate(by_game.items(), 1):
            sample = rows[0]
            print(f"  [{j}/{len(by_game)}] {sample['game_date']} | "
                  f"game {gid}")

            starters = get_starters(gid)
            if not starters:
                print(f"    Still unavailable — skipping.")
                continue

            for inc in rows:
                team_abb = inc["team"]
                lineup   = starters.get(team_abb)
                if not lineup:
                    print(f"    No starters for {team_abb} in this game.")
                    continue
                patch_row(output, inc["row_num"], lineup)
                filled += 1

        print(f"  Backfill complete: {filled}/{len(incomplete)} rows updated.")
    else:
        print("\nNo incomplete rows — dataset is fully populated.")

    # ── Step 3: Refresh summary ────────────────────────────────────────────
    print("Refreshing summary sheet...")
    refresh_summary(output)
    print(f"\n✅  Done!  Dataset saved to: {output}")


if __name__ == "__main__":
    main()
