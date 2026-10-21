# FTB Scout improvement-list completion audit

Verified locally October 21, 2026. Base checkout: `3a3d6a3`. Existing working changes were retained. This report covers the five requested improvements and their integration with the separately validated Assists/Rebounds extension. It does not declare all current-season play-by-play complete.

## Delivered behavior

| Request | Implemented and verified behavior |
|---|---|
| Actual starters in Picks | Upcoming feed defaults to complete, fresh NBA-confirmed starting fives. The projected-starter view is an explicit opt-in and labels provisional players. Freshness, missing confirmations, and exclusions remain visible. Historical season review remains available. |
| Extreme points-ladder audit | Independently reconstructed all 103 saved points ladders, with 1,236 numeric comparisons. The points-ladder details show historical minutes and hits, fitted variability, conversion probability, break-even, and EV arithmetic. No original model weights were changed. |
| New-gamebook ingestion | Shared PDF text fallback handles the new font, box columns, wrapped play descriptions and clock-only rows. All three October 20 games entered the normal verified box/opening pipeline. Unchanged retries, revised sources, failed replacements, identity failures and retained earlier sources have regression coverage. |
| Daily scorecard | Market totals precede bet-type totals; FTB, points, threes, assists and rebounds remain separate. Ordinary overs, unders and alternative ladders are distinct. Primary records are chosen per fixture; repeated captures are not extra bets. Original prices, timestamps, model versions and lineup assumptions are preserved. Pending and review cases do not become losses. |
| Opening attempts and rebounds | Picks, Parlay and Matchup expose initial attempts, makes, offensive rebounds before the team's first score, printed putbacks and direct rebound finishes. Source paths preserve intervening turnovers and team/dead-ball credits. First score including free throws and first made field goal are separate definitions. |

Assists and Rebounds EV/Parlay models remain experimental and have separate protocols, diagnostics and publication gates. Their retrospective validation does not establish a profitable live edge. See `../../ASSISTS_REBOUNDS_IMPLEMENTATION.md` and the adjacent Assists/Rebounds audit folder.

## What creates the Keldon Johnson 20+ estimate

The original +1700 offer implies decimal odds 18 and a 5.56% break-even probability. The saved model's 24.21% win estimate produces `0.2420578 × 18 − 1 = +335.70%` EV. That arithmetic reproduces independently; it is not approval of the probability.

The input history has 82 same-team appearances, 13 previous 20+ results (15.85%), 13.18 average points and 23.31 historical minutes. The blended historical exposure is 23.50 minutes; this is a historical proxy, not a game-specific minutes forecast. Reconstructed shooting opportunities are 11.35 FGA, 4.07 three-point attempts and 2.67 free-throw attempts. After the existing positional adjustments, raw scoring mean is 14.21; calibrated mean is 14.53.

Observed historical scoring standard deviation is 6.00. The fitted count distribution's raw standard deviation is about 7.73; its raw 20+ tail is 21.84%, then the existing CDF calibration increases it to 24.21%. Historical exposure, fitted variance, calibration and long offered odds explain the large EV. Exposure sensitivity changes the tail sharply: at 75% of the historical exposure proxy it is about 10.42%; at 50% it is about 1.76%. These are sensitivity scenarios, not replacement forecasts. One night's outcomes were not used to refit weights.

Evidence: `points-ladder-audit.json`, `../../scripts/audit_points_ladders.py`, and the saved source fixture. The independent audit reconstructs minutes, shooting opportunities, positional shrink ratios, count probabilities and quoted EV rather than importing the production probability implementation.

## Verified source coverage and corrections

The 2025–26 archive has 1,322 games and 689,825 active events. Independent reconciliation performed 404,682 checks across the 14 additive components, with no differences. It includes 51 single-overtime and nine double-overtime games. Database integrity and foreign-key checks passed. This reconciliation shares the retained identity evidence; it does not establish exact defenders, possession counts or lineup stints.

The opening-path audit reconstructed 5,288 team/definition targets, 5,659 misses, 1,130 player offensive rebounds, 213 printed putback finishes and 689 cases where the rebounder made the next recorded attempt. Its 54,364 checks had no failures. The compact browser preload is approximately 8.01 MB uncompressed / 485 KB gzip; full ledgers are not processed on browser refresh.

Current-season coverage is three verified box/opening games, 84 box rows, 68 played appearances and zero unresolved played-box identities. All 12 team/definition opening paths are verified. Full-game events are verified for BOS–DET and PHI–NYK; OKC–SAS remains partial. The coverage/discrepancy report retains 17 discrepancy entries arising from six ambiguous stat actors and their unreconciled totals, plus separate unresolved technical-foul context. These are not 17 independent missing plays. Affected components are withheld. Verified box totals and separately verified opening paths remain usable.

NBA revised the PHI–NYK and OKC–SAS PDFs during this audit. The revised OKC–SAS source restored previously omitted late shot descriptions and corrected Shai Gilgeous-Alexander, Alex Caruso and Jared McCain rebound/steal credits. Original and revised PDF hashes and old records are retained. See `official-source-corrections.json`. Neither a changed PDF nor an unavailable replacement silently overwrites the old source history.

The remaining J. Williams identities cannot be assigned merely to force box totals to match. Conflicting provider score/clock evidence remains explicit. **The current-season full-game archive is not a fully verified release.**

## First-night scorecard reproduction

The original in-app record grades 344 supported offers as 134 wins and 210 losses. Its 63 displayed selections grade 20 wins and 43 losses. At one illustrative unit per displayed selection and the originally recorded odds:

| Market | Selections | Wins | Losses | Illustrative net units |
|---|---:|---:|---:|---:|
| First Team Basket | 5 | 2 | 3 | +6.700 |
| Points | 31 | 7 | 24 | −8.470 |
| Made threes | 27 | 11 | 16 | +1.527 |
| Total | 63 | 20 | 43 | −0.243 |

Points ladders were 2/22 and −8.800 units; points unders were 5/9 and +0.330. Threes ladders were 2/14 and −1.000; threes unders were 9/13 and +2.527. These are editable saved-research statistics, not authenticated pregame issuance, independent trials, account returns or bookmaker settlement.

The final feed changed OKC–SAS's displayed start time by 20 minutes. An explicit fixture review binds the original saved fixture, actual game ID, date, teams, phase and exact NBA PDF hashes. The grader accepts only those reviewed source versions; unrelated or tampered fixture mismatches remain under review. Original pregame timestamps and receipts are unchanged.

## Browser and regression verification

All 28 JavaScript publication commands passed, including existing EV, Parlay, Matchup, lineup, refresh, export and additional-market checks. The full Python suite passed 88 tests; the separate opening-gamebook suite passed eight. The seven real-PDF regression tests were also rerun after the final opening-path change. All six original frozen engine/model/history hashes match the starting baseline.

Browser checks used the built publication output with the original saved October 20 snapshot copied to an explicitly marked local test origin. The publication package contains no replay/seed script. Checks covered all three opening-night matchups, current-season partial event coverage, strict/broad positions, FT/FG definitions, head-to-head, last-5/10/20 controls, same-day pregame exclusions, insufficient Parlay samples, confirmed/projected starter controls, original-price disclosure and scorecard pending states. Source-record comparisons independently reproduced Collins and Bridges rebound finishes.

A real 390 × 844 browser viewport showed document width 387 pixels. Opening tables retained 700-pixel internal scroll areas inside 323-pixel containers. The scorecard also stayed within the viewport. This is responsive-browser evidence, not a physical-phone device test. Desktop and mobile screenshots are retained in this folder. Stale live prices were correctly excluded during the final pass; they were not refreshed by changing source capture times.

The final publication package has 77 assets in `.build-tests/complete-improvements-final-v3-20261021`. `verification-summary.json` records checks and package hashes. `git diff --check` passed.

## Publication handoff recorded before release authorization

Application changes are local and uncommitted; no main-branch push or website deployment was performed in this completion pass. Original public NBA PDFs, revised sources, box databases and compressed current event data were uploaded through the existing monthly GitHub release archive. Those archive uploads do not deploy the new application.

The durable `automated-data` branch was read and merged into a local release candidate, retaining all 11 older batches and the new October 20 batch. The prepared candidate is `.pbp/20261021-release-durable-state`; it has not been pushed. Publishing its three-game state before the application update would expose the older publication checks to a dataset shape they do not yet expect. Release the tested code and merged collector state together, then verify the resulting Pages deployment. Retain pending schedule checks and partial event work separately from completed box batches.

Live polling remains every five minutes. Morning PDFs remain 8:00–11:00 AM America/Chicago at 30-minute intervals. No bets or account transactions were performed.

## Release authorization

The user subsequently authorized publishing this implementation on October 21, accepting that ambiguous OKC Williams events can remain excluded. This accepts partial event coverage for the release; it does not resolve those identities or waive box-score verification. Verified OKC boxes and independently verified opening paths remain usable. The pre-release status above records the implementation handoff; the release receipt and GitHub Pages run establish actual deployment status.
