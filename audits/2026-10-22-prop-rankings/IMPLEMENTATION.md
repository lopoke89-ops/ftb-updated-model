# Prop matchup ranks and stat sheet

Starting live release: `548bf5c1e009201a138feae0910a4fb8a1980410`. Context version `ev-context-v2`; presentation `prop-sheet-v1`. Research display only; source records, models, engine weights, probability/EV calculations, offer eligibility and EV-table selection ordering remain unchanged.

## User-facing behavior

EV Bets gains an expandable **Matchup stat sheet** grouped by fixture and offensive team. Fresh projected/confirmed starters appear first, explicitly labeled; other roster players remain in a separate expandable section, with injury/exclusion reasons. All four supported count stats appear together: points, made threes, assists and rebounds. PG/SG/SF/PF/C use accepted dated five-position starter records. G/F/C fallback covers known played appearances and is labeled separately.

Each stat shows the opponent’s most-allowed rank, actual allowance per 48 credited player-minutes, the exposure-weighted reference excluding that opponent, percentage difference, matched/expected games and actual date range. Latest available season same-team player production and historical minutes are descriptive. The highest estimated EV among existing supported fresh offers can appear with exact side/line, price, win/push probabilities, EV and exact-target historical W/L/push counts. These roster research rows are not additional displayed betting selections. Missing/expired/unsupported offers have no EV; historical research remains readable during a price outage.

Current and prior seasons are separate packets with separate position/cohort labels. If a tiny current sample falls back to G/F while the archive has verified PG/SG/SF/PF, the archive retains the exact cohort and labels it. Sparse current evidence is expandable; usable prior-season research stays visible and explicitly dated. There is no borrowing of prior-season games into a current-season rank.

## Declared rank convention

- Same source season, strictly earlier game dates, regular season only; overtime statistics remain included.
- Rank 1 is most allowed. Fewest rank is retained in evidence. Competition ties compare unrounded integer numerator/exposure cross-products; alphabetical order never breaks a statistical tie.
- A team qualifies with at least **20 matched games and 90% game coverage** for the given cohort/stat. At least **20 NBA teams** must qualify before any rank is displayed. The denominator is the actual eligible count, with all 30 NBA teams’ totals/seconds/coverage retained.
- These are transparent descriptive display sufficiency conventions. They have not been shown to guarantee stable rankings, forecast accuracy or betting value. They do not change probability eligibility.
- Count allowance is sum of accepted credited production / sum of the same rows’ positive minute-seconds × 2,880. Zero production remains zero; absent stats/minutes/source matches are exclusions. Zero exposure is unavailable. A paired positive-exposure descriptive sample can differ from a model’s played-appearance sample.
- Largest contributing game’s share of total production is exposed as a concentration diagnostic. No outlier is trimmed or probability adjusted.
- Historical position evidence is reconstructed from retained records; it is not proof of a pregame capture or a defensive assignment. Pace, schedule and opponent-player quality remain unadjusted.

## Separate FTB opening research

For each defending team, verified opponent **first team scores including free throws** are grouped by recorded starting position. The denominator is accepted opening games with a complete source-matched five-role cohort; bench/other first scorers remain a separate category. Five role counts plus other must equal accepted games. Source, hash, event identity, team, period, scoring points, sequence, page and matching first-score record are required. Missing or ambiguous events reduce that component’s coverage; official box research and an independently verified opposite-team path remain usable. There is no OKC blanket exemption.

Opening frequencies receive the same descriptive rank coverage convention. They are not individual forecast probabilities, first-game-basket estimates, method-market estimates or full-game allowance substitutions. FTB probability and EV remain withheld under the existing repaired-model gate.

## Saved evidence and compatibility

Existing schema-4 research records retain context v2 and presentation/code hashes. Current and prior profile objects, including full rank peer numerators/denominators and coverage, are deduplicated into contextProfiles; result packets retain profile IDs for both seasons. Original saved records remain untouched and retain their prior context versions. The archive’s existing immutable identity includes researchContext/contextProfiles, so changed evidence receives a new record. Roster-sheet rows are never added to displayedSelectionKeys.

## Validation

- Independent Python reconstruction: **600 count ranks** (30 teams × five positions × four stats), **1,200 opponent/reference sum checks**, and **150 opening-position ranks**. All pass against production output. The reference shares retained identities, official extracted box rows, dated role records and verified opening events; it imports no production aggregation/rank/forecast helper.
- Real historical rank coverage: all 600 count cases qualify. Opening sample is 82/82 for 28 teams and 81/82 for DAL/LAL; three bench/other opening scorers are retained across DEN/LAC/NYK.
- Synthetic tests cover exact ties, all positions/markets, zero rates, insufficient games, incomplete coverage, too few league peers, strictly earlier cutoffs, independent seasons, missing opening identities preserving boxes/opposite paths, excluded players, unavailable odds, unchanged offer values and preserved saved-profile references.
- Existing numeric engines/models, Parlay and Matchup hashes match the prior release (see INDEPENDENT_RANKINGS.json).
- Browser preview uses real historical records and clearly labeled synthetic fixtures/lineups/prices. It creates no prospective forecast or betting record. Live publication and browser acceptance are recorded separately in the parent workspace.

## Limitations / future research

The ranks describe historical production allowed to a cohort; they do not isolate causal defensive skill. Twenty games/90% coverage is a display convention requiring future stability research. No confidence intervals, possession reconstruction, lineup-stint model, opponent-quality adjustment, minutes forecast, new training or probability multipliers are introduced. Those require separate research and evaluation. One screenshot’s results are not a training target.
