import json
from urllib.request import Request, urlopen


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    event_id = "401809243"  # HOU @ OKC
    summary = fetch_json(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
    )
    plays = summary.get("plays") or []
    print("plays count", len(plays))

    print("\nFirst 5 plays raw keys:")
    for play in plays[:5]:
        print(play.keys())
        break

    scoring = []
    for play in plays:
        score_val = play.get("scoreValue")
        if score_val:
            scoring.append(play)
        if len(scoring) >= 5:
            break

    print("\nFirst 5 plays with scoreValue:")
    for play in scoring[:5]:
        print(
            {
                "clock": play.get("clock"),
                "period": play.get("period"),
                "scoringPlay": play.get("scoringPlay"),
                "scoreValue": play.get("scoreValue"),
                "team": play.get("team"),
                "text": play.get("text"),
            }
        )

    scoring_p1 = []
    for play in plays:
        period = play.get("period") or {}
        pnum = period.get("number") or period.get("value")
        if pnum != 1:
            continue
        score_val = play.get("scoreValue")
        if score_val:
            scoring_p1.append(play)
        if len(scoring_p1) >= 5:
            break

    print("\nFirst 5 scoring plays in period 1:")
    for play in scoring_p1[:5]:
        print(
            {
                "clock": play.get("clock"),
                "period": play.get("period"),
                "scoringPlay": play.get("scoringPlay"),
                "scoreValue": play.get("scoreValue"),
                "team": play.get("team"),
                "text": play.get("text"),
            }
        )


if __name__ == "__main__":
    main()
