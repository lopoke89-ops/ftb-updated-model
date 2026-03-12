"""Validate first 5 NBA_First_Basket rows against ESPN play-by-play."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / ".." / "first team basket dataset" / "NBA_First_Basket_2025-26.xlsx"


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_clock(clock: str) -> int:
    if not clock or ":" not in clock:
        return -1
    mins, secs = clock.split(":", 1)
    try:
        return int(mins) * 60 + int(secs)
    except ValueError:
        return -1


def get_period(play: dict) -> int:
    period = play.get("period") or {}
    return period.get("number") or period.get("value") or 0


def get_team_abbr(play: dict) -> str:
    team = play.get("team") or {}
    return team.get("abbreviation") or team.get("shortDisplayName") or ""


def get_play_name(play: dict) -> str:
    athletes = play.get("athletes") or []
    if athletes:
        name = athletes[0].get("displayName") or athletes[0].get("fullName")
        if name:
            return name
    athlete = play.get("athlete") or {}
    name = athlete.get("displayName") or athlete.get("fullName")
    if name:
        return name
    text = play.get("text") or ""
    return text.split(" makes ")[0].split(" misses ")[0]


def get_first_scores(plays: list[dict]) -> dict:
    first_by_team: dict[str, dict] = {}
    for play in plays:
        if not play:
            continue
        if not (play.get("scoringPlay") or play.get("scoreValue") or play.get("scoreValue") == 0):
            continue
        score_val = play.get("scoreValue") or 0
        if score_val <= 0:
            continue
        if get_period(play) != 1:
            continue
        team = get_team_abbr(play)
        if not team:
            continue
        clock = play.get("clock") or ""
        remaining = parse_clock(clock)
        prev = first_by_team.get(team)
        if not prev or remaining > prev["remaining"]:
            first_by_team[team] = {
                "remaining": remaining,
                "clock": clock,
                "name": get_play_name(play),
                "text": play.get("text") or "",
                "scoreValue": score_val
            }
    return first_by_team


def main() -> int:
    df = pd.read_excel(EXCEL_PATH, sheet_name="First Baskets").head(5)
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    event_map: dict[tuple[str, str, str], str] = {}
    for date in sorted(df["GAME_DATE"].dropna().unique()):
        date_str = pd.to_datetime(date).strftime("%Y%m%d")
        scoreboard = fetch_json(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        )
        for event in scoreboard.get("events", []):
            comp = (event.get("competitions") or [None])[0] or {}
            competitors = comp.get("competitors") or []
            home = away = ""
            for c in competitors:
                team = c.get("team") or {}
                if c.get("homeAway") == "home":
                    home = team.get("abbreviation") or ""
                if c.get("homeAway") == "away":
                    away = team.get("abbreviation") or ""
            if home and away:
                event_map[(date_str, home, away)] = event.get("id")

    print("ESPN validation for first 5 rows:")
    for _, row in df.iterrows():
        date = row.get("GAME_DATE")
        date_str = pd.to_datetime(date).strftime("%Y%m%d") if pd.notna(date) else ""
        home = str(row.get("HOME_TEAM") or "").strip()
        away = str(row.get("AWAY_TEAM") or "").strip()
        event_id = event_map.get((date_str, home, away))
        if not event_id:
            print(f"- {home} vs {away} ({date_str}): ESPN event not found")
            continue
        summary = fetch_json(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
        )
        plays = summary.get("plays") or (summary.get("pbp") or {}).get("plays") or []
        first_scores = get_first_scores(plays)
        home_score = first_scores.get(home, {})
        away_score = first_scores.get(away, {})
        print(f"- {home} vs {away} ({date_str}) event {event_id}")
        print(f"  Home: ESPN={home_score.get('name')} {home_score.get('clock')} | Sheet={row.get('HOME_FIRST_SCORER')} {row.get('HOME_TIME')}")
        print(f"        ESPN text: {home_score.get('text')}")
        print(f"  Away: ESPN={away_score.get('name')} {away_score.get('clock')} | Sheet={row.get('AWAY_FIRST_SCORER')} {row.get('AWAY_TIME')}")
        print(f"        ESPN text: {away_score.get('text')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
