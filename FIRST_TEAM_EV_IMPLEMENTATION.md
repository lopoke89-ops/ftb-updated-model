# First Team Basket in EV Bets

First Team Basket is an additional market filter and participates in the all-market EV ranking when eligible. It has a separate experimental model, `ev-first-team-v1.1`. The frozen Points/Threes engine, model and prospective protocol are unchanged. Game First Basket and combined-parlay EV remain unsupported.

## Offer and eligibility

The Tennessee collector loads FanDuel's **Quick Bets** tab and accepts only `FIRST_TEAM_BASKET_SCORER` / **First Team Basket Scorer**. It preserves fixture, market, selection, current-roster identity, price and original capture time. The quote uses period `team-first-score`, side `yes`, null threshold, free-throws-included scoring and starter-required settlement. Game-first-basket, overtime, team-to-score-first and field-goal-only contracts are excluded.

Fresh prices appear in **First Team Basket prices** before an estimate is eligible. Each waiting row explains why EV is withheld and has no probability/EV. Market presence, a depth chart and a previous lineup do not confirm a starter. Missing/unposted markets do not renew earlier prices or suppress successful captures for other markets.

EV consumes the **same `teamView` lineup resolver and shared lineup context as Parlay**. The collapsible Starting lineups panel and refresh control also appear on the EV tab. Fresh NBA confirmed fives take precedence; otherwise a complete fresh projected five can support a **Projected lineup · provisional** estimate. No projection grants starter confirmation or changes the finalized First Team Basket requirement in Picks/Parlay.

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
| Binary Brier | 0.15934 |
| Start-history baseline Brier | 0.15912 |
| Uniform-starter baseline Brier | 0.16237 |
| Binary log loss | 0.49658 |
| Calibration slope / intercept | 1.146 / 0.207 |
| Weighted calibration error | 0.01284 |

The model **does not demonstrate improvement over start history**. Its intercept exceeds the declared prospective promotion limit. These small retrospective results do not qualify it for a dependable or proven-edge claim. Numerical EV is experimental research, conditional on the supplied lineup. Prior-season transfer and future profitability remain unvalidated. Model configuration, reliability bins, baseline scores and paired fixture-cluster intervals are retained in `ev_first_team_model.json`.

[FIRST_TEAM_EV_FORWARD_PROTOCOL.json](FIRST_TEAM_EV_FORWARD_PROTOCOL.json) declares a separate prospective cohort, checkpoints and promotion criteria. Browser-local records are editable and depend on the view being open; a shared trusted issuer and independent coverage ledger remain necessary for verified public track-record claims. There are no historical FanDuel price returns or joint-parlay forecasts.

## Saving and grading

Schema-3 snapshots retain per-result model/engine/protocol/rules/forward-protocol hashes, the first-team model manifest, exact five confirmations or separately labeled projections, original prices, display filters, supported negative offers and withheld first-team offer reasons. Earlier records remain unchanged. Top-level count-model metadata remains for compatibility; each first-team result has its own model identity.

Grader v3 retains count-prop behavior and adds First Team Basket. A nonstarter is a rule-indicated void even if they later play. A starter wins if they score their own team's first points, including a free throw; another team's earlier score does not matter. Missing PDF opening evidence remains pending; mismatched sources/events require review. No field-goal-only or ESPN substitution is allowed. Reports retain the PDF hash, page and sequence. Projected records belong to a separate secondary cohort. Grading records the actual PDF five and `lineupConditionMet`; when any teammate differs, the ordinary contract result is retained but `probabilityEvaluationEligible=false`. Selected nonstarters remain void. Matched projected scenarios are never pooled into the confirmed-starter primary evaluation. Original v1 confirmed records remain gradeable with their original model manifest. Actual account settlement and exceptional sportsbook rulings are unverified. See the [FanDuel Tennessee house rules](https://www.fanduel.com/fanduel-sportsbook-house-rules-tn), checked October 19, and the bound [rules profile](FIRST_TEAM_EV_RULES.json).

## Verification

Rebuild only explicitly with `node scripts/train_first_team_ev.cjs`. Publication verifies the independent engine/trainer/protocol/rules/archive/opening hashes and JSON/browser-model equality. Tests cover competing outcomes, prior dates, current-team starts, confirmations, waiting prices without EV, exact markets, availability, first-score free throws, nonstarter voids and source conflicts.

The live replay on October 19 covered **2,261 quotes**, including **139 First Team Basket offers**, across 16 fixtures, with no parser/identity differences. Live confirmed-starter EV cannot be verified before real confirmations exist. The v1 release was verified in the waiting-price state. v1.1 additionally tests complete shared projections, confirmation precedence, Questionable and exclusion policy, source/fixture/season/freshness failures, filters, saving, conditional-lineup grading, and v1 compatibility. Operational eligibility changed; numerical parameters, retrospective diagnostics and support thresholds remain exactly identical. Frozen v1 files are retained in `audits/2026-10-19-first-team-projections/baseline-v1/`.

Service-layer schema-4 guards and grader-v4 strict receipts are described in the [full EV-tab audit](audits/2026-10-19-ev-tab/AUDIT_REPORT.md). First-team fitted parameters and model hash remain unchanged. Earlier v1/v1.1 records retain their original context and are labeled legacy local records by the new grader.
