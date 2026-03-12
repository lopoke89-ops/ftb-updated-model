import json
import urllib.request
from pathlib import Path

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


def fetch_espn_games() -> list[dict]:
    schedule = []
    for d in DATES:
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
            f"?dates={d}"
        )
        with urllib.request.urlopen(url) as resp:
            data = json.load(resp)
        for ev in data.get("events", []):
            competition = (ev.get("competitions") or [{}])[0]
            teams = competition.get("competitors", [])
            home = next((t for t in teams if t.get("homeAway") == "home"), None)
            away = next((t for t in teams if t.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            game_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            schedule.append(
                {
                    "date": game_date,
                    "home": normalize_team(home["team"]["abbreviation"]),
                    "away": normalize_team(away["team"]["abbreviation"]),
                    "event_id": ev.get("id") or "",
                    "start": ev.get("date") or "",
                }
            )
    return schedule


def load_excel_games(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="First Baskets")
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    mask = df["GAME_DATE"].between("2025-10-21", "2025-10-23")
    df_sub = df[mask].copy()
    records = []
    for _, row in df_sub.iterrows():
        records.append(
            {
                "date": row.get("GAME_DATE"),
                "home": str(row.get("HOME_TEAM") or "").strip(),
                "away": str(row.get("AWAY_TEAM") or "").strip(),
                "game_id": str(row.get("GAME_ID") or "").strip(),
                "home_scorer": str(row.get("HOME_FIRST_SCORER") or "").strip(),
                "away_scorer": str(row.get("AWAY_FIRST_SCORER") or "").strip(),
            }
        )
    return records


def find_incomplete_rows(records: list[dict]) -> list[dict]:
    incomplete = []
    for rec in records:
        if not rec["home_scorer"] or not rec["away_scorer"]:
            incomplete.append(rec)
    return incomplete


def main() -> None:
    excel_path = Path(
        r"c:\Users\lopok\Desktop\scrapper\nba ftb shi\NBA_First_Basket_2025-26.xlsx"
    )
    schedule = fetch_espn_games()
    excel_records = load_excel_games(excel_path)

    schedule_set = {(rec["date"], rec["home"], rec["away"]) for rec in schedule}
    excel_set = {(rec["date"], rec["home"], rec["away"]) for rec in excel_records}

    print(f"ESPN games: {len(schedule_set)}")
    print(f"Excel games: {len(excel_set)}")

    missing = sorted(schedule_set - excel_set)
    extra = sorted(excel_set - schedule_set)

    print("\nMissing in Excel (ESPN-only):", len(missing))
    for row in missing:
        print("  ", row)

    print("\nExtra in Excel (not in ESPN for dates):", len(extra))
    for row in extra:
        print("  ", row)

    print("\nESPN schedule detail:")
    for rec in sorted(schedule, key=lambda r: (r["date"], r["home"], r["away"])):
        print(
            f"  {rec['date']} {rec['away']} @ {rec['home']}"
            f" | event {rec['event_id']} | start {rec['start']}"
        )

    print("\nExcel schedule detail:")
    for rec in sorted(excel_records, key=lambda r: (r["date"], r["home"], r["away"])):
        print(
            f"  {rec['date']} {rec['away']} @ {rec['home']}"
            f" | game {rec['game_id']}"
        )

    incomplete = find_incomplete_rows(excel_records)
    print("\nIncomplete rows (missing scorer):", len(incomplete))
    for rec in incomplete:
        print(
            f"  {rec['date']} {rec['away']} @ {rec['home']}"
            f" | game {rec['game_id']}"
        )


if __name__ == "__main__":
    main()
