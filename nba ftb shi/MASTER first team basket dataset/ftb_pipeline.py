"""
FTB PbP Data Engine v2 — Excel Integration Pipeline
====================================================
Processes the NBA_First_Basket_2025-26.xlsx dataset and produces:
  1.  ftb_data_output.json  — drop-in replacement for localStorage "ftb-engine-v4" key
  2.  season_ftb_patch.js   — JS constant snippet to replace SEASON_FTB_DATA in the HTML

The output schema is fully compatible with the existing app pipeline:
  playerFtb  → { [fullName]: { ftbMade, gamesStarted, firstShotRate, shots, position, team } }
  teamStats  → { [abbr]:    { games, tipPct, firstPointPct, firstFGPct } }
  positionData → { [abbr]: { PG, SG, SF, PF, C, totalGames } }   (defending-team breakdown)

Usage:
  python ftb_pipeline.py [--xlsx path] [--roster path] [--out-dir path] [--verbose]

Author: FTB Scout Pro pipeline (auto-generated)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ─── Logging setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ftb_pipeline")


# ─── Constants ───────────────────────────────────────────────────────────────

EXCEL_SHEET = "First Baskets"

# Standard shot-type keys that match the app's internal schema
SHOT_KEYS = ("layup", "dunk", "mid", "threeP", "ft", "tip", "hook")

# All 30 NBA team abbreviations in the pipeline's canonical form
ALL_TEAMS = [
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
]

# Minimum games-started threshold for Bayesian base-rate to kick in
MIN_GAMES_BAYESIAN = 3

# Required columns in the Excel sheet
REQUIRED_COLS = [
    "GAME_ID", "GAME_DATE",
    "HOME_TEAM", "AWAY_TEAM",
    "HOME_FIRST_SCORER", "HOME_SHOT_DESC",
    "AWAY_FIRST_SCORER", "AWAY_SHOT_DESC",
    "HOME_POINTS", "HOME_TIME",
    "AWAY_FIRST_SCORER", "AWAY_SHOT_DESC", "AWAY_POINTS", "AWAY_TIME",
]

# Maps player position abbreviations to the 5 standard codes
POS_NORMALIZE = {
    "PG": "PG", "POINT GUARD": "PG", "G": "PG",
    "SG": "SG", "SHOOTING GUARD": "SG",
    "SF": "SF", "SMALL FORWARD": "SF", "F": "SF",
    "PF": "PF", "POWER FORWARD": "PF",
    "C":  "C",  "CENTER": "C",
    # Common hybrid designations → best primary position
    "G/F": "SG", "F/G": "SF", "F/C": "PF", "C/F": "C",
}

# ─── Shot-type classification ─────────────────────────────────────────────────

# Each rule is (pattern, shot_type).  Evaluated in order; first match wins.
SHOT_RULES: List[Tuple[re.Pattern, str]] = [
    # NBA.com description keywords (evaluated first because they are more specific)
    (re.compile(r"\balley.?oop\b",              re.I), "dunk"),
    (re.compile(r"\bdunk\b",                    re.I), "dunk"),
    (re.compile(r"\blayup\b|\blay.up\b|\bfinger.roll\b|\bcutting\b", re.I), "layup"),
    (re.compile(r"\bdriving\b.*\blayup\b",      re.I), "layup"),
    (re.compile(r"\b(hook)\b",                  re.I), "hook"),
    (re.compile(r"\btip.?in\b|\btip.?shot\b|\btip\b", re.I), "tip"),
    (re.compile(r"\bfree.throw\b",              re.I), "ft"),
    # 3-point detection — covers both formats
    (re.compile(r"3pt\b|3-point|\bthree.point|\bthree pt\b|3PT Jump", re.I), "threeP"),
    (re.compile(r"three point jumper|three point shot", re.I), "threeP"),
    # ESPN "makes 26-foot three point" format
    (re.compile(r"\d+-foot three",              re.I), "threeP"),
    # Running / floating / step-back / pull-up → mid-range
    (re.compile(r"\bfloating\b|\bstep.back\b|\bfadeaway\b|\bpull.up\b|\brunning\b", re.I), "mid"),
    # Generic jump shot → mid
    (re.compile(r"\bjump.shot\b|\bjumper\b|\b\d+.foot\b", re.I), "mid"),
]

def classify_shot(description: Optional[str]) -> str:
    """
    Return one of {dunk, layup, hook, tip, ft, threeP, mid} from a shot description.

    Handles both ESPN narrative format ("makes 13-foot two point shot") and
    NBA.com PbP format ("Doncic 13' Driving Floating Jump Shot (2 PTS)").
    Falls back to "mid" for any unrecognised description.
    """
    if not description or not isinstance(description, str):
        return "mid"
    for pattern, shot_type in SHOT_RULES:
        if pattern.search(description):
            return shot_type
    return "mid"  # default: unclassified jump shot / mid-range


# ─── Name normalisation ───────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    """Remove diacritics so Jokić == Jokic, Vučević == Vucevic, etc."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def build_roster_index(roster_path: Path) -> Tuple[Dict[str, List[dict]], Dict[str, List[dict]]]:
    """
    Load player_roster.json and return two lookup dictionaries:

      by_abbrev[abbreviated_name_normalised] → player dict
      by_full[full_name_normalised]          → player dict

    Normalised = stripped accents, lower-cased, whitespace-collapsed.
    """
    with roster_path.open(encoding="utf-8") as fh:
        roster_json = json.load(fh)

    by_abbrev: Dict[str, List[dict]] = {}
    by_full:   Dict[str, List[dict]] = {}

    for player in roster_json["players"]:
        abbr_key = _strip_accents(player["abbreviated"]).lower().strip()
        full_key = _strip_accents(player["full_name"]).lower().strip()
        by_abbrev.setdefault(abbr_key, []).append(player)
        by_full.setdefault(full_key, []).append(player)

    abbrev_collisions = sum(1 for v in by_abbrev.values() if len(v) > 1)
    full_collisions = sum(1 for v in by_full.values() if len(v) > 1)
    log.info(
        "Roster loaded: %d entries (%d abbreviated keys, %d full-name keys, %d abbrev collisions, %d full-name collisions)",
        len(roster_json["players"]),
        len(by_abbrev),
        len(by_full),
        abbrev_collisions,
        full_collisions
    )
    return by_abbrev, by_full


def resolve_player(
    raw_name: str,
    team: str,
    by_abbrev: Dict[str, List[dict]],
    by_full: Dict[str, List[dict]],
) -> Tuple[str, str, bool]:
    """
    Resolve a raw name (may be abbreviated or full) to (full_name, position, found).

    Resolution order:
      1. Exact match on abbreviated key (team-independent — most names are unique)
      2. Exact match on full-name key
      3. Partial match: does the raw name end in the last token of any abbreviated key?
         (handles minor formatting differences)
      4. Returns (raw_name, "UNK", False) with a warning if nothing matches.
    """
    norm = _strip_accents(raw_name).lower().strip()

    # 1. Direct abbreviated match
    if norm in by_abbrev:
        candidates = by_abbrev[norm]
        if len(candidates) == 1:
            p = candidates[0]
            return p["full_name"], p["position"], True
        team_match = [p for p in candidates if p.get("primary_team") == team]
        if len(team_match) == 1:
            p = team_match[0]
            return p["full_name"], p["position"], True
        log.warning("AMBIGUOUS abbreviated name: '%s' (team=%s) — %d candidates", raw_name, team, len(candidates))
        return raw_name, "UNK", False

    # 2. Full-name match
    if norm in by_full:
        candidates = by_full[norm]
        if len(candidates) == 1:
            p = candidates[0]
            return p["full_name"], p["position"], True
        team_match = [p for p in candidates if p.get("primary_team") == team]
        if len(team_match) == 1:
            p = team_match[0]
            return p["full_name"], p["position"], True
        log.warning("AMBIGUOUS full name: '%s' (team=%s) — %d candidates", raw_name, team, len(candidates))
        return raw_name, "UNK", False

    # 3. Fuzzy: last name + suffix match
    last_token = norm.split()[-1] if norm.split() else ""
    if last_token:
        candidates = [
            p
            for key, players in by_abbrev.items()
            if key.split()[-1] == last_token
            for p in players
        ]
        if len(candidates) == 1:
            p = candidates[0]
            log.debug("Fuzzy match: '%s' → '%s' (via last-name)", raw_name, p["full_name"])
            return p["full_name"], p["position"], True
        if len(candidates) > 1:
            # Disambiguate by team
            team_match = [p for p in candidates if p.get("primary_team") == team]
            if len(team_match) == 1:
                p = team_match[0]
                log.debug("Fuzzy+team match: '%s'@%s → '%s'", raw_name, team, p["full_name"])
                return p["full_name"], p["position"], True

    log.warning("UNRESOLVED player: '%s' (team=%s) — position will be UNK", raw_name, team)
    return raw_name, "UNK", False


# ─── Excel ingestion ──────────────────────────────────────────────────────────

def ingest_excel(xlsx_path: Path) -> pd.DataFrame:
    """
    Read the 'First Baskets' sheet and validate required columns.
    Returns a DataFrame with clean dtypes and no fully-null rows.
    """
    log.info("Reading Excel: %s", xlsx_path)
    df = pd.read_excel(xlsx_path, sheet_name=EXCEL_SHEET)

    # Validate columns
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Excel: {missing}")

    before = len(df)
    # Drop rows where both scorer cells are missing
    df = df.dropna(subset=["HOME_FIRST_SCORER", "AWAY_FIRST_SCORER"], how="all")
    after = len(df)
    if before != after:
        log.warning("Dropped %d rows with no scorer data", before - after)

    log.info("Ingested %d game rows (columns: %s)", after, list(df.columns))
    return df


# ─── Clock → seconds conversion ───────────────────────────────────────────────

def clock_to_seconds(clock_str: Optional[str]) -> Optional[float]:
    """Convert 'MM:SS' game clock to total seconds remaining."""
    if not isinstance(clock_str, str):
        return None
    m = re.match(r"(\d{1,2}):(\d{2})", clock_str.strip())
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


# ─── Team-level stats computation ─────────────────────────────────────────────

def compute_team_stats(df: pd.DataFrame) -> Dict[str, dict]:
    """
    Derive per-team FTB statistics from the raw game DataFrame.

    Returns teamStats[abbr] = {
        games, firstFGWins, firstFGPct,
        firstPointPct (same as firstFGPct since no FT data),
        tipPct (set to firstFGPct as proxy — tip data not in dataset)
    }
    """
    team_games:      Dict[str, int] = defaultdict(int)
    team_ftg_wins:   Dict[str, int] = defaultdict(int)

    for _, row in df.iterrows():
        home = row.get("HOME_TEAM")
        away = row.get("AWAY_TEAM")
        if not home or not away:
            continue

        home_sec = clock_to_seconds(row.get("HOME_TIME"))
        away_sec = clock_to_seconds(row.get("AWAY_TIME"))

        team_games[home] += 1
        team_games[away] += 1

        if home_sec is not None and away_sec is not None:
            # Higher seconds remaining = earlier in game = scored first
            if home_sec > away_sec:
                team_ftg_wins[home] += 1
            elif away_sec > home_sec:
                team_ftg_wins[away] += 1
            # exact tie: neither credited (rare)

    team_stats = {}
    for team in ALL_TEAMS:
        games = team_games.get(team, 0)
        if games == 0:
            continue
        wins = team_ftg_wins.get(team, 0)
        pct = round(wins / games * 100, 1)
        team_stats[team] = {
            "games":          games,
            "firstFGWins":    wins,
            "firstFGPct":     pct,
            "firstPointPct":  pct,      # same source; FT-only openers not in dataset
            "tipPct":         pct,      # proxy: no raw tip data in this dataset
        }

    log.info("Team stats computed for %d teams", len(team_stats))
    return team_stats


# ─── Event extraction ─────────────────────────────────────────────────────────

def build_events(
    df: pd.DataFrame,
    by_abbrev: Dict[str, dict],
    by_full: Dict[str, dict],
) -> Tuple[List[dict], dict]:
    """
    Expand each game row into two event dicts (one per team's first scorer).

    Returns:
        events  — list of event dicts
        resolve_stats — summary counts for the validation report
    """
    events: List[dict] = []

    resolve_stats = {
        "total_events": 0,
        "resolved": 0,
        "unresolved": 0,
        "pos_unk": 0,
    }

    for _, row in df.iterrows():
        game_id   = str(row.get("GAME_ID", "")).strip()
        game_date = str(row.get("GAME_DATE", "")).strip()
        home_team = str(row.get("HOME_TEAM", "")).strip()
        away_team = str(row.get("AWAY_TEAM", "")).strip()

        # -- Home team first scorer ------------------------------------------
        home_scorer = row.get("HOME_FIRST_SCORER")
        if pd.notna(home_scorer) and isinstance(home_scorer, str) and home_scorer.strip():
            full, pos, found = resolve_player(home_scorer.strip(), home_team, by_abbrev, by_full)
            shot_type = classify_shot(row.get("HOME_SHOT_DESC"))
            points    = row.get("HOME_POINTS")
            clock     = row.get("HOME_TIME")

            # Infer threeP from POINTS if shot classifier returns mid
            if shot_type == "mid" and pd.notna(points) and int(points) == 3:
                shot_type = "threeP"

            events.append({
                "game_id":       game_id,
                "game_date":     game_date,
                "scoring_team":  home_team,
                "defending_team": away_team,
                "player":        full,
                "position":      pos,
                "shot_type":     shot_type,
                "points":        int(points) if pd.notna(points) else None,
                "clock":         str(clock).strip() if pd.notna(clock) else "",
                "period":        1,
                "source":        "xlsx",
            })

            resolve_stats["total_events"] += 1
            if found: resolve_stats["resolved"] += 1
            else:     resolve_stats["unresolved"] += 1
            if pos == "UNK": resolve_stats["pos_unk"] += 1

        # -- Away team first scorer ------------------------------------------
        away_scorer = row.get("AWAY_FIRST_SCORER")
        if pd.notna(away_scorer) and isinstance(away_scorer, str) and away_scorer.strip():
            full, pos, found = resolve_player(away_scorer.strip(), away_team, by_abbrev, by_full)
            shot_type = classify_shot(row.get("AWAY_SHOT_DESC"))
            points    = row.get("AWAY_POINTS")
            clock     = row.get("AWAY_TIME")

            if shot_type == "mid" and pd.notna(points) and int(points) == 3:
                shot_type = "threeP"

            events.append({
                "game_id":        game_id,
                "game_date":      game_date,
                "scoring_team":   away_team,
                "defending_team": home_team,
                "player":         full,
                "position":       pos,
                "shot_type":      shot_type,
                "points":         int(points) if pd.notna(points) else None,
                "clock":          str(clock).strip() if pd.notna(clock) else "",
                "period":         1,
                "source":         "xlsx",
            })

            resolve_stats["total_events"] += 1
            if found: resolve_stats["resolved"] += 1
            else:     resolve_stats["unresolved"] += 1
            if pos == "UNK": resolve_stats["pos_unk"] += 1

    log.info("Events extracted: %d total", len(events))
    return events, resolve_stats


# ─── Player FTB aggregation ───────────────────────────────────────────────────

def aggregate_player_ftb(
    events: List[dict],
    df: pd.DataFrame,
) -> Dict[str, dict]:
    """
    Build the playerFtb dict consumed by computeFtbProb() in the app.

    Schema per player:
      ftbMade      — count of first-team baskets scored
      gamesStarted — total games played by player's team (proxy for games started)
      firstShotRate — ftbMade / gamesStarted (probability of being first scorer)
      shots        — { layup, dunk, mid, threeP, ft, tip, hook } counts
      position     — NBA position abbreviation (PG / SG / SF / PF / C)
      team         — most-recent team abbreviation
    """
    # Precompute total games per team from the dataset
    team_total_games: Dict[str, int] = defaultdict(int)
    for _, row in df.iterrows():
        home = str(row.get("HOME_TEAM", "")).strip()
        away = str(row.get("AWAY_TEAM", "")).strip()
        if home: team_total_games[home] += 1
        if away: team_total_games[away] += 1

    player_data: Dict[str, dict] = {}

    for ev in events:
        name = ev["player"]
        if not name:
            continue

        if name not in player_data:
            player_data[name] = {
                "ftbMade":     0,
                "gamesStarted": 0,   # filled in below
                "shots":       {k: 0 for k in SHOT_KEYS},
                "position":    ev["position"],
                "team":        ev["scoring_team"],
            }

        rec = player_data[name]
        rec["ftbMade"] += 1

        # Track most-recent team (last entry wins for traded players)
        rec["team"]     = ev["scoring_team"]
        rec["position"] = ev["position"]

        st = ev.get("shot_type", "mid")
        if st not in SHOT_KEYS:
            st = "mid"
        rec["shots"][st] += 1

    # Fill gamesStarted = team games played (all starters / rotation players)
    for name, rec in player_data.items():
        team = rec["team"]
        gs = team_total_games.get(team, rec["ftbMade"])
        rec["gamesStarted"] = gs

    # Compute firstShotRate for each player
    for rec in player_data.values():
        gs = max(rec["gamesStarted"], 1)
        rec["firstShotRate"] = round(rec["ftbMade"] / gs, 4)

    log.info("Player FTB aggregation: %d unique players", len(player_data))
    return player_data


# ─── Position-vs-defending-team breakdown ─────────────────────────────────────

def aggregate_position_data(events: List[dict]) -> Dict[str, dict]:
    """
    Build positionData[team] = { PG, SG, SF, PF, C, totalGames }.
    Each value is the percentage (0-100) of first-baskets AGAINST that team
    scored by players at each position.

    This feeds computePositionLikelihood() in the app.
    """
    counts: Dict[str, Dict[str, int]] = {
        t: {pos: 0 for pos in ["PG", "SG", "SF", "PF", "C", "unknown"]}
        for t in ALL_TEAMS
    }

    for ev in events:
        def_team = ev.get("defending_team", "")
        pos      = ev.get("position", "UNK")
        if def_team not in counts:
            continue
        std_pos = pos if pos in ["PG", "SG", "SF", "PF", "C"] else "unknown"
        counts[def_team][std_pos] += 1

    pos_result: Dict[str, dict] = {}
    for team, raw in counts.items():
        known = raw["PG"] + raw["SG"] + raw["SF"] + raw["PF"] + raw["C"]
        if known < MIN_GAMES_BAYESIAN:
            continue
        pos_result[team] = {
            "PG":         round(raw["PG"] / known * 100),
            "SG":         round(raw["SG"] / known * 100),
            "SF":         round(raw["SF"] / known * 100),
            "PF":         round(raw["PF"] / known * 100),
            "C":          round(raw["C"]  / known * 100),
            "totalGames": known,
        }

    log.info("Position data computed for %d defending teams", len(pos_result))
    return pos_result


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_output(
    player_ftb:    Dict[str, dict],
    team_stats:    Dict[str, dict],
    pos_data:      Dict[str, dict],
    resolve_stats: dict,
) -> None:
    """
    Verify the processed data meets quality thresholds.
    Logs warnings rather than raising exceptions so the pipeline continues.
    """
    log.info("─── VALIDATION REPORT ───────────────────────────────────────────")

    # Events
    total = resolve_stats["total_events"]
    res   = resolve_stats["resolved"]
    unres = resolve_stats["unresolved"]
    unk   = resolve_stats["pos_unk"]
    log.info("Events:        %d total  |  %d resolved (%.1f%%)  |  %d unresolved",
             total, res, (res / total * 100) if total else 0, unres)

    if unres > 0:
        log.warning("  %d players could not be matched in roster — "
                    "check player_roster.json for missing entries", unres)

    # Positions
    log.info("Players:       %d unique  |  %d with UNK position",
             len(player_ftb), unk)
    if unk > 0:
        log.warning("  %d player entries lack a valid position — "
                    "downstream positionData accuracy may be reduced", unk)
    unk_players = [n for n, r in player_ftb.items() if r.get("position") == "UNK"]
    if unk_players:
        log.warning("  UNK position players: %s", unk_players)

    # Teams
    missing_teams = [t for t in ALL_TEAMS if t not in team_stats]
    if missing_teams:
        log.warning("  Missing team stats for: %s", missing_teams)
    else:
        log.info("Team stats:    all 30 teams present ✓")

    # positionData coverage
    log.info("Position data: %d / 30 defending teams", len(pos_data))

    # FTB count sanity
    top5 = sorted(player_ftb.items(), key=lambda x: -x[1]["ftbMade"])[:5]
    log.info("Top 5 FTB scorers:")
    for name, rec in top5:
        shots_str = ", ".join(
            f"{k}:{v}" for k, v in rec["shots"].items() if v > 0
        )
        log.info("  %-30s  %2d FTBs  [%s]  pos=%s  team=%s  rate=%.1f%%",
                 name, rec["ftbMade"], shots_str, rec["position"],
                 rec["team"], rec["firstShotRate"] * 100)

    log.info("─────────────────────────────────────────────────────────────────")


# ─── JS constant generator ────────────────────────────────────────────────────

def _shots_to_js(shots: dict) -> str:
    """Render shot counts as a compact JS object literal."""
    return (
        "{ "
        f"layup: {shots['layup']}, dunk: {shots['dunk']}, mid: {shots['mid']}, "
        f"threeP: {shots['threeP']}, ft: {shots['ft']}, tip: {shots['tip']}, hook: {shots['hook']}"
        " }"
    )


def generate_js_constant(player_ftb: Dict[str, dict]) -> str:
    """
    Render playerFtb as the SEASON_FTB_DATA JavaScript constant that can be
    pasted directly into the HTML to replace the hardcoded static data.
    Sorted descending by ftbMade so high-volume players appear first.
    """
    lines = ["// AUTO-GENERATED by ftb_pipeline.py — do not edit manually",
             "// Source: NBA_First_Basket_2025-26.xlsx",
             f"// Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
             "const SEASON_FTB_DATA = {"]

    sorted_players = sorted(player_ftb.items(), key=lambda x: -x[1]["ftbMade"])

    prev_tier = None
    tier_labels = {10: "TOP TIER (10+ FTBs)", 6: "MID TIER (6–9 FTBs)", 1: "LOW TIER (1–5 FTBs)"}

    for name, rec in sorted_players:
        ftb = rec["ftbMade"]
        tier = 10 if ftb >= 10 else (6 if ftb >= 6 else 1)
        if tier != prev_tier:
            lines.append(f"\n  // ── {tier_labels[tier]} ───────────────────────────────────────────")
            prev_tier = tier

        js_name = name.replace('"', '\\"')
        shots_js = _shots_to_js(rec["shots"])
        gs = rec["gamesStarted"]
        rate = rec["firstShotRate"]
        pos  = rec["position"]
        team = rec["team"]

        lines.append(
            f'  "{js_name}": '
            "{ "
            f"ftbMade: {ftb}, gamesStarted: {gs}, "
            f"firstShotRate: {rate}, "
            f"shots: {shots_js}, "
            f"position: \"{pos}\", team: \"{team}\""
            " },"
        )

    lines.append("};\n")
    return "\n".join(lines)


# ─── JSON export ──────────────────────────────────────────────────────────────

def export_json(
    player_ftb:  Dict[str, dict],
    team_stats:  Dict[str, dict],
    pos_data:    Dict[str, dict],
    meta:        dict,
    out_path:    Path,
) -> None:
    """
    Write the localStorage-compatible JSON to out_path.
    Format matches what the jedibets engine saves:
      { playerFtb, teamStats, positionData, savedAt, source, meta }
    """
    payload = {
        "playerFtb":    player_ftb,
        "teamStats":    team_stats,
        "positionData": pos_data,
        "savedAt":      datetime.utcnow().isoformat() + "Z",
        "source":       "xlsx-pipeline",
        "meta":         meta,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    log.info("JSON written: %s  (%d bytes)", out_path, out_path.stat().st_size)


# ─── HTML patch  ──────────────────────────────────────────────────────────────

def patch_html(html_path: Path, js_constant: str) -> bool:
    """
    Replace the SEASON_FTB_DATA constant in the HTML file in-place.
    Returns True on success, False if the marker was not found.
    """
    text = html_path.read_text(encoding="utf-8")

    # Locate the constant — match from 'const SEASON_FTB_DATA' to the closing '};'
    pattern = re.compile(
        r"(?://[^\n]*\n)*const SEASON_FTB_DATA\s*=\s*\{.*?\n\};\n",
        re.DOTALL,
    )
    if not pattern.search(text):
        log.warning("SEASON_FTB_DATA marker not found in %s — skipping HTML patch", html_path)
        return False

    new_text = pattern.sub(js_constant + "\n", text, count=1)

    # Verify brace balance of the resulting script block
    script_m = re.search(r"<script>(.*)</script>", new_text, re.DOTALL)
    if script_m:
        script = script_m.group(1)
        brace_bal = script.count("{") - script.count("}")
        paren_bal = script.count("(") - script.count(")")
        if brace_bal != 0 or paren_bal != 0:
            log.error("HTML patch aborted: brace balance=%d, paren balance=%d — "
                      "new constant may be malformed", brace_bal, paren_bal)
            return False

    html_path.write_text(new_text, encoding="utf-8")
    log.info("HTML patched: %s", html_path)
    return True


# ─── Also update app's localStorage restore handler  ─────────────────────────

def patch_html_restore_handler(html_path: Path) -> bool:
    """
    Extend the localStorage restore handler so it also reads the new
    'positionData' field produced by this pipeline (field not present in
    legacy jedibets format).
    """
    text = html_path.read_text(encoding="utf-8")

    OLD = (
        "// New jedibets format: { playerFtb, teamStats, source: \"jedibets\" }\n"
        "          if (parsed.source === \"jedibets\" && parsed.playerFtb) {\n"
        "            setComputedPlayerFtb(parsed.playerFtb);\n"
        "            if (parsed.teamStats) setComputedTeamStats(parsed.teamStats);\n"
        "            setEngineStatus(\"done\");\n"
        "            addLog(`📦 Loaded cached JediBets data — ${Object.keys(parsed.playerFtb).length} players · ${Object.keys(parsed.teamStats || {}).length} teams`);"
    )
    NEW = (
        "// New jedibets / xlsx-pipeline format: { playerFtb, teamStats, positionData, source }\n"
        "          if ((parsed.source === \"jedibets\" || parsed.source === \"xlsx-pipeline\") && parsed.playerFtb) {\n"
        "            setComputedPlayerFtb(parsed.playerFtb);\n"
        "            if (parsed.teamStats)    setComputedTeamStats(parsed.teamStats);\n"
        "            if (parsed.positionData) setPositionData(parsed.positionData);\n"
        "            setEngineStatus(\"done\");\n"
        "            const src = parsed.source === \"xlsx-pipeline\" ? \"Season XLSX\" : \"JediBets\";\n"
        "            addLog(`📦 Loaded cached ${src} data — ${Object.keys(parsed.playerFtb).length} players · ${Object.keys(parsed.teamStats || {}).length} teams`);"
    )

    if OLD not in text:
        log.warning("Restore handler marker not found — skipping that patch")
        return False

    html_path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    log.info("Restore handler patched to accept positionData field")
    return True


def add_load_json_button(html_path: Path) -> bool:
    """
    Add a '📂 Load Season JSON' button to the engine panel that lets the user
    import the ftb_data_output.json file produced by this pipeline directly
    into the app without re-running the engine.
    """
    text = html_path.read_text(encoding="utf-8")

    # Only patch once
    if "loadSeasonJson" in text:
        log.info("Load JSON button already present — skipping button patch")
        return True

    # Find the ▶ Fetch JediBets Data button region and insert before it
    OLD_BTN_REGION = (
        'onClick: () => runDataEngine(false),\n'
        '    style: {\n'
        '      background: "#1D4ED8",'
    )
    if OLD_BTN_REGION not in text:
        log.warning("Button insertion point not found — skipping button patch")
        return False

    LOAD_BTN_JS = (
        "// ── Load Season JSON button (import ftb_data_output.json) ─────\n"
        "  const fileInputRef = React.useRef(null);\n"
        "  function loadSeasonJson(e) {\n"
        "    const file = e.target.files[0];\n"
        "    if (!file) return;\n"
        "    const reader = new FileReader();\n"
        "    reader.onload = ev => {\n"
        "      try {\n"
        "        const parsed = JSON.parse(ev.target.result);\n"
        "        if (!parsed.playerFtb) throw new Error('No playerFtb field');\n"
        "        setComputedPlayerFtb(parsed.playerFtb);\n"
        "        if (parsed.teamStats)    setComputedTeamStats(parsed.teamStats);\n"
        "        if (parsed.positionData) setPositionData(parsed.positionData);\n"
        "        setEngineStatus('done');\n"
        "        const src = parsed.source || 'JSON';\n"
        "        const players = Object.keys(parsed.playerFtb).length;\n"
        "        const teams   = Object.keys(parsed.teamStats || {}).length;\n"
        "        addLog(`📂 Imported ${src}: ${players} players · ${teams} teams`);\n"
        "      } catch(err) {\n"
        "        addLog('❌ JSON load failed: ' + err.message);\n"
        "      }\n"
        "    };\n"
        "    reader.readAsText(file);\n"
        "    e.target.value = '';\n"
        "  }\n"
    )

    # Insert the ref + handler before the first useCallback in the component
    UC_MARKER = "const runDataEngine = useCallback"
    if UC_MARKER not in text:
        log.warning("useCallback marker not found for JS injection")
        return False

    text = text.replace(UC_MARKER, LOAD_BTN_JS + "\n  " + UC_MARKER, 1)

    # Add the actual button element just before the run-engine button
    LOAD_BTN_ELEM = (
        "/*#__PURE__*/React.createElement(\"label\", {\n"
        "    className: \"btn\",\n"
        "    style: {\n"
        "      background: \"#0f2a1a\",\n"
        "      border: \"1px solid #22c55e55\",\n"
        "      color: \"#4ADE80\",\n"
        "      borderRadius: 8,\n"
        "      padding: \"7px 14px\",\n"
        "      fontSize: 11,\n"
        "      cursor: \"pointer\"\n"
        "    }\n"
        "  },\n"
        "  \"\\uD83D\\uDCC2 Load Season JSON\",\n"
        "  /*#__PURE__*/React.createElement(\"input\", {\n"
        "    type: \"file\",\n"
        "    accept: \".json\",\n"
        "    style: { display: \"none\" },\n"
        "    onChange: loadSeasonJson\n"
        "  })\n"
        "), "
    )

    text = text.replace(OLD_BTN_REGION, LOAD_BTN_ELEM + OLD_BTN_REGION, 1)

    html_path.write_text(text, encoding="utf-8")
    log.info("📂 Load Season JSON button added to engine panel")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="FTB PbP Data Engine v2 — Excel Integration Pipeline"
    )
    parser.add_argument(
        "--xlsx",
        default="/mnt/user-data/uploads/NBA_First_Basket_2025-26.xlsx",
        help="Path to the Excel workbook",
    )
    parser.add_argument(
        "--roster",
        default="/home/claude/player_roster.json",
        help="Path to player_roster.json",
    )
    parser.add_argument(
        "--out-dir",
        default="/mnt/user-data/outputs",
        help="Directory for output files",
    )
    parser.add_argument(
        "--html",
        default="/mnt/user-data/outputs/ftb-scout_fixed.html",
        help="Path to ftb-scout HTML file to patch (optional)",
    )
    parser.add_argument(
        "--patch-html",
        action="store_true",
        default=True,
        help="Patch the HTML with the new SEASON_FTB_DATA constant",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    xlsx_path   = Path(args.xlsx)
    roster_path = Path(args.roster)
    out_dir     = Path(args.out_dir)
    html_path   = Path(args.html)

    # Validate paths
    for p in (xlsx_path, roster_path):
        if not p.exists():
            log.error("File not found: %s", p)
            return 1

    log.info("═══════════════════════════════════════════════════════════════")
    log.info("  FTB PbP Data Engine v2 — Excel Integration Pipeline")
    log.info("  Source: %s", xlsx_path.name)
    log.info("═══════════════════════════════════════════════════════════════")

    # Step 1 — Ingest
    df = ingest_excel(xlsx_path)

    # Step 2 — Build roster index
    by_abbrev, by_full = build_roster_index(roster_path)

    # Step 3 — Compute team stats
    team_stats = compute_team_stats(df)

    # Step 4 — Extract events (with name resolution + position attachment)
    events, resolve_stats = build_events(df, by_abbrev, by_full)

    # Step 5 — Aggregate player FTB records
    player_ftb = aggregate_player_ftb(events, df)

    # Step 6 — Aggregate position data (defending team breakdown)
    pos_data = aggregate_position_data(events)

    # Step 7 — Validate
    validate_output(player_ftb, team_stats, pos_data, resolve_stats)

    # Step 8 — Export JSON
    meta = {
        "totalGames":       len(df),
        "totalEvents":      resolve_stats["total_events"],
        "playersTracked":   len(player_ftb),
        "positionsMapped":  sum(1 for r in player_ftb.values() if r["position"] != "UNK"),
        "positionsUnknown": sum(1 for r in player_ftb.values() if r["position"] == "UNK"),
        "season":           "2025-26",
        "dataSource":       "NBA_First_Basket_2025-26.xlsx",
    }
    json_out = out_dir / "ftb_data_output.json"
    export_json(player_ftb, team_stats, pos_data, meta, json_out)

    # Step 9 — Generate JS constant
    js_constant = generate_js_constant(player_ftb)
    js_out = out_dir / "season_ftb_patch.js"
    js_out.parent.mkdir(parents=True, exist_ok=True)
    js_out.write_text(js_constant, encoding="utf-8")
    log.info("JS constant written: %s", js_out)

    # Step 10 — Patch HTML
    if args.patch_html and html_path.exists():
        import shutil
        bak = html_path.with_name(html_path.stem + "_pre_patch.html")
        shutil.copy2(html_path, bak)
        log.info("HTML backup: %s", bak)

        ok1 = patch_html(html_path, js_constant)
        ok2 = patch_html_restore_handler(html_path)
        ok3 = add_load_json_button(html_path)

        if ok1 and ok2:
            # Verify syntax balance
            script_m = re.search(
                r"<script>(.*)</script>",
                html_path.read_text(encoding="utf-8"),
                re.DOTALL,
            )
            if script_m:
                script = script_m.group(1)
                bb = script.count("{") - script.count("}")
                pb = script.count("(") - script.count(")")
                if bb == 0 and pb == 0:
                    log.info("✅ HTML syntax check passed (brace balance=0, paren balance=0)")
                else:
                    log.error("❌ HTML syntax check FAILED (brace=%d, paren=%d) — "
                              "restore from backup %s", bb, pb, bak)
    else:
        if not html_path.exists():
            log.warning("HTML file not found at %s — skipping HTML patch", html_path)

    # Final summary
    log.info("═══════════════════════════════════════════════════════════════")
    log.info("  PIPELINE COMPLETE")
    log.info("  Games processed:    %d", len(df))
    log.info("  Events extracted:   %d", resolve_stats["total_events"])
    log.info("  Players tracked:    %d", meta["playersTracked"])
    log.info("  Positions mapped:   %d / %d  (%.1f%%)",
             meta["positionsMapped"], meta["playersTracked"],
             meta["positionsMapped"] / max(meta["playersTracked"], 1) * 100)
    log.info("  JSON output:        %s", json_out)
    log.info("  JS constant:        %s", js_out)
    log.info("═══════════════════════════════════════════════════════════════")
    return 0


if __name__ == "__main__":
    sys.exit(main())
