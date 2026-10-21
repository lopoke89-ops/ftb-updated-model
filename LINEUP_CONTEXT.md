# Projected and confirmed starting lineups

In **Filters**, choose **Upcoming game**, a game date within the next seven days, and the matchup. For the season opener, select **2026–27** and **October 20, 2026**. Open **Starting lineups** above the main rankings or Parlay Machine. Both screens use the same lineup snapshot. The panel stays collapsible to preserve space.

The panel shows a source link, capture/check time, and the provider's update time when supplied. Player cards and Parlay selections identify projected starters and players outside the current projected five. **Refresh lineups** checks immediately. The main player details also link to their lineup source.

## Status and source policy

### Upcoming Picks starter feed

Upcoming Picks defaults to **Confirmed starters only**. It uses the same complete
five-player team view and NBA confirmation validator as the shared lineup panel,
Parlay and EV. Every identity must still match the current roster. The card list
and its leading-player highlight both use this restricted set; historical grades
and their denominators are unchanged.

Before confirmation, the feed lists the teams awaiting fresh NBA evidence.
**Include projected starters · unconfirmed** explicitly opts into the current
projected five. Complete NBA confirmations take precedence and replace changed
projected starters. Neither previous-game starters nor manual scenario assumptions
can add players to either feed. Availability/scenario exclusions still apply;
Show excluded players cannot bring a bench player into the starter feed.

Confirmations expire under the existing five-minute rule. Partial lineups,
unresolved roster joins and unavailable sources withhold the affected team.
Pregame cards close at scheduled tipoff or when the fixture is no longer pregame.
Historical review and the other tabs retain their existing research scope.

- **Depth-chart projection · unconfirmed** uses ESPN's current team depth chart. It is a derived projection, not an announced game lineup. The browser binds it to the selected scheduled fixture and current roster.
- **NBA expected starters · unconfirmed** uses a complete, active, five-position expected lineup in the NBA daily feed on game day. It takes precedence over a depth-chart projection when complete and consistent with reported availability.
- **NBA confirmed starters** uses the existing official confirmation validator. All five must resolve to current roster identities, belong to the selected matchup/date, be explicitly confirmed and active, and have a capture no more than five minutes old before scheduled tipoff.
- **Previous lineup** remains historical reference. Manual scenarios remain assumptions. Neither can grant confirmation.

ESPN depth charts come from `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/<team-id>/depthcharts`. Season and team IDs must match the fixture and current roster. Out and Doubtful players are excluded; Questionable players retain that label. The assignment chooses five distinct players with the smallest total listed depth rank across PG/SG/SF/PF/C. A replacement's depth rank is visible. Missing positions, unresolved identities, or inability to form a unique five withhold the team instead of inventing a starter.

Depth-chart captures expire after six hours; original cloud capture times are preserved. NBA expected and confirmed captures expire after five minutes. Projections expire at tipoff and cannot transfer to another fixture. A source URL, capture timestamp, and provider timestamp remain separate fields. Reading a cloud file never relabels its data as newly captured.

## Refresh behavior

The browser checks lineup feeds independently every five minutes in Upcoming game view, skips hidden-tab polling, and checks immediately on returning to the page. It does not depend on a successful schedule/injury refresh to keep its own timer running. Current roster and injury changes also trigger reevaluation. Requests completing after a date/view/roster change cannot replace a newer lineup result.

The cloud workflow retains the existing five-minute schedule with an offset from the start of the hour. It captures depth charts for teams with upcoming fixtures in the next seven days. Once a fixture is within two hours of tipoff, a running worker polls every five minutes and stays through gaps until the day's remaining pregame fixtures are finished, or its four-hour runtime ends. GitHub concurrency keeps a pending successor instead of interrupting an active worker. Source failures retain the last successful capture with its original timestamp and are retried on the next poll.

GitHub scheduled starts remain best effort and can be delayed. The active worker reduces dependence on each individual scheduled trigger; it does not guarantee timely startup or upstream availability. The browser's direct feed, manual refresh, and expiration checks remain necessary. GitHub documents schedule delays in its [workflow troubleshooting guide](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).

The `nba-live-lineups` branch stores `live-lineups.json` and `projected-lineups.json`. Publishing either preserves the other. Neither uses or replaces the separate final-gamebook archive branch.

The publisher supports the workflow's sparse checkout: unchanged cache blobs are referenced from the fetched parent tree without requiring them to be downloaded locally. A run ending with an unresolved source/publication failure reports failure instead of a successful empty update. Publication was checked against the actual branch contents after rollout.

## Grading and evidence

Projections add lineup context and labels. They do not change historical grades, historical PDF positions, ranking weights, or readiness thresholds. First Team Basket selections remain provisional until the existing NBA confirmation and availability requirements are met. A depth-chart position is not substituted for a historical gamebook position.

**Save selection evidence** now includes the complete lineup context, with projected/confirmed status, fixture identity, source, and timestamps. It remains a research snapshot, not a verified issuance receipt. Local capture archives retain the per-source payloads and original capture times. No grades or outcomes are reconstructed after a game from the newly fetched lineup data.

The local server's lineup capture extension validates the two new source kinds with `lineup_capture.py`. It permits only the exact NBA daily-lineup and ESPN team-depth-chart URL patterns, checks payload identity, and enforces the same five-minute/six-hour capture limits. The existing non-lineup capture rules remain in force. The publication and local research-receipt code hash lists both include the projection module.

## Verification

Sixteen focused JavaScript checks cover all 30 teams (including Sacramento), source/season/roster identity, unique-player assignment, Out/Doubtful/Questionable handling, expiry, fixture mismatch, official precedence, stale cloud captures, preserved source capture times, and timer/visibility cleanup. Integration checks exercise the panel in both actual UI entry points and the selection-evidence download. Eight collector checks cover projection capture, invalid seasons, worker retry/handoff, preservation of both capture files in sparse checkouts, independent publication when an official source fails, and failure reporting.

Live ESPN responses resolved five distinct current-roster players for all six opening-night teams during implementation. The ordinary JavaScript and Python regression checks also passed. Interactive browser verification was unavailable in the implementation session; the preview was queued in the app.
