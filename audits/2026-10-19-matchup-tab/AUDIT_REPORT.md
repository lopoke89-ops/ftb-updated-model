# Matchup tab correction and evidence audit — October 19, 2026

**Decision:** suitable for descriptive basketball research with the limitations below. Matchup now displays independently scoped positional production against the selected opponent’s observed positional allowance. It does not calculate a win probability, EV, or a validated causal matchup effect.

## Why the graphs appeared to repeat

The old Matchup render in `analyst_ui.js` displayed two **team-level first-score position shares**, using `analyst.js.positionCharts`. It never compared full-game player production with the selected opponent’s allowances. In all-opponents mode, selecting another opponent could therefore leave the same team’s graph unchanged. There were no Points, Blocks, Rebounds, or Assists chart inputs at all.

The five-position-only summary also discarded recorded G/F labels. Reproducing the pregame summary on the verified archive gave zero PG/SG/SF/PF bars for all six opener teams and large Unknown bars: BOS 70.8%, DET 68.8%, PHI 73.4%, NYK 80.4%, OKC 71.1%, SAS 96.2%. Those similar shapes were a position-resolution/presentation failure. They were not evidence that all teams had the same basketball tendencies. Season-review summaries were numerically different; an identical cached chart array for all teams was not established.

The replacement is isolated in `matchup.js` and `matchup_ui.js`. It reads completed-game appearance records rather than reusing the first team’s display snapshot or a current-roster role map. Fixture IDs key the pair; each direction explicitly names its production team and allowance team.

## Findings and corrections

| Finding | Severity | Consequence | Correction | Verification |
|---|---|---|---|---|
| Team first-score shares presented where opponent comparisons were expected | High | Changing opponent could leave the team chart unchanged; full-game positional questions were unanswered | Separate paired directions: A production vs opponents against B, and B production vs opponents against A | Three opener fixtures render six correctly keyed, distinct direction charts |
| G/F labels discarded by the five-position summary | High | Most pregame history appeared Unknown with identical zero specific-position bars | Recorded G/F/C default; optional strict five-position mode; retain Unknown explicitly | Appearance-role tests, raw position coverage audit, browser strict-mode checks |
| Full-game scoring and opening scoring not independently represented | High | First-score frequencies could be mistaken for full-game scoring strength | Points, Blocks, REB, OREB, DREB, AST and separate First Team Basket metric; independent FT-inclusive/FG opening switch | All metrics and both opening definitions tested; 102 independent scope cases |
| No explicit opposing-stat-recorder comparison for blocks/assists/rebounds | High | A block could be interpreted as a blocked shooter’s statistic | Read the opposing player’s own box-score count; label blocker/passer attribution; team rebounds excluded | Synthetic attribution regression and independent official-box reconciliation |
| Raw positional totals without playing-time context | Medium | Groups with more minutes or player slots could appear advantaged | Default pooled rate per 48 player-minutes; per-team-game and production-share alternatives; league position reference | Numerators and minute/game denominators independently rebuilt in Python |
| Shared pick-readiness/current-roster notices did not describe a historical team comparison | Medium | View could imply that old-team production had moved with a traded player | Matchup-specific scope notices; keep appearance team/role; no reallocation by current roster | Team-stint regression; prior-season labels; current-only empty state |
| Empty filtered evidence could be visually ambiguous | Medium | A missing role or unsupported scope could look like a measured zero | Explicit Unavailable; no chart for empty team scope; missing counts/minutes suppress affected rates | Play-in/Cup empty scopes, current-only opener, missing metric/minutes, duplicate IDs and failed trust cases |

## What the numbers mean

- **Production:** sum the selected team’s played player records, grouped by that appearance’s recorded role.
- **Opponents against a team:** sum its opponents’ played player records from that team’s selected games, grouped by the opposing stat recorder’s role. The defender’s roster position is not used.
- **Per 48 player-minutes:** `48 × positional count / summed positional player-minutes`. This adjusts for playing time and grouped slots. It is not a per-possession, pace-adjusted, rebound-chance, or shot-contest rate.
- **Per team game:** positional count divided by all of that team’s games in scope, including games in which that recorded position had no event. A position with no recorded appearances is unavailable.
- **Share:** positional count divided by all recorded player production for that statistic, including Unknown roles. Team-credited/unassigned rebounds are excluded.
- **First Team Basket:** one first scoring event per team per game. Includes free throws by default; the alternate definition uses its first made field goal. This is separate from full-game Points and whole-game First Basket. Shares are descriptive frequencies, not player win probabilities.
- **League reference:** the same season, phase, date cutoff and last-N-per-team window across all opponents, grouped by the same role definition. Above-reference alignment is descriptive and unvalidated as a forecast feature.

The evidence drawer exposes the raw numerator, denominator, position appearances, games with that position, and links to the NBA gamebooks for each side. Each chart displays its own team-game count and actual statistics-through date. The bars share a scale within their comparison; the two direction cards can use different maxima, so compare their printed values.

## Scope and failure contract

- Seasons never pool. Automatic upcoming **descriptive** history uses the current season once both teams have at least one completed game in the selected scope. Otherwise it uses labeled completed prior-season history. This differs intentionally from prediction support thresholds; it does not change them. Explicit current-only never falls back.
- Regular season, playoffs, play-in and Cup final are separately selectable. Combined regular season + playoffs excludes the other competitions; All includes them explicitly.
- Last 5/10/20 selects each team’s own last eligible games after phase and optional exact-pair filtering. Head-to-head uses only that unordered pair, not a union of unrelated opponents.
- Historical pregame and upcoming scope exclude selected-day and later records. Season review explicitly uses the complete selected season through its verified archive date and can include the selected game. It is not a pregame backtest.
- Historical team stints and appearance roles remain unchanged after trades. NBA gamebook roles take priority; dated box-score roles are a labeled fallback where the PDF omits a position. Broad labels are never split into guessed five-position roles.
- A DNP is excluded; a played row printed 00:00 remains an appearance. Missing counts do not become zero. Missing minutes suppress the affected per-minute rate. Missing first-score evidence suppresses the affected opening shares.
- Duplicate fixture/player identity, missing boxes, unknown participation, failed evidence trust, or invalid filters produce an explicit unavailable error. Empty filtered team samples do not substitute broader current history.
- In head-to-head mode, A production and opponents against B describe the same events. Equal paired bars there are expected and explained on screen.
- Pick grading and the global whole-game scoring selector are disabled for Matchup; its opening definition is controlled inside this tab. This prevents unrelated filters from appearing to change full-game counts.

## Independent reconciliation

Reproduce with `python scripts/audit_matchup.py` from the repository root. The JavaScript export contains actual chart inputs; an independent Python calculation selects game IDs and rebuilds role totals/minute denominators directly from `official_boxscores.json` and first-scorer IDs from `opening_data.json`. It does not call the chart calculation helpers to determine expected values.

Result: **1,322 games, 28,716 played appearances, 102 scope cases, 1,224 scoped series, 351,756 comparisons, zero differences.** The raw appearance check includes six box-score metrics, seconds, official role, source PDF hash, participation, fixture metadata, and both opening definitions. League reference totals and seconds also reconcile. Source extracts retain the PDF hashes and were previously reconciled to all 1,322 downloaded gamebooks in the October 19 EV data audit; no completed-game data was changed by this task.

Role provenance: 13,220 appearances have a gamebook position; 15,495 use a retained dated box-score fallback; one appearance remains Unknown. A gamebook position may itself be broad G or F; this does not establish five-position coverage.

Representative **2025–26 all-competition Points per 48 player-minutes**, used for the October 20 upcoming slate:

| Direction | Team games (production / allowance) | Guards: team production / opponents against other team | Forwards | Centers |
|---|---:|---:|---:|---:|
| BOS vs opponents against DET | 89 / 96 | 21.75 / 22.25 | 25.64 / 21.71 | 20.92 / 19.50 |
| DET vs opponents against BOS | 96 / 89 | 23.22 / 21.86 | 20.74 / 21.12 | 27.05 / 20.32 |
| PHI vs opponents against NYK | 94 / 102 | 24.81 / 22.25 | 19.68 / 21.40 | 23.16 / 20.21 |
| NYK vs opponents against PHI | 102 / 94 | 24.53 / 23.30 | 21.80 / 22.88 | 22.00 / 21.76 |
| OKC vs opponents against SAS | 97 / 106 | 25.50 / 22.44 | 20.07 / 21.45 | 22.73 / 21.59 |
| SAS vs opponents against OKC | 106 / 97 | 25.80 / 21.96 | 20.34 / 21.37 | 27.63 / 19.85 |

Example: BOS guards scored **5,075 points in 11,198.8167 player-minutes**, giving `5075 / 11198.8167 × 48 = 21.7523`. BOS’s sample ends May 2; DET’s ends May 17. Those dates are displayed separately, rather than giving both charts the league’s June 13 archive date. Full precision and supporting sample summaries are in `source-reconciliation.json`.

## Verification and boundaries

- 18 JavaScript suites passed, including 24 new Matchup/parent integration checks; 65 Python collector/publication tests and 8 NBA opening extraction tests passed.
- Browser checks cover the three opener fixtures and All, seven metrics, both opening definitions, three normalization modes, both position groupings, all six competitions, all four windows, both opponent-history settings, all three history choices, both seasons, all three analysis views, and changed game dates.
- Historical opening night has no prior records and displays Unavailable. October 23 pregame samples stop October 21. Review mode explicitly includes the complete archived season. Current-only 2026–27 remains unavailable before the opener.
- Desktop/mobile layout and publication checks are recorded with the release evidence. The browser’s displayed values are compared with the independent reconciliation samples.
- Parlay/EV engines, coefficients, thresholds, frozen manifests, research records, and underlying canonical data are unchanged. Shared `analyst_ui.js` changes route the new Matchup panel and adjust only Matchup-specific filter labels/notices. The core model hash remains `0802a57953dd0e670937089143813ab3ea2af7fd7c03e29d14a592d2c532c120`.

**Remaining limits:** historical roles are reported roles, not defensive assignments; broad groups combine multiple roles; source position coverage varies; minute normalization cannot account for pace, opponent lineup assignments or scheme; a small sample remains a small sample. These charts support research and prospective hypotheses. They do not demonstrate a predictive or profitable advantage.
