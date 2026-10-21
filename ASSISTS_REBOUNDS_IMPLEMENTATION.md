# Assists, Rebounds, and daily research scorecards

Implemented locally October 21, 2026. Not committed, pushed, or deployed. This is an experimental market extension, not a model-promotion or profitable-edge claim.

## What is implemented

- EV supports ordinary full-game Assists and Rebounds over/under offers and the exact FanDuel To Record X+ milestone formats. The read-only Tennessee collector now checks five market tabs on the existing five-minute schedule.
- New probability models are separately versioned as ev-assists-rebounds-v1, with separate protocol, forward protocol, rules profile, model/engine/trainer hashes, and chronological diagnostics.
- Parlay adds two descriptive research slots per team, with source season, actual through date, sample, historical average/season-average target, candidate comparisons, availability, positional coverage and exclusions.
- Rebounds use player total rebounds = offensive + defensive rebounds. The Parlay cards and EV detail show the offensive/defensive split. Unassigned team rebounds are excluded.
- Daily research scorecards separate points, threes, assists, rebounds, and FTB, then split over/under/milestone types. A single latest saved complete-supported-offer snapshot is chosen per fixture; selecting another later game does not discard earlier-game records. Original timestamps, filters and coverage remain available.
- Saved EV exports bind the new market model identity separately. Official-box grading handles wins/losses/pushes/DNP voids, pending finals, source conflicts and missing-stat review without substituting zero.

Original Points, Threes and FTB model parameters, original Parlay engine and historical saved research were preserved. The baseline hashes are in frozen-baseline-hashes.json. Original October 20 outcomes were regraded: 134 wins and 210 losses across its 344 supported offers; its displayed 63 reproduce 20-43 and -0.2431 illustrative units.

## Basketball and scope

EV uses at least 20 complete prior appearances with the current team, at least 10 games per team and 80% known-role player-minute coverage. Other-team appearances are explicitly excluded from EV. Complete zero-minute played rows are still appearances; no positive recorded exposure withholds the forecast. Selected-day and later results are excluded.

New Parlay slots are descriptive and retain the existing five-appearance/five-team-game minimum so last-5/10/20 controls remain usable. Season-average targets are computed from the full selected competition at the same cutoff; the observed hit count uses the selected statistical window. Prior-season fallback can follow player identities across stints when selected and is labeled. Head-to-head limits the rows to the displayed team/opponent.

Each new Parlay evidence score equally weights positional own production share, opposing positional allowance share, and a historical opportunity proxy. The proxy equally weights relative recorded minutes and relative credited-stat rate among eligible candidates. Potential assists, rebound chances, defender assignments and conversion rates are not observed or invented. There is no positive shooting-correlation requirement for these new count categories. Original three-market ranking rules are unchanged.

New Parlay exports retain source-linked additional-market research separately from the original three-market prospective cohort; they are not promoted into that cohort or treated as probabilities. No joint-parlay EV is calculated.

## Separate retrospective validation

Protocol: development through December 15, 2025; calibration December 16–February 15; diagnostics February 16–April 12, 2026. Candidate configurations were selected on development dates only. CDF calibration used calibration dates only. Same-observation calibrated season-mean and recent-20 baselines are reported. The completed archive was already inspected, so these are retrospective diagnostics.

| Market | Supported appearances | Fixtures | Brier | Season-mean baseline | Recent-mean baseline | Log loss | Weighted calibration error |
|---|---:|---:|---:|---:|---:|---:|---:|
| Assists | 7059 | 411 | 0.19799 | 0.20263 | 0.19856 | 0.58104 | 1.06% |
| Rebounds | 7093 | 411 | 0.18451 | 0.18762 | 0.18531 | 0.54954 | 1.18% |

Each appearance has total weight one across its supported thresholds. Alternate lines are correlated. The independent auditor reproduced the trainer metrics, reconstructed 31,120 prior-only feature sets directly from raw box records, checked 28,716 player appearances and all rebound split equations, and generated 1,000-replicate paired fixture-cluster intervals. Both markets passed the declared experimental gate against the calibrated season-mean baseline. This is not prospective approval or a historical odds-return study.

Support withholds thresholds outside the separately fitted range or lacking five prior wins and five prior losses at the exact target. Current projected role changes are withheld. Unsupported prices, missing identity joins, stale/cached/suspended quotes, unavailable histories and failed model validation produce explicit exclusions.

Static publication checks require matching model content, engine, trainer, protocol, forward protocol, rules, browser payload, and independent-audit hashes. A mismatched or missing validation artifact stops publication.

## Rules and source evidence

[FanDuel Tennessee house rules](https://www.fanduel.com/fanduel-sportsbook-house-rules-tn), effective October 15, 2026 and checked October 21, state that ordinary player performance totals include overtime, have action once the player takes the court, and void for no participation. The new rules profile excludes promotions, combos, partial periods and joint-parlay settlement. Project statistical outcomes remain distinct from sportsbook account settlement and later official corrections.

The live read-only Atlanta–Orlando capture obtained 67 assists offers and 80 rebounds offers without source issues, alongside the three existing market categories. Browser verification used those real captured prices in an explicitly marked local transport replay; the production odds branch was not changed. Screenshots are ev-assists-browser.png and ev-rebounds-browser.png. The local replay is not a source-verified GitHub publication or authenticated pregame receipt.

## Checks and publication status

Focused engine, exact-contract, scope, grading, missing-data and UI checks are in tests/test_additional_markets.cjs, tests/test_ev_ui.cjs and tests/test_ev_scorecard.cjs. Existing Parlay, EV, source/collector and publication checks are also run; final results are recorded in this audit folder.

The broader list is now implemented and locally verified in [the completion audit](audits/2026-10-21-complete-improvements/AUDIT_REPORT.md): the new-font PDF importer, independent points-ladder trace, daily scorecard, and source-linked opening rebound paths. Current-season box scores and opening paths cover three games; full-game events are verified for two and partial for OKC–San Antonio. This extension does not claim complete current-season event coverage.

No production deployment or account betting actions were performed.

## Final local verification

All 27 JavaScript commands from the publication workflow passed, including the independent raw-record audit. The full Python suite passed 79 tests; the final publication suite additionally passed 10 tests after the last packaging changes. The final 75-asset publication package was built successfully, and its new browser files match the working sources. All six original frozen-file hashes still match.

Final browser evidence covers Assists/Rebounds EV, ungraded scorecards, ATL–ORL and GSW–LAL, last-5/10/20 windows, insufficient head-to-head samples, and missing current-season data. The final read-only capture contained 64 assists and 80 rebounds offers; market counts changed naturally since the earlier capture. Screenshots are ev-assists-final.png, ev-rebounds-final.png and parlay-counts-final.png. New tail estimates sometimes differ sharply from bookmaker prices; passing retrospective checks does not validate those individual prices or establish a betting edge.

The preview remains a clearly marked local transport replay. The release folder itself contains no replay script. No mobile-device browser pass is claimed. The opening-night regression was rerun with the final scorecard implementation and preserved the original outcomes. See verification-summary.json and javascript-checks.json.

## Completion follow-up — October 21

The completion audit supersedes the earlier packaging and mobile-check status above. Its final package contains 77 assets; the complete Python suite passed 88 tests plus the eight opening-gamebook checks. A real 390 × 844 browser viewport passed the scorecard and opening-path overflow checks. Main code and the website have not been deployed by this completion pass.
