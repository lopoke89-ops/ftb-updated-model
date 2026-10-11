# Opening-night readiness evaluation

The implemented policy selects evidence for each team/opponent pair and market. It is a retrospective sample-readiness rule, not a calibrated forecast.

## Selected thresholds

| Market | Games for each team | Player appearances | Additional rule |
|---|---:|---:|---|
| first-team-basket | 5 | 5 | Five starts; shared capped scoring-share grade |
| points | 5 | 5 | Positive paired attempts/makes correlation |
| threes | 5 | 8 | Positive paired attempts/makes correlation |

## Chronological later-date results

Development: through December 15, 2025. Later evaluation: December 16, 2025 through June 13, 2026. The development grid and selection rule are saved in `nba ftb shi/readiness_evaluation_protocol.json`. The report binds the exact model, evidence and evaluator hashes.

| Competition / target | Selections / opportunities | Coverage | Hits | Hit rate | DNP | Simple baseline hit rate* |
|---|---:|---:|---:|---:|---:|---:|
| regular-season / first-team-basket / FT included | 1365 / 1686 | 81.0% | 260 | 19.0% | 169 | 19.0% |
| regular-season / first-team-basket / FG only | 1364 / 1686 | 80.9% | 245 | 18.0% | 167 | 18.0% |
| regular-season / points | 1525 / 1686 | 90.5% | 633 | 41.5% | 206 | 41.5% |
| regular-season / threes | 1350 / 1686 | 80.1% | 391 | 29.0% | 180 | 32.8% |
| playoffs / first-team-basket / FT included | 79 / 170 | 46.5% | 18 | 22.8% | 1 | 25.0% |
| playoffs / first-team-basket / FG only | 79 / 170 | 46.5% | 19 | 24.1% | 1 | 26.2% |
| playoffs / points | 88 / 170 | 51.8% | 34 | 38.6% | 1 | 40.0% |
| playoffs / threes | 56 / 170 | 32.9% | 23 | 41.1% | 0 | 44.3% |

*Baseline coverage differs. Use the paired comparisons in the JSON report to assess differences on common fixtures. First Basket baseline uses observed scoring share. Points uses FGA; Threes uses 3PA. DNP selections count as misses; participating-player rates are separately reported.

The equal one-third positional offense, positional defense and opportunity weights remain as requested. Positive correlation also remains required. These tests do not establish consistent improvement from those features. Threes underperformed the attempt-volume baseline in the later regular-season sample.

## Evidence limits

- The corrected archive was already inspected. Time ordering prevents future-game inputs, but these are not unseen live results.
- Historical candidates use the most recent earlier box roster. Historical injury announcements are unavailable. Eventual final-box starters appear only in a separate conditional analysis and never tune the policy.
- Only 1 dated specific-role reference exists in the old archive. The mean known-specific-role roster fraction across tested team fixtures is 15.0%; mean unknown-position points share is 83.3%. Guard/wing validation is therefore limited.
- Completed-season analysis applies reviewed season-role references retrospectively. This does not establish each historical game’s exact role. The strict pregame test does not use later canonical references.
- New morning collections retain specific roles only when NBA’s complete positional starting five matches the PDF starters. Those postgame observations can support later games and cannot confirm an earlier pregame announcement.
- A verified 2024–25 archive is unavailable, so cross-season fallback performance is not validated. Old and current seasons remain separate.
- Bootstrap intervals include fixture and weekly-block sensitivity. They describe this retrospective sample and are not calibrated matchup confidence.

## Early-season coverage

| Market | Selections / early opportunities | Coverage | Hit rate |
|---|---:|---:|---:|
| first-team-basket | 339 / 618 | 54.9% | 20.4% |
| points | 437 / 618 | 70.7% | 46.7% |
| threes | 283 / 618 | 45.8% | 38.2% |

Early means either team has fewer than 20 competition games. With zero new-season games, each matchup retains three market slots per team using labeled prior history where an eligible current-roster player exists. Unsupported markets explain their missing evidence.

## Reproduce

```sh
node scripts/evaluate_readiness.cjs
node "nba ftb shi/tests/test_readiness.cjs"
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/build_pages.py
```

Full results, development grid, traded-player slices, ablations and uncertainty are in `nba ftb shi/readiness_evaluation.json` and in the app’s Data tab.
