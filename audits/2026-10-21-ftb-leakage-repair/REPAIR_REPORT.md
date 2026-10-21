# First Team Basket leakage repair — October 21, 2026

Starting revision: `625a9e9dd56274bdcf1b8cb1ad01329690d257d2`.

This is the first implementation phase following the completed ground-up audit. It repairs finding F01 and withholds the affected forecasts. It does not implement the collector, release-parity or prospective-issuance recommendations, and it does not establish a betting edge.

## Result

The FTB model is now `ev-first-team-v1.2`, with `enabled: false`. Probability and EV are unavailable for both confirmed and projected lineups. Fresh valid offered prices remain visible with the withholding reason and are retained in coverage-only research captures. Historical grades, opening paths, original source records and the count-prop models remain available under their existing limitations.

The repaired fit agrees with an independently written Python record reconstruction, but it performs worse than the simpler start-history baseline on the inspected diagnostic sample. Keeping it disabled is therefore a forecasting decision as well as protection against reusing the contaminated fit. An engineering pass does not qualify this market for release.

## Defect and correction

The original `features()` saved `history: r.history`. Each chronological fitting row held a pointer to the live state. Later `addGame()` calls extended that history before candidate selection, calibration and scoring. Scalar starts/wins stayed at the earlier date while the recent-20 component included later games. Merely building the row before its game did not prevent this leakage.

The repair copies every history entry and freezes the entries, array, player rows and feature object. The trainer records a SHA-256 fingerprint when it retains each row. After the whole archive replay, it verifies that all 424 fingerprints remain unchanged and that every retained history is strictly earlier than the predicted date, with counts/wins consistent with the feature totals. Same-day state and out-of-order updates fail the cutoff. Public prediction handles an invalid feature snapshot by withholding it; the trainer fails rather than continuing a fit.

The same candidate grid, source archive, support minimums and chronological windows are retained. The original v1.1 engine, trainer, model JSON/browser payload and three bound policies are preserved byte for byte in `baseline-v1.1/`. v1 remains in the October 19 baseline. The older models are never silently upgraded or reassigned to the new cohort.

The repaired fit selects the same non-temperature grid parameters (prior 100, recent weight 0.5, offense exponent 0, defense exponent 0.5). Calibration temperature changes from **0.49972 to 1.02021**. Keeping the old fitted temperature after copying histories would not repair the contaminated training.

## Retrospective comparison

All comparisons below use the same 202 supported team lineups in 162 fixtures, with 984 supported player decisions. Each team lineup has total binary-decision weight one. Both teams and their players stay together in fixture-cluster resampling. Development contains 50 lineups; calibration contains 172. Development ends January 15; calibration ends February 28; diagnostic dates run March 1–April 12, 2026.

| Frozen repaired predictor | Binary Brier (lower is better) | Binary log loss (lower is better) |
|---|---:|---:|
| Repaired candidate | 0.16103016 | 0.50173505 |
| Calibrated start-history baseline | 0.15911917 | 0.49613643 |
| Uniform starters plus explicit other-scorer residual | 0.16237355 | 0.50588425 |

The independent Python implementation reconstructs prior team/player/role counters and recent histories directly from records, without importing the JavaScript feature or probability helpers. All 984 individual candidate probabilities match the saved production cases within **8.33e-17**. Outcomes and weights match; aggregate candidate and baseline losses match within 1e-10. The independent 2,000-replicate paired fixture-cluster Brier difference interval versus start history is **[0.0001319, 0.0036455]**. Positive differences favor the baseline. This is an exploratory diagnostic, not prospective significance.

The reference still shares the identity mappings, extracted official opening ledger and historical role labels. It verifies the frozen configurations; it does not independently optimize the candidate grid or temperature. Final-box starters define the historical conditional-five scenario. These records do not establish that lineups, role labels or later source corrections were available before tipoff. The archive and its outcomes had already been inspected. No untouched holdout or historical sportsbook-price profitability is claimed.

Calibration slope **1.576** and intercept **0.806** also miss the declared prospective gates. The small conditional sample and unvalidated cross-season transfer remain limitations. The refit must not be presented as improved merely because the leakage is fixed.

## Receipts, display and release protection

Grader v7 preserves original v1/v1.1 receipt data, prices and statistical win/loss/void outcomes. It adds `forecastEvidence: invalidated-temporal-leakage`, an explanation, and `probabilityEvaluationEligible: false`. A correct source-based outcome does not rehabilitate a defective forecast. Projected/confirmed cohorts and frozen-five mismatch checks remain separate. No original saved research is edited.

The EV panel explains withholding before the table and labels the repaired diagnostics as retrospective and disabled. Its current fresh-price waiting rows contain no probability or EV. Coverage-only records preserve the raw offers and reasons even when there are no supported estimates. A publication test deliberately enables the manifest and confirms that the exporter blocks release. Source, trainer and policy hash checks remain enforced. CI also runs the independent Python reconstruction against the frozen case evidence.

The low-level distribution helper remains available for offline research and tests. Synthetic numerical/contract tests explicitly use an enabled test fixture; that fixture is not written to the deployed model. The live engine test uses the actual disabled model and proves prices are preserved without forecast output.

## Reproduce and inspect

Run with Node.js and the collector's Python dependencies installed:

```sh
node "nba ftb shi/tests/test_ev_first_team.cjs"
node "nba ftb shi/tests/test_ev_ui.cjs"
python -B audits/2026-10-21-ftb-leakage-repair/reference_first_team.py
python -B audits/2026-10-21-ftb-leakage-repair/verify_repair.py
```

`verify_repair.py` runs every JavaScript test file, Python collector/publication tests, opening parser tests, the independent reference, an isolated repeat fit, and a new publication build. It checks the preserved baseline against the starting commit and verifies that archived data and the other frozen engines/models/policies are unchanged. `VERIFICATION.json` records results; local raw logs and duplicate candidate models are ignored by Git. The training command never runs a collector or publishes.

Evidence files: `FIRSTTEAM_INDEPENDENT.json`, `production-diagnostic-cases.json`, `training-summary.json`, the baseline files and `VERIFICATION.json`.

Verification completed successfully: **24 JavaScript test files, 89 Python collector/publication tests, eight opening-parser tests**, independent replay, byte-identical isolated repeat fit and the publication build. After making the withholding notice more prominent, the 29-check EV UI test and publication build passed again. The final browser preview was checked at desktop size and 390 × 844; `desktop-preview.jpg` and `mobile-preview.jpg` preserve the display. During that check the actual feed was older than five minutes, and all 3,752 stale offers remained excluded. Fresh FTB price-only behavior is established by the real-engine UI fixture rather than a claim that fresh real offers were observed. Browser checks used the localhost origin, whose automatic research records are separate from the deployed origin and are not prospective evidence.

The source-only repair is prepared for review. No production deployment, collector invocation or publication workflow dispatch was performed during local verification.

## Remaining work, in order

1. **Collector component separation (confirmed defect):** publish independently verified final boxes when opening extraction fails; retry missing openings separately. Acceptance must include count-prop availability, event-feature withholding and correct denominators. A backend-only patch that lets missing openings become FTB losses would be unsafe.
2. **Bounded source revision checks (confirmed operational gap):** recheck recent completed batches on an explicit cadence, preserve prior accepted source versions on partial failure and report attempt versus successful-source times separately. Do not recollect merely to validate this repair.
3. **Local/deployed release parity (confirmed drift):** unify the desktop launch target with the validated release while preserving the sibling local server, saved research and journals. An indiscriminate folder overwrite would lose capabilities or evidence.
4. **Prospective capture and evaluation (new infrastructure):** an independent expected-fixture/offer ledger and trusted append-only pre-tip issuer, with a new versioned cohort. Browser-local research cannot supply those guarantees. Grade availability, exact-five conditions and missing checkpoints before interpreting forecast scores.
5. **Count-prop tail and role research (new model/evaluation work):** predeclare ordinary over/under versus ladder strata, minutes/role sensitivity, comparable baselines and clustered uncertainty. Do not tune caps or weights to one extreme Keldon result or one night.

FTB probability/EV stays withheld unless a later explicit release changes the gate with a documented validation decision. Completing the independent arithmetic replay is necessary engineering evidence, not sufficient forecast evidence. No collector state, source ledger, saved selections, other market weights or scheduled production jobs are changed in this phase.
