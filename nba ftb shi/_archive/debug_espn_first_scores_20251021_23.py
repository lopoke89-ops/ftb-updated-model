import json
from urllib.request import Request, urlopen

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
    return normalize_team(team.get("abbreviation") or team.get("shortDisplayName") or "")


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
                "scoreValue": score_val,
                "period": get_period(play),
            }
    return first_by_team


def dump_event(event_id: str, label: str) -> None:
    summary = fetch_json(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
    )
    plays = summary.get("plays") or []
    first_scores = get_first_scores(plays)
    print(f"\n{label} event {event_id} first_scores keys: {list(first_scores.keys())}")
    for team, data in first_scores.items():
        print(f"  {team}: {data['name']} {data['clock']} {data['text']}")


if __name__ == "__main__":
    dump_event("401809243", "HOU@OKC")
    dump_event("401809244", "GSW@LAL")
    dump_event("401809235", "SAS@DAL")
    dump_event("401809234", "CLE@NYK")
    dump_event("401809236", "OKC@IND")
