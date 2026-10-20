# Full-game play-by-play release audit — 2026-10-19

The downloaded 2025–26 archive is fully verified against the work order's required statistical and event-identity checks: **1,322 verified games, zero partial or quarantined games, zero required unresolved context roles, and zero discrepancies**. This report records the local release checks. Actual publication status and deployed commit are recorded in the [release notes](https://github.com/lopoke89-ops/ftb-updated-model/releases/tag/full-game-pbp-2025-26-v10).

## Coverage and provenance

- Canonical starting checkout and remote: `dd70188aa2cf3bde662ae744d7800ea0937ab100`, initially clean.
- Source: 1,322 immutable NBA PDFs, 159,045,415 bytes; 1,230 regular-season games, 85 playoff games, six Play-in games and one Cup final. Statistics through June 13, 2026.
- Active ledger: **689,825 events**; 1,262 four-period games, 51 single-OT games and nine double-OT games. All 14 supported statistical components reconcile in every game.
- Parser `full-game-pbp-v10` (canonical LF source bytes, checked against the staged Git objects); parser and identity resolver code hashes, PDF hashes, source URLs, page/line spans, clocks, order, printed descriptions, identities, scores and interpretation methods are retained. The final manifest content hash is `350990ed9dacd893bac9b21402bc2e98b312a4193455bce8c15c69a2a11a5924`.
- The local ledger retains all development revisions. Historical parser source newline bytes were restored only where SHA-256 proves an exact match to the original stored parser hash; all retained parser source hashes now pass the independent audit (`parser_byte_provenance.json`). The 11,896,500,224-byte SQLite compresses to 1,758,845,107 bytes. The archive includes original PDFs, 75 immutable identity captures, parser sources, revisions and active pointers. The compressed file was read back completely and matched the original database SHA-256. See `release_archive.json` for both digests and its release download URL.
- `release_coverage.json`, the source manifest and empty `play_by_play_discrepancies.json` are the final coverage authorities. `parser_revision_history.json` indexes retained interpretations.

## Resolution of the previously partial archive

The fixes interpret source evidence and preserve its original text; they do not replace PDF credits with another provider's statistics or allocate credits merely to fit final totals.

1. Same-initial collisions and surname-only Yang actions use exact same-game event identity evidence where the official text alone is insufficient. The preserved ESPN capture must match the game and both teams, period, clock, action/role, verified same-game roster ID, candidate constraints and available score, shot value/result, FT ordinal or resolved counterpart. Every compatible match must agree on one actor. The audit found 1,196 roles resolved this way and 857 roles uniquely supported by official period boxes. Capture hash and matched play IDs are retained; capture hashes participate in revision identity. Team rebounds and turnovers never receive individual identities through this crosswalk.
2. Neutral-site quarter boxes with printed team names are recognized in addition to HOME/VISITOR labels.
3. Ten period-start score snapshots precredit a subsequent same-clock technical free throw. Both printed and effective interpretations are retained, and scoring advances on the actual free throw.
4. Wrapped technical-foul recipients, hyphenated names, double technicals, DNP recipients, explicit team bench/timeout/delay subtypes and printed non-player recipients retain distinct roles. Technical/team events never become pooled personal-foul statistics.
5. Five team rebounds were printed in a column inconsistent with the explicit team name. The unique printed team name controls the team credit; the original source column and interpretation remain attached.
6. The archive contains 1,153 printed team heaves. They establish the preceding missed-attempt basis for rebounds, without creating player FGA. This resolved the remaining rebound-split deficits.

The identity audit verifies all captured hashes and every retained crosswalk play/actor link, and finds zero team-only credits assigned to individuals. Its method-frequency label “unresolved same-game abbreviation” also includes explicit team/deadball records; these are not required unresolved player identities. Required unresolved context is zero. See `release_identity_audit.json` and the source-case regression fixtures.

## Implementation and preserved behavior

The full-game ledger reconciles final scores, period coverage and shooting, and player FGM/FGA, 3PM/3PA, FTM/FTA, points, assists, steals, blocks, turnovers and offensive/defensive/total rebounds. Component acceptance and retry state remain separate from verified boxes. Future failures explicitly withhold affected event context while independent box views stay usable.

Matchup adds Threes and compact pooled FG/2P/3P/FT makes, attempts and conversion in both directions. Zero attempts means conversion unavailable. It separately exposes assisted makes by passer role, blocked attempts by shooter role, printed-distance coverage and First Team Basket context. Historical G/F/C labels remain appearance-specific; strict positions use complete, hash-linked same-game five-position starter evidence where supported. Broad bench roles remain Unknown in strict mode. Roles and blocks do not identify actual defenders.

Season, competition, date, exact-opponent, rolling-history, position and normalization controls remain active. Per-game, share and per-48 player-minute denominators retain their definitions. Pregame evidence excludes selected-day and later outcomes. Core statistics remain sourced from independently verified final boxes. Team colors, collapsible controls and responsive layout remain intact.

The separate event queue processes completed-box/pending-event games, changed PDFs, forced retries and source revisions. Collection retains five-minute live-feed checks and seven America/Chicago morning checks at 08:00, 08:30, 09:00, 09:30, 10:00, 10:30 and 11:00. Source processing occurs during collection/backfill. Compressed, hash-checked ledger snapshots and immutable identity captures use the existing release archive and durable state branch. Hashing large archive assets streams the file rather than reading it into memory.

Frozen analyst, box/opening, Parlay, EV/model and research inputs are byte-identical to the starting release; see `frozen_inputs.json`. No rankings, EV probabilities, eligibility rules, model weights or saved research were redesigned.

## Independent checks and browser evidence

- Independent event/box/hash/sequence recount: **404,680 checks, zero differences**, all 1,322 games; SQLite integrity `ok`, no foreign-key violations.
- Independent opening audit: **29,084 comparisons, zero differences**, all 1,322 games.
- Independent shooting display audit: **96 scope combinations, 133,632 comparisons, zero differences**, both directions, competitions, rolling windows, opponent filters, positions, conversion and normalization.
- Python: **77 script tests plus eight opening-parser tests passed**. Twelve focused ledger tests cover regulation/double OT, repeated clocks, continuation lines, source edge cases, ambiguous identities, unique crosswalk matching, wrong-game/hash rejection, team-only credits, missing periods, revised/corrupt PDFs, retries, atomic transactions and archive restore/failure.
- All **21 JavaScript regression suites passed**, including Parlay, EV, Matchup, browser and collection-related views. See `release_browser_regressions.json` and `release_python_checks.json`.
- Identical-input and forced single-game retries retain manifest identity, row counts and active pointers; see `idempotence.json`.
- Actual final-candidate browser checks cover BOS–DET shooting, PHI–NYK last-five assists and OKC–SAS strict historical pregame. OKC's previously incomplete pregame sample now displays **29 fully verified / 29 scoped games**, with evidence ending December 22 before the selected December 23 game.
- Independently checked displayed values include BOS guards 817/2,264 threes (36.1%) versus 643/1,959 (32.8%) allowed by Detroit to opposing guards; PHI's last-five assist context is 107 linked records, comprising 64 guards, 24 forwards and 19 centers.
- `release_browser_cases.json` preserves final visible text. `release-bos-det-shooting.png` and `release-okc-sas-pregame.png` show final browser evidence. Earlier browser-control/mobile/source-page reports and screenshots document the broader filter matrix, unavailable states, small-screen layout and visual source traces. Early sample/validation/retry files are retained development evidence, not final coverage claims.

## Scope limits and release operations

“Fully verified” applies to this downloaded archive and the work order's specified checks. It does not mean every bench appearance has a supported five-position assignment, personal fouls have been reconciled as a new model, or exact defenders/lineup stints/possessions have been reconstructed. Lineups, pace, opponent-adjusted forecasting, model training, calibration and EV redesign remain deferred.

The live service is published by the existing Pages workflow after pushing the verified implementation. Publication must be confirmed by workflow success and the public asset hash/browser checks; a local build or queued workflow alone is not deployment. See the release notes for that final status. The source ledger is a release asset rather than a browser download dependency. Revert the additive code/assets together to roll back; keep manifests paired with their parser and preserve the separate source archive.
