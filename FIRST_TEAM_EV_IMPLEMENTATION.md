# First Team Basket in EV Bets

First Team Basket probabilities and EV are **withheld** following the October 21 ground-up audit. The previous v1/v1.1 fit retained mutable player-history arrays; later games entered recent-history features during fitting and diagnostics. Those forecast diagnostics are invalid. Original models, source and protocols are preserved under `audits/2026-10-21-ftb-leakage-repair/baseline-v1.1` (v1 is preserved under the earlier October 19 audit). Saved selections and original prices are not rewritten.

`ev-first-team-v1.2` repairs feature snapshots and refits the same declared grid and chronological windows. It is disabled in its manifest and blocked from enabling by the publication check. Fresh offered FTB prices, source-based historical summaries, opening paths and ordinary statistical grading remain usable. Count-prop engines/models/protocols are unchanged. Game First Basket and combined-parlay EV remain unsupported.

## Offer and eligibility

The Tennessee collector loads FanDuel's **Quick Bets** tab and accepts only `FIRST_TEAM_BASKET_SCORER` / **First Team Basket Scorer**. It preserves fixture, market, selection, current-roster identity, price and original capture time. The quote uses period `team-first-score`, side `yes`, null threshold, free-throws-included scoring and starter-required settlement. Game-first-basket, overtime, team-to-score-first and field-goal-only contracts are excluded.

Fresh prices appear in **First Team Basket prices** before an estimate is eligible. Each waiting row explains why EV is withheld and has no probability/EV. Market presence, a depth chart and a previous lineup do not confirm a starter. Missing/unposted markets do not renew earlier prices or suppress successful captures for other markets.

The retained scenario implementation consumes the **same `teamView` lineup resolver and shared lineup context as Parlay**. Fresh NBA confirmed fives take precedence over complete fresh projected fives. These eligibility checks remain tested for a future release, but neither lineup basis currently enables a probability or EV. No projection grants starter confirmation or changes the finalized First Team Basket requirement in Picks/Parlay.

ESPN depth-chart projections expire after six hours, NBA expected fives after five minutes. Five distinct current-roster identities/positions, exact fixture/date/season, one origin and one capture time are required. Quotes must be active, within five minutes and before either advertised tipoff. Quote/lineup expiry wakes EV immediately; saving rechecks both freshness and the exact frozen lineup. Partial, stale or incompatible fives withhold estimates.

Out/Doubtful or scenario exclusions block either lineup. Questionable/unconfirmed projected players remain provisional; unresolved Questionable availability blocks finalized confirmed-lineup estimates. The existing **Include provisional availability / role** filter, enabled by default, controls projected EV. Disabling it leaves confirmed eligible estimates only.

All five still need **20 prior same-team regular-season starts**; the selected player additionally needs three first-score wins and five losses as a starter. New-team, rookie and rotation gaps can withhold the entire lineup's EV. These guards are not relaxed to fill the screen. A complete projection alone does not establish adequate basketball evidence.

Projected probability and EV are **conditional on those exact five players starting**. No chance of starting, chance of void, unconditional return or historical projected-lineup validation is claimed. Projection details retain the actual five, source/capture time and this assumption.

## Independent probability and source evidence

`ev_first_team.js` models five competing starter outcomes plus an explicit nonstarter-first-scorer probability. These six outcomes sum to one. The five starters are not forced to sum to 100% while the other outcome is omitted. Prices for both teams are not normalized as one exclusive market. A five-starter price list that omits a possible nonstarter scorer is not exhaustive for proportional de-vig.

Features are prior same-team first-score rates as a starter, shrinkage, optional recent-20 starter history, and shrunken own/opponent G/F/C first-score rates per starting-player exposure. A roster role is not a defender assignment. The original Parlay grade is not used as a probability; count-prop attempts/makes correlation is not a first-team probability model.

Only the hash-linked **NBA PDF opening ledger** in the verified Parlay supplement supplies first-score outcomes. Legacy ESPN opening-source metadata is not an authoritative fallback. Source URL/hash, first-quarter event/page and player identities are checked. Other competitions, selected-day/later outcomes and other-team starts are excluded from the model history.

## Diagnostics and limits

No complete five-starter lineup met the 20-prior-start requirement before December 15. The separate fitting windows therefore use development through **January 15, 2026**, calibration **January 16–February 28**, and diagnostics **March 1–April 12**. The windows were selected for sample availability. Entire dates are predicted before their outcomes enter state.

Development chooses shrinkage/recent mixture and positional exponents by joint likelihood. Calibration fits a positive temperature on calibration dates only. Final-box starters define a conditional-known-lineup retrospective scenario; historical pregame announcements were not archived. The archive was already inspected and is not an untouched prospective test. Diagnostic slope/intercept are descriptive and never applied back to the production model.

| Diagnostic quantity | Result |
|---|---:|
| Development / calibration / diagnostic conditional lineups | 50 / 172 / 202 |
| Diagnostic fixtures / supported player decisions | 162 / 984 |
| Repaired binary Brier | 0.16103 |
| Start-history baseline Brier | 0.15912 |
| Uniform-starter baseline Brier | 0.16237 |
| Repaired binary log loss | 0.50174 |
| Start-history baseline log loss | 0.49614 |
| Calibration slope / intercept | 1.576 / 0.806 |
| Weighted calibration error | 0.01522 |

The repaired model performs worse than start history on these identical cases. An independent Python reconstruction matches all 984 individual probabilities within 8.4e-17 and reproduces binary losses. It imports no production math helpers; it shares the source-extracted opening ledger, IDs and historical role labels. It checks the frozen fit, not an independently optimized training run. Its exploratory 2,000-replicate fixture-cluster Brier difference interval is [0.00013, 0.00365] (positive means the model is worse). The archive was already inspected; this is not fresh evidence or prospective significance.

The engineering repair copies and freezes history entries, arrays, player rows and the feature object. The trainer asserts strictly earlier-date histories/counts/wins and checks all 424 retained lineup hashes after replaying the full archive. Regression tests append later games and mutate underlying state; retained features and predictions stay unchanged. Temperature changes from the contaminated fit's 0.49972 to 1.02021; the old fitted temperature must not be reused. The repaired model's calibration also misses the prospective gates. Prior-season transfer and future profitability remain unvalidated. Configuration, reliability bins and baseline comparisons are retained in `ev_first_team_model.json`.

[FIRST_TEAM_EV_FORWARD_PROTOCOL.json](FIRST_TEAM_EV_FORWARD_PROTOCOL.json) declares a separate prospective cohort, checkpoints and promotion criteria. Browser-local records are editable and depend on the view being open; a shared trusted issuer and independent coverage ledger remain necessary for verified public track-record claims. There are no historical FanDuel price returns or joint-parlay forecasts.

## Saving and grading

Schema-4 snapshots retain per-result model/engine/protocol/rules/forward-protocol hashes, exact lineups, original prices, display filters, supported negative offers and withheld first-team offer reasons. Withholding-only captures preserve the raw offered prices and reasons with an empty FTB result set. Earlier schema-3/4 receipts remain unchanged. Each first-team result retains its own model identity.

Grader v7 labels every v1/v1.1 FTB forecast `invalidated-temporal-leakage` and makes it ineligible for probability accuracy. This preserves its original forecast, price and ordinary contract outcome without treating a source-correct win/loss as valid model evidence. Count-prop grading behavior is unchanged.

A nonstarter is a rule-indicated void even if they later play. A starter wins if they score their own team's first points, including a free throw; another team's earlier score does not matter. Missing PDF openings remain pending; mismatched sources require review. No field-goal-only or ESPN substitution is allowed. Reports retain PDF hash, page and sequence. Projected records remain separate from the confirmed cohort; any frozen-five mismatch excludes conditional probability evaluation. Actual sportsbook settlement remains unverified. The preserved [rules profile](FIRST_TEAM_EV_RULES.json) records the original external rule check; this repair does not change market definitions.

## Verification

Rebuild only explicitly with `node scripts/train_first_team_ev.cjs --diagnostic-cases audits/2026-10-21-ftb-leakage-repair/production-diagnostic-cases.json`. Use `--output-dir` for an isolated candidate fit. Publication verifies engine/trainer/protocol/rules/archive/opening hashes, immutable snapshot checks, JSON/browser-model equality, and the disabled release state. CI runs the independent Python reconstruction. Tests cover retained-history mutation, selected-day cutoffs, the live withholding state, price-only receipts and legacy evidence invalidation as well as existing contract/lineup cases.

The October 19 quote replay remains parser/identity evidence only; it does not validate the contaminated fit. The repair evidence, preserved baseline, independent case reconstruction and remaining release requirements are in [the repair report](audits/2026-10-21-ftb-leakage-repair/REPAIR_REPORT.md).
