"""Update merged_dataset.json with FTB totals from NBA_First_Basket_2025-26.xlsx."""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / ".." / "first team basket dataset" / "NBA_First_Basket_2025-26.xlsx"
ROSTER_PATH = BASE_DIR / "player_roster.json"
MERGED_PATH = BASE_DIR / "merged_dataset.json"

TARGET_PLAYERS = {
    "Marcus Sasser",
    "Bub Carrington",
    "Kasparas Jakučionis",
    "Taylor Hendricks",
    "Leonard Miller",
    "Christian Braun",
}


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_key(name: str) -> str:
    cleaned = strip_accents(name or "")
    return "".join(ch for ch in cleaned.lower() if ch.isalnum())


def initial_last_key(full_name: str) -> str:
    parts = [p for p in full_name.replace("'", "").replace(".", "").split() if p]
    if not parts:
        return ""
    return normalize_key(f"{parts[0][0]} {parts[-1]}")


def build_roster_maps(path: Path):
    by_full: dict[str, list[dict]] = defaultdict(list)
    by_abbrev: dict[str, list[dict]] = defaultdict(list)
    by_initial: dict[str, list[dict]] = defaultdict(list)
    if not path.exists():
        return by_full, by_abbrev, by_initial
    with path.open(encoding="utf-8") as fh:
        roster = json.load(fh).get("players", [])
    for player in roster:
        full = player.get("full_name") or ""
        abbrev = player.get("abbreviated") or ""
        if full:
            by_full[normalize_key(full)].append(player)
            init_key = initial_last_key(full)
            if init_key:
                by_initial[init_key].append(player)
        if abbrev:
            by_abbrev[normalize_key(abbrev)].append(player)
    return by_full, by_abbrev, by_initial


def resolve_roster(name: str, team: str, by_full, by_abbrev, by_initial):
    key = normalize_key(name)
    candidates = by_abbrev.get(key) or by_full.get(key) or by_initial.get(key) or []
    if not candidates:
        init_key = initial_last_key(name)
        candidates = by_initial.get(init_key, []) if init_key else []
    if not candidates:
        return None
    if team:
        matches = [p for p in candidates if p.get("primary_team") == team]
        if matches:
            return matches[0]
    return candidates[0]


def main() -> int:
    by_full, by_abbrev, by_initial = build_roster_maps(ROSTER_PATH)

    df = pd.read_excel(EXCEL_PATH, sheet_name="First Baskets")
    team_games: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)

    for _, row in df.iterrows():
        home = str(row.get("HOME_TEAM") or "").strip()
        away = str(row.get("AWAY_TEAM") or "").strip()
        if home:
            team_games[home] += 1
        if away:
            team_games[away] += 1
        for col, team in (("HOME_FIRST_SCORER", home), ("AWAY_FIRST_SCORER", away)):
            scorer = str(row.get(col) or "").strip()
            if not scorer:
                continue
            roster = resolve_roster(scorer, team, by_full, by_abbrev, by_initial)
            canonical = (roster or {}).get("full_name") or scorer
            counts[normalize_key(canonical)] += 1

    merged = json.loads(MERGED_PATH.read_text(encoding="utf-8"))
    players = merged.get("players", {})

    updates = {}
    for name in TARGET_PLAYERS:
        key = normalize_key(name)
        rec = players.get(key)
        if not rec:
            continue
        team = rec.get("team") or (resolve_roster(name, "", by_full, by_abbrev, by_initial) or {}).get("primary_team") or ""
        ftb = counts.get(key, 0)
        games = team_games.get(team, 0) if team else 0
        rec["ftbMade"] = ftb
        rec["gamesStarted"] = games
        rec["firstShotRate"] = round(ftb / games, 4) if games else 0
        updates[name] = {"ftbMade": ftb, "gamesStarted": games, "team": team}

    MERGED_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Updated FTB totals:")
    for name, data in updates.items():
        print(f"- {name}: {data['ftbMade']} (gamesStarted={data['gamesStarted']}, team={data['team']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
