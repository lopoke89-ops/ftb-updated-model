import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

DATES = ["20251021", "20251022", "20251023"]
TEAM_MAP = {
    "NY": "NYK",
    "GS": "GSW",
    "SA": "SAS",
    "NO": "NOP",
    "UTAH": "UTA",
    "WSH": "WAS",
    "LA": "LAC",
    "BRK": "BKN",
}


def normalize_team(abbr: str) -> str:
    if not abbr:
        return ""
    key = abbr.strip().upper()
    return TEAM_MAP.get(key, key)


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clock_display(clock: object) -> str:
    if isinstance(clock, dict):
        return str(clock.get("displayValue") or "")
    return str(clock or "")


def parse_clock(clock: object) -> int:
    display = clock_display(clock)
    if not display or ":" not in display:
        return -1
    mins, secs = display.split(":", 1)
    try:
        return int(mins) * 60 + int(secs)
    except ValueError:
        return -1


def get_period(play: dict) -> int:
    period = play.get("period") or {}
    return period.get("number") or period.get("value") or 0


def get_team_abbr(play: dict, team_id_map: dict[str, str]) -> str:
    team = play.get("team") or {}
    team_id = str(team.get("id") or "")
    mapped = team_id_map.get(team_id, "")
    return normalize_team(
        team.get("abbreviation") or team.get("shortDisplayName") or mapped
    )


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


def get_first_scores(plays: list[dict], team_id_map: dict[str, str]) -> dict:
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
        team = get_team_abbr(play, team_id_map)
        if not team:
            continue
        clock = play.get("clock")
        remaining = parse_clock(clock)
        prev = first_by_team.get(team)
        if not prev or remaining > prev["remaining"]:
            first_by_team[team] = {
                "remaining": remaining,
                "clock": clock_display(clock),
                "name": get_play_name(play),
                "text": play.get("text") or "",
                "scoreValue": score_val,
                "period": get_period(play),
            }
    return first_by_team


def has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip() not in ("", "nan", "None")


def build_event_map(dates: list[str]) -> dict[tuple[str, str, str], str]:
    event_map: dict[tuple[str, str, str], str] = {}
    for date_str in dates:
        scoreboard = fetch_json(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        )
        for event in scoreboard.get("events", []):
            comp = (event.get("competitions") or [None])[0] or {}
            competitors = comp.get("competitors") or []
            home = away = ""
            for competitor in competitors:
                team = competitor.get("team") or {}
                abbr = normalize_team(team.get("abbreviation") or "")
                if competitor.get("homeAway") == "home":
                    home = abbr
                if competitor.get("homeAway") == "away":
                    away = abbr
            if home and away:
                event_map[(date_str, home, away)] = str(event.get("id"))
    return event_map


def main() -> None:
    excel_path = Path(
        r"c:\Users\lopok\Desktop\scrapper\nba ftb shi\NBA_First_Basket_2025-26.xlsx"
    )
    df = pd.read_excel(excel_path, sheet_name="First Baskets")
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    mask = df["GAME_DATE"].between("2025-10-21", "2025-10-23")
    df_sub = df[mask].copy()

    dates = sorted({d.strftime("%Y%m%d") for d in df_sub["GAME_DATE"].dropna()})
    event_map = build_event_map(dates)

    updated = 0
    missing_event = 0
    missing_scores = 0

    for idx, row in df_sub.iterrows():
        home = str(row.get("HOME_TEAM") or "").strip()
        away = str(row.get("AWAY_TEAM") or "").strip()
        date_val = row.get("GAME_DATE")
        if pd.isna(date_val):
            continue
        date_str = pd.to_datetime(date_val).strftime("%Y%m%d")

        if has_value(row.get("HOME_FIRST_SCORER")) and has_value(
            row.get("AWAY_FIRST_SCORER")
        ):
            continue

        event_id = event_map.get((date_str, home, away))
        if not event_id:
            missing_event += 1
            continue

        summary = fetch_json(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
        )
        plays = summary.get("plays") or (summary.get("pbp") or {}).get("plays") or []
        team_id_map = {}
        for entry in (summary.get("boxscore") or {}).get("teams") or []:
            team = entry.get("team") or {}
            team_id = str(team.get("id") or "")
            abbr = normalize_team(team.get("abbreviation") or "")
            if team_id and abbr:
                team_id_map[team_id] = abbr
        first_scores = get_first_scores(plays, team_id_map)
        home_score = first_scores.get(home)
        away_score = first_scores.get(away)

        if not home_score or not away_score:
            missing_scores += 1
            continue

        df.loc[idx, "HOME_FIRST_SCORER"] = home_score.get("name")
        df.loc[idx, "HOME_SHOT_DESC"] = home_score.get("text")
        df.loc[idx, "HOME_POINTS"] = home_score.get("scoreValue")
        df.loc[idx, "HOME_TIME"] = home_score.get("clock")
        df.loc[idx, "HOME_PERIOD"] = home_score.get("period")

        df.loc[idx, "AWAY_FIRST_SCORER"] = away_score.get("name")
        df.loc[idx, "AWAY_SHOT_DESC"] = away_score.get("text")
        df.loc[idx, "AWAY_POINTS"] = away_score.get("scoreValue")
        df.loc[idx, "AWAY_TIME"] = away_score.get("clock")
        df.loc[idx, "AWAY_PERIOD"] = away_score.get("period")

        updated += 1

    df.to_excel(excel_path, sheet_name="First Baskets", index=False)

    print("Backfill complete.")
    print("Rows updated:", updated)
    print("Rows missing event:", missing_event)
    print("Rows missing scores:", missing_scores)


if __name__ == "__main__":
    main()
