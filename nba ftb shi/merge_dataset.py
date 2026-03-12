"""Merge FTB, PPG, and Lineups datasets into a single JSON file.

Outputs a JSON payload shaped for ftb-scout.html:
{
  "meta": {...},
  "players": {
     "normalizedname": { ... merged fields ... }
  }
}
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_FTB_XLSX = BASE_DIR / ".." / "first team basket dataset" / "NBA_First_Basket_2025-26.xlsx"
DEFAULT_LINEUPS_XLSX = BASE_DIR / ".." / "first team basket dataset" / "NBA_Lineups_2025-26.xlsx"
DEFAULT_PPG_XLSX = BASE_DIR / ".." / "first team basket dataset" / "NBA_PPG_2025-26.xlsx"
DEFAULT_FTB_JSON = BASE_DIR / "ftb_data_output.json"
DEFAULT_ROSTER_JSON = BASE_DIR / "player_roster.json"
DEFAULT_OUTPUT = BASE_DIR / "merged_dataset.json"

SHOT_KEYS = ("layup", "dunk", "mid", "threeP", "ft", "tip", "hook")


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_key(name: str) -> str:
    if not name:
        return ""
    cleaned = strip_accents(name)
    cleaned = "".join(ch for ch in cleaned.lower() if ch.isalnum())
    return cleaned


def _initial_last_key(full_name: str) -> str:
    parts = [p for p in full_name.replace("'", "").replace(".", "").split() if p]
    if not parts:
        return ""
    first_initial = parts[0][0]
    last = parts[-1]
    return normalize_key(f"{first_initial} {last}")


def build_roster_maps(path: Path) -> Tuple[Dict[str, List[dict]], Dict[str, List[dict]], Dict[str, List[dict]]]:
    if not path.exists():
        return {}, {}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    by_full: Dict[str, List[dict]] = {}
    by_abbrev: Dict[str, List[dict]] = {}
    by_initial_last: Dict[str, List[dict]] = {}
    for player in data.get("players", []):
        full_name = player.get("full_name") or ""
        abbrev = player.get("abbreviated") or ""
        full_key = normalize_key(full_name)
        if full_key:
            by_full.setdefault(full_key, []).append(player)
        if abbrev:
            abbr_key = normalize_key(abbrev)
            if abbr_key:
                by_abbrev.setdefault(abbr_key, []).append(player)
        init_key = _initial_last_key(full_name)
        if init_key:
            by_initial_last.setdefault(init_key, []).append(player)
    return by_full, by_abbrev, by_initial_last


def resolve_roster(name: str, team: str,
                   by_full: Dict[str, List[dict]],
                   by_abbrev: Dict[str, List[dict]],
                   by_initial_last: Dict[str, List[dict]]) -> Optional[dict]:
    key = normalize_key(name)
    candidates = by_abbrev.get(key) or by_full.get(key) or by_initial_last.get(key) or []
    if not candidates:
        init_key = _initial_last_key(name)
        candidates = by_initial_last.get(init_key, []) if init_key else []
    if not candidates:
        return None
    if team:
        team_match = [p for p in candidates if p.get("primary_team") == team]
        if team_match:
            return team_match[0]
    return candidates[0]


def load_ppg_data(path: Path) -> Dict[str, Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name="PPG")
    result = {}
    for _, row in df.iterrows():
        name = str(row.get("FULL_NAME") or "").strip()
        if not name:
            continue
        key = normalize_key(name)
        rec = {
            "name": name,
            "team": str(row.get("TEAM") or "").strip(),
            "ppg": safe_float(row.get("PPG")),
            "gp": safe_float(row.get("GP")),
            "source": "ppg"
        }
        result[key] = choose_record(result.get(key), rec)
    return result


def load_lineups_data(path: Path,
                      roster_full: Dict[str, List[dict]],
                      roster_abbrev: Dict[str, List[dict]],
                      roster_initial: Dict[str, List[dict]]) -> Dict[str, Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name="Lineups")
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    starter_counts = defaultdict(int)
    latest_lineup_by_team = {}

    for _, row in df.iterrows():
        team = str(row.get("TEAM") or "").strip()
        if not team:
            continue
        game_date = row.get("GAME_DATE")
        if pd.notna(game_date):
            prev = latest_lineup_by_team.get(team)
            if not prev or game_date > prev["date"]:
                starters = [str(row.get(f"STARTER_{i}") or "").strip() for i in range(1, 6)]
                latest_lineup_by_team[team] = {"date": game_date, "starters": starters}

        for i in range(1, 6):
            starter = str(row.get(f"STARTER_{i}") or "").strip()
            if starter:
                roster = resolve_roster(starter, team, roster_full, roster_abbrev, roster_initial)
                canonical_name = (roster or {}).get("full_name") or starter
                key = normalize_key(canonical_name)
                starter_counts[(key, team)] += 1

    merged = {}
    for team, info in latest_lineup_by_team.items():
        starters = info["starters"]
        for idx, name in enumerate(starters, start=1):
            if not name:
                continue
            roster = resolve_roster(name, team, roster_full, roster_abbrev, roster_initial)
            canonical_name = (roster or {}).get("full_name") or name
            key = normalize_key(canonical_name)
            merged[key] = choose_record(
                merged.get(key),
                {
                    "name": canonical_name,
                    "team": team,
                    "starterRank": idx,
                    "starterCount": starter_counts.get((key, team), 0),
                    "lineupDate": info["date"].strftime("%Y-%m-%d") if info["date"] else "",
                    "source": "lineups"
                }
            )
    return merged


def load_ftb_json(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    player_ftb = data.get("playerFtb", {})
    result = {}
    for name, rec in player_ftb.items():
        key = normalize_key(name)
        result[key] = {
            "name": name,
            "team": rec.get("team") or "",
            "position": rec.get("position") or "",
            "ftbMade": rec.get("ftbMade") or 0,
            "gamesStarted": rec.get("gamesStarted") or 0,
            "firstShotRate": rec.get("firstShotRate") or 0,
            "shots": rec.get("shots") or {k: 0 for k in SHOT_KEYS},
            "source": "ftb_json"
        }
    return result


def load_ftb_from_excel(path: Path,
                        roster_full: Dict[str, List[dict]],
                        roster_abbrev: Dict[str, List[dict]],
                        roster_initial: Dict[str, List[dict]]) -> Dict[str, Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name="First Baskets")
    team_games = defaultdict(int)
    counts = defaultdict(lambda: {"ftbMade": 0, "team": "", "name": ""})

    for _, row in df.iterrows():
        home_team = str(row.get("HOME_TEAM") or "").strip()
        away_team = str(row.get("AWAY_TEAM") or "").strip()
        if home_team:
            team_games[home_team] += 1
        if away_team:
            team_games[away_team] += 1

        for scorer_col, team in [("HOME_FIRST_SCORER", home_team), ("AWAY_FIRST_SCORER", away_team)]:
            scorer = str(row.get(scorer_col) or "").strip()
            if not scorer:
                continue
            key = normalize_key(scorer)
            counts[key]["ftbMade"] += 1
            counts[key]["team"] = team or counts[key]["team"]
            if not counts[key]["name"]:
                counts[key]["name"] = scorer

    result = {}
    for key, rec in counts.items():
        team = rec.get("team") or ""
        games_started = team_games.get(team, rec.get("ftbMade", 0))
        roster = resolve_roster(rec.get("name") or key, team, roster_full, roster_abbrev, roster_initial) or {}
        result[key] = {
            "name": roster.get("full_name") or rec.get("name") or key,
            "team": team or roster.get("team") or "",
            "position": roster.get("position") or "",
            "ftbMade": rec.get("ftbMade", 0),
            "gamesStarted": games_started,
            "firstShotRate": round(rec.get("ftbMade", 0) / max(games_started, 1), 4),
            "shots": {k: 0 for k in SHOT_KEYS},
            "source": "ftb_excel"
        }
    return result


def merge_ftb_sources(ftb_json: Dict[str, Dict[str, Any]],
                      ftb_excel: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged = {**ftb_excel}
    for key, rec in ftb_json.items():
        if rec.get("ftbMade") or rec.get("gamesStarted"):
            merged[key] = {**merged.get(key, {}), **rec}
        else:
            merged.setdefault(key, rec)
    return merged


def safe_float(val: Any) -> float | None:
    try:
        num = float(val)
        return num
    except (TypeError, ValueError):
        return None


def choose_record(existing: Dict[str, Any] | None, incoming: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return incoming
    # Prefer records with richer stats
    existing_score = score_record(existing)
    incoming_score = score_record(incoming)
    if incoming_score > existing_score:
        merged = {**existing, **incoming}
    else:
        merged = {**incoming, **existing}
    # Preserve higher starterRank detail if both present
    if "starterRank" in existing or "starterRank" in incoming:
        merged["starterRank"] = incoming.get("starterRank") or existing.get("starterRank")
    return merged


def score_record(rec: Dict[str, Any]) -> int:
    score = 0
    if rec.get("ppg") is not None:
        score += 2
    if rec.get("starterRank"):
        score += 3
    if rec.get("ftbMade"):
        score += 2
    if rec.get("position"):
        score += 1
    return score


def merge_records(ftb_map: Dict[str, Dict[str, Any]],
                  ppg_map: Dict[str, Dict[str, Any]],
                  lineup_map: Dict[str, Dict[str, Any]],
                  roster_full: Dict[str, List[dict]],
                  roster_abbrev: Dict[str, List[dict]],
                  roster_initial: Dict[str, List[dict]]) -> Dict[str, Dict[str, Any]]:
    merged = {}

    for key, rec in ftb_map.items():
        merged[key] = rec.copy()

    for key, rec in ppg_map.items():
        merged[key] = choose_record(merged.get(key), rec)

    for key, rec in lineup_map.items():
        merged[key] = choose_record(merged.get(key), rec)

    def resolve_ppg_record(primary_key: str, rec_name: str, roster: Optional[dict]) -> Optional[Dict[str, Any]]:
        candidates = []
        if primary_key:
            candidates.append(primary_key)
        if rec_name:
            candidates.append(normalize_key(rec_name))
        if roster and roster.get("full_name"):
            candidates.append(normalize_key(roster.get("full_name")))
        if roster and roster.get("abbreviated"):
            candidates.append(normalize_key(roster.get("abbreviated")))
        init_key = _initial_last_key(roster.get("full_name") if roster else rec_name)
        if init_key:
            candidates.append(init_key)
        for key in candidates:
            ppg_rec = ppg_map.get(key)
            if ppg_rec and ppg_rec.get("ppg") is not None:
                return ppg_rec
        return None

    canonical = {}
    for key, rec in merged.items():
        roster = resolve_roster(rec.get("name") or key, rec.get("team") or "", roster_full, roster_abbrev, roster_initial)
        canonical_name = (roster or {}).get("full_name") or rec.get("name") or key
        canonical_key = normalize_key(canonical_name) or key
        rec = {**rec, "name": canonical_name}
        if roster:
            if not rec.get("position"):
                rec["position"] = roster.get("position") or ""
            if not rec.get("team"):
                rec["team"] = roster.get("primary_team") or ""
        ppg_rec = resolve_ppg_record(canonical_key, rec.get("name"), roster)
        if ppg_rec and ppg_rec.get("ppg") is not None:
            rec["ppg"] = ppg_rec.get("ppg")
        if ppg_rec and ppg_rec.get("gp") is not None:
            rec["gp"] = ppg_rec.get("gp")
        canonical[canonical_key] = choose_record(canonical.get(canonical_key), rec)

    for key, rec in canonical.items():
        rec.setdefault("shots", {k: 0 for k in SHOT_KEYS})
        rec.setdefault("ftbMade", 0)
        rec.setdefault("gamesStarted", 0)
        rec.setdefault("firstShotRate", 0)
        rec.setdefault("ppg", None)
        rec.setdefault("gp", None)
        rec.setdefault("starterRank", None)
        rec.setdefault("starterCount", 0)
        rec.setdefault("lineupDate", "")
    return canonical


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge FTB/PPG/Lineups datasets")
    parser.add_argument("--ftb-xlsx", default=str(DEFAULT_FTB_XLSX))
    parser.add_argument("--lineups-xlsx", default=str(DEFAULT_LINEUPS_XLSX))
    parser.add_argument("--ppg-xlsx", default=str(DEFAULT_PPG_XLSX))
    parser.add_argument("--ftb-json", default=str(DEFAULT_FTB_JSON))
    parser.add_argument("--roster-json", default=str(DEFAULT_ROSTER_JSON))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    ftb_xlsx = Path(args.ftb_xlsx)
    lineups_xlsx = Path(args.lineups_xlsx)
    ppg_xlsx = Path(args.ppg_xlsx)
    ftb_json = Path(args.ftb_json)
    roster_json = Path(args.roster_json)
    output = Path(args.output)

    roster_full, roster_abbrev, roster_initial = build_roster_maps(roster_json)
    ppg_map = load_ppg_data(ppg_xlsx)
    lineup_map = load_lineups_data(lineups_xlsx, roster_full, roster_abbrev, roster_initial)

    ftb_json_map = load_ftb_json(ftb_json)
    ftb_excel_map = load_ftb_from_excel(ftb_xlsx, roster_full, roster_abbrev, roster_initial)
    ftb_map = merge_ftb_sources(ftb_json_map, ftb_excel_map)

    merged = merge_records(ftb_map, ppg_map, lineup_map, roster_full, roster_abbrev, roster_initial)

    meta = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "players": len(merged),
            "ppg": len(ppg_map),
            "lineups": len(lineup_map),
            "ftb": len(ftb_map)
        },
        "sources": {
            "ftbXlsx": str(ftb_xlsx),
            "lineupsXlsx": str(lineups_xlsx),
            "ppgXlsx": str(ppg_xlsx),
            "ftbJson": str(ftb_json) if ftb_json.exists() else "",
            "rosterJson": str(roster_json) if roster_json.exists() else ""
        }
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "players": merged,
        "source": "merged-excel"
    }
    with output.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"Merged dataset written: {output} ({len(merged)} players)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
