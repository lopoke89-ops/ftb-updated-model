# Parlay Machine audit — October 10, 2026

The repeated names exposed an incomplete candidate pool and a selection-policy gap. Each market already had its own ranking; there was no deliberate reuse of the First Basket winner. Broad G/F labels excluded many guards and wings, leaving centers to win several incomplete comparisons. Some repetitions also occurred with complete candidate pools because the same player's evidence score led each market.

## Evidence and corrections

- Downloaded and retained all 212 NBA daily lineup files corresponding to the 2025–26 gamebook schedule. Matched each team’s full five NBA starters to the five PDF-verified starters by identity before accepting any specific roles for that team game.
- Added 13,210 dated role records for 2,642 of 2,644 team gamebooks. DAL and LAL on April 5, 2026 (ESPN fixture 401810995) did not match and remain unresolved. None of the scoring or stat values in the PDF ledger changed.
- Exact PDF positions take precedence. NBA observations can resolve broad labels on the observed game date and support later games. Carried roles do not establish exact bench roles. Retrospective downloads do not establish historical pregame announcements.
- Production selections require known positions at the displayed resolution for at least 80% of the relevant offense and opponent-allowed production. Automatic mode keeps PG/SG/SF/PF/C when supported and otherwise uses a labeled G/F/C comparison for both teams in that market. Strict five-position and forced G/F/C modes are available. Coarse labels are never guessed into finer roles. Unknown production remains in the denominator. This is an operational completeness safeguard, not a statistically optimized forecasting threshold.
- Candidate and team sample minimums now apply to every view and prior-season fallback. With the expanded role evidence, the predeclared development-grid procedure selected First Basket: 5 team games / 5 player appearances; Points: 5 / 10; Threes: 10 / 10. First Basket also requires five starts.
- Rejected candidates no longer set the minutes, attempt-volume or first-score normalization scales for eligible candidates. Each market scales its own pool.
- Each card includes a top-five candidate comparison and exclusion audit. Repeated picks are labeled as separate market rankings with potentially related outcomes. The audit export retains the comparison and completeness policy.
- Historical evaluation recomputes each sample-minimum variant separately and gives baselines matching team/player sample minimums. It separates conditional ranking diagnostics from results passing positional completeness.

## Repeat-player stress test

This diagnostic compares 870 hypothetical ordered team/opponent pairs (30 × 29), not 870 independent games or prospective predictions. It uses historical rosters and does not reconstruct historical injuries.

| Scope | Before: one player in all three markets | After: conditional rankings | After: rankings passing completeness |
|---|---:|---:|---:|
| Completed-season review | 113 / 870 | 76 / 870 | 76 / 870 combinations with all three selections |
| January 1 historical pregame | 551 / 696 combinations with three rankings | 162 / 870 | 162 / 870 combinations with all three selections |

Every pre-fix January triple had at least one market with no more than two eligible candidates. None of the post-fix triples has that thin-pool condition. Remaining repetitions are inspectable rankings, not proof of predictive superiority. The automatic G/F/C fallback supplies sufficient coverage in these two full-season diagnostic scopes. Strict mode can still withhold incomplete comparisons; any market that fails its selected-resolution coverage or sample minimum remains unavailable.

## Prediction objective still needs validation

The current Points/Threes score measures positional production and shooting opportunity. It does not estimate the chance of reaching the displayed season-average target. The observed hit rate is now explicitly labeled and shown for all compared candidates. A high FGA/FGM or 3PA/3PM correlation alone does not establish future target attainment.

The next modeling step is to estimate target-attainment probability for the same player and fixed pregame target, using expected minutes, shot volume, conversion and opponent positional allowance. Validate the positional and correlation contributions against simpler versions on time-ordered data, then record predictions before tipoff and settle them against the NBA PDFs. Keep final/provisional selections, missed coverage and DNP outcomes explicit.

The corrected archive has already been inspected. The refreshed evaluation is retrospective, historical injury announcements are unavailable, and cross-season fallback lacks a verified 2024–25 test archive. The audit fixes do not establish a live predictive advantage.

## Validation and sources

156 named JavaScript tests plus live-refresh checks; 32 Python collector/publication tests and 8 opening-play tests; strict publication build and browser verification.

- [Refreshed evaluation](READINESS_EVALUATION.md)
- [NBA daily lineup source example](https://stats.nba.com/js/data/leaders/00_daily_lineups_20251022.json)
- [Download historical NBA role captures and matched evidence](https://github.com/lopoke89-ops/ftb-updated-model/releases/download/nba-2025-26-archive/nba-2025-26-lineup-role-evidence.zip)
- [PDF archive and database release](https://github.com/lopoke89-ops/ftb-updated-model/releases/tag/nba-2025-26-archive)

Retained captures include the source URL, capture time, canonical JSON SHA-256, gamebook hash and stable player IDs. Local detailed before/after diagnostics, logs and the source archive are in `parlay_reaudit_2026-10-10` beside the repository checkout.
