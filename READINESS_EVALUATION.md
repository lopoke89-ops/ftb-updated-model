# Opening-night readiness evaluation

Historical policy and baseline rows are conditional ranking diagnostics before the 80% positional completeness safeguard. issuedPolicy reports selections that pass the safeguard. Historical injury and starter-confirmation limitations remain; these are not prospectively issued forecasts.

## Selected sample minimums

| Market | Games for each team | Player appearances |
|---|---:|---:|
| first-team-basket | 5 | 5 |
| points | 5 | 10 |
| threes | 10 | 10 |

First Basket also requires five starts and the shared capped scoring-share grade. Points and Threes require positive attempts/makes correlation. All production selections require at least 80% known positional production on both sides at the displayed resolution. Automatic mode uses specific roles where supported and otherwise compares G/F/C for both teams; strict five-position mode remains available. That completeness safeguard is operational, not a fitted predictive threshold.

## Chronological later-date results

Development ends 2025-12-15; later evaluation starts 2025-12-16. Each sample-minimum variant recomputes normalization using its own eligible candidates. Baselines use the same team/player sample minimums. Historical DNPs count as misses; participating-player results are retained separately.

| Competition / market / target | Conditional rankings | Hit rate | Baseline rate | Rankings passing positional coverage |
|---|---:|---:|---:|---:|
| regular-season / first-team-basket / first-team-score-including-free-throws | 1686 / 1686 | 21.6% | 21.6% | 1686 |
| regular-season / first-team-basket / first-team-made-field-goal | 1686 / 1686 | 20.4% | 20.3% | 1686 |
| regular-season / points / first-team-score-including-free-throws | 1686 / 1686 | 40.5% | 38.8% | 1686 |
| regular-season / threes / first-team-score-including-free-throws | 1686 / 1686 | 40.6% | 41.1% | 1686 |
| playoffs / first-team-basket / first-team-score-including-free-throws | 90 / 170 | 22.2% | 15.6% | 90 |
| playoffs / first-team-basket / first-team-made-field-goal | 90 / 170 | 24.4% | 17.8% | 90 |
| playoffs / points / first-team-score-including-free-throws | 42 / 170 | 45.2% | 47.6% | 42 |
| playoffs / threes / first-team-score-including-free-throws | 38 / 170 | 36.8% | 44.7% | 38 |

Aggregate baseline coverage can differ. The paired fixture and weekly-block comparisons in the JSON report assess improvement on common games. The same corrected archive was already inspected; these are retrospective diagnostics and do not establish an unseen live advantage.

## Position evidence

The archive now contains 13211 dated role records. NBA role files matched 2,642 of 2,644 PDF team starting fives. The two unmatched team lineups are retained as unresolved. Mean known candidate-roster fraction in the test is 72.8%; mean unknown specific-position points production is 15.4%. Automatic G/F/C comparisons account for 2740 of 10520 market records.

Pregame tests exclude later canonical season-role references. Specific roles are dated postgame NBA observations matched to all five PDF starters; the latest earlier observation can support later games but does not prove an exact bench role or a historical pregame announcement. Automatic comparisons fall back to gamebook G/F/C groups for both teams when specific coverage is incomplete. Cross-season performance is unvalidated.

PDF final statistics and opening events remain authoritative. Exact PDF positions take precedence. Earlier NBA role observations may be carried forward to later appearances; they do not establish exact bench roles.

## Remaining limits

- Historical injury and pregame lineup announcements are unavailable. Eventual actual starters appear only in a separately labeled conditional analysis.
- A verified 2024–25 archive is unavailable; cross-season fallback performance is unvalidated.
- The equal one-third components and positive-correlation requirement remain. Evidence scores do not estimate the probability of reaching a season-average target.
- Prospective timestamped selections are needed to assess the deployed workflow.

## Reproduce

```sh
node scripts/evaluate_readiness.cjs
node "nba ftb shi/tests/test_parlay.cjs"
python scripts/build_pages.py
```

Full results, development grids, ablations, coverage and uncertainty are in `nba ftb shi/readiness_evaluation.json`.
