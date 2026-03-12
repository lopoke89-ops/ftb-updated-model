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
                    "event_id": str(ev.get("id") or ""),
                }
            )
    return schedule


def main() -> None:
    excel_path = Path(
        r"c:\Users\lopok\Desktop\scrapper\nba ftb shi\NBA_First_Basket_2025-26.xlsx"
    )
    df = pd.read_excel(excel_path, sheet_name="First Baskets")
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    schedule = fetch_espn_games()
    schedule_set = {(rec["date"], rec["home"], rec["away"]) for rec in schedule}

    mask = df["GAME_DATE"].between("2025-10-21", "2025-10-23")
    df_sub = df[mask].copy()
    excel_set = set(
        zip(
            df_sub["GAME_DATE"].dt.strftime("%Y-%m-%d"),
            df_sub["HOME_TEAM"].astype(str).str.strip(),
            df_sub["AWAY_TEAM"].astype(str).str.strip(),
        )
    )

    missing = sorted(schedule_set - excel_set)
    extra = sorted(excel_set - schedule_set)

    if not missing and not extra:
        print("No differences found. No changes made.")
        return

    print("Removing extra rows:", extra)
    for date_str, home, away in extra:
        date_val = pd.to_datetime(date_str)
        df = df[~(
            (df["GAME_DATE"] == date_val)
            & (df["HOME_TEAM"].astype(str).str.strip() == home)
            & (df["AWAY_TEAM"].astype(str).str.strip() == away)
        )]

    print("Adding missing rows:", missing)
    columns = list(df.columns)
    rows_to_add = []
    schedule_map = {
        (rec["date"], rec["home"], rec["away"]): rec for rec in schedule
    }
    numeric_ids = pd.to_numeric(df["GAME_ID"], errors="coerce")
    max_id = int(numeric_ids.max()) if numeric_ids.notna().any() else 22500000
    for offset, (date_str, home, away) in enumerate(sorted(missing), start=1):
        rec = schedule_map[(date_str, home, away)]
        new_row = {col: None for col in columns}
        new_row["GAME_ID"] = str(max_id + offset)
        new_row["GAME_DATE"] = pd.to_datetime(date_str)
        new_row["HOME_TEAM"] = home
        new_row["AWAY_TEAM"] = away
        rows_to_add.append(new_row)

    if rows_to_add:
        df = pd.concat([df, pd.DataFrame(rows_to_add)], ignore_index=True)

    df = df.sort_values(["GAME_DATE", "GAME_ID"], na_position="last").reset_index(
        drop=True
    )

    df.to_excel(excel_path, sheet_name="First Baskets", index=False)

    print("Update complete.")
    print("Rows removed:", len(extra))
    print("Rows added:", len(rows_to_add))


if __name__ == "__main__":
    main()
