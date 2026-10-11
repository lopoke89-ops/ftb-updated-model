# Parlay transition implementation report — October 11, 2026

The revised work order's Phase A transparency and Phase B isolated research implementation are complete. Phase C has a frozen protocol, outcome tools and a completed conditional diagnostic. Genuine season-transition validation and any production promotion remain unproven. Publication and deployment receipts are retained in the workspace's `parlay_transition_2026-10-11` folder.

## Delivered behavior

- Every Parlay market card shows actual current-season appearances, points and made threes separately from the season supporting its selection. Expandable details show filtered player/team/opponent counts, five-start progress, shooting pairs, positional coverage, the active candidate path, target basis and collection/publication/check timestamps. Missing data remains unavailable; verified zero appearances remain zero.
- Refresh comparisons distinguish relevant new games, changed PDF hashes, unrelated games, source checks, context changes, retained selections and evidence-basis changes. Current candidate readiness is independent of an archive-selected player's progress.
- Research is off by default. It uses fitted equivalent sample counts for volume, conversion, starting/opening and positional inputs, preserves equal one-third outer weights and the observed scoring-share safeguard, and discloses current/historical support. Five current shooting pairs activate the current correlation gate. Unsupported playoffs, incomplete evidence, unknown positional production and unsupported role changes withhold affected research output.
- Both paths use the same production-derived candidate target rule. A common G/F/C comparison cannot change the target season or confer current production eligibility. Actual season averages stay factual; research scores are not probabilities.
- Schema 3 exports preserve fixture IDs, UTC captures, model/protocol/source hashes, counts, source health, actual targets and both model outputs. Older exports import as research snapshots. The separate local ledger receives fresh pregame records, preserves linked revisions and snapshot files, settles from verified NBA PDFs, and evaluates only a consistent release cohort.

The production modules `parlay.js`, `scouting_history.js`, `analyst.js` and `lineups.js` are unchanged from baseline `4782c14102c23c0344b1f04819bd38057d09d539`. Three slots per team, availability/confirmation restrictions, season separation, position fallback/strict mode, target thresholds, team colors, shot colors and collapsible filters remain in place. The separate old local analyst journal is unchanged.

## Verification

- Nine JS suites passed: browser, analyst, scouting, readiness, Pages, Parlay, live refresh, transition and UI export. Existing numerical/eligibility checks and new tests cover zero/one observations, current-candidate transitions, missing correlations, coverage, deterministic estimates and immutable production results.
- 42 Python script tests and 8 NBA opening-parser tests passed. These exercise collector retries, schedule failures/DST, fixture deduplication, forced official corrections, preserved prior versions, stale/mixed publication rejection, source reconciliation, receipt integrity/version exclusion and linked PDF outcome corrections.
- The actual UI's Blob download payload matches the recoverable browser record, contains all six market slots, retains provisional status, and passes the target/metadata contract. The in-app browser displayed the save acknowledgement, but its automation download-event listener did not return the app-managed file path; native download delivery was not independently verified through that listener.
- Browser checks verified opening-night prior-season fallback, zero current appearances/starts, experimental isolation, clean punctuation, keyboard disclosure operation and responsive cards. At the mobile test size the document width and scroll width were both 387 px: no page overflow. Preview screenshot retained in the workspace.
- Static publication passes with 39 allowlisted assets, 1,322 archived games and 2,644 first-team scores, including 249 free-throw first scores. Current 2026–27 history correctly contains zero verified completed games before the opener. No source season data or authoritative PDFs were rewritten by this order.

## Conditional historical diagnostic

The frozen protocol was committed before reviewing these outcomes. Fitting uses the prefix through December 15, 2025; 109 later regular-season dates provide 1,686 team/fixture opportunities per market/definition. There are no captured historical injury announcements or confirmed pregame lineups, and the windows belong to the same season. DNPs count as misses. These are conditional diagnostic selections, not prospectively issued picks.

| Market | Production hits / selections | Research hits / selections | Paired difference | Paired fixture-bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: |
| First team score, FT included | 340/1686 (20.17%) | 347/1667 (20.82%) | +0.48 pp | -1.20 to +2.10 pp |
| Points | 699/1686 (41.46%) | 703/1686 (41.70%) | +0.24 pp | -1.54 to +2.02 pp |
| Made threes | 678/1686 (40.21%) | 670/1685 (39.76%) | -0.42 pp | -2.08 to +1.25 pp |
| First made field goal | 322/1686 (19.10%) | 323/1668 (19.36%) | +0.12 pp | -1.38 to +1.68 pp |

Every paired interval includes zero. The threes research ranking underperformed production, while its simple attempt-volume baseline reached 42.61%, versus 39.76% for the adaptive ranking. This supports further study of that market, not post-result tuning or immediate promotion. All results, DNP counts, withheld coverage, early sample bands, player/target differences and weekly sensitivity intervals are retained in [the diagnostic JSON](PARLAY_TRANSITION_DIAGNOSTIC.json).

## Dependencies and operating limits

Only the verified 2025–26 archive was found locally. An older verified season or frozen 2026–27 prospective records is needed for a genuine transition study. The first two operating days test live operation and collection, not predictive advantage. The current [prospective status](PARLAY_PROSPECTIVE_STATUS.json) contains no qualifying outcomes and no promotion.

The model is regular-season research only; rookies without qualifying history, projected rotations, probabilities and joint-parlay calculations remain outside scope. Frozen receipt timing uses the local runner plus a fresh source schedule and is not independent third-party timestamp attestation. Browser storage is capped; use downloaded exports and backups of the local ledger. The existing morning workflow skips complete batches and later PDF corrections require a forced recheck.

See [the operating runbook](PARLAY_TRANSITION_RUNBOOK.md), [model contract](PARLAY_TRANSITION_MODEL.md), [frozen protocol](PARLAY_RESEARCH_PROTOCOL.json) and [fitted configuration](<nba ftb shi/parlay_research_config.json>).
