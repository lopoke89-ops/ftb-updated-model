# First-night review and upcoming starter feed

Implemented locally on October 20–21, 2026, based on release 3a3d6a3.
This change has not been committed, pushed, or deployed.

## What the first night supports

- The reviewed three-game outcomes can be used as source-checked research results:
  official final boxes and first-score PBP were independently verified.
- Continue prospective evidence collection with frozen selections, prices, filters,
  model versions and lineup assumptions preserved before tipoff. Deduplicate
  repeated snapshots and keep individual statistical results separate from
  account settlement and actual stakes.
- Approve the main-feed starter gate as a display correctness improvement,
  verified by focused checks and browser evidence independently of the night's
  wins and losses.
- Preserve explicit provisional, missing, stale and nonstarter states.

One night does not approve calibrated probabilities, a profitable EV advantage,
S/A predictive superiority, changed weights, or larger betting exposure. The
primary overnight saved list went 20–43, -0.2431 illustrative units; its FTB subset
went 2–3, +6.70 units. Those five FTB bets represent only three team outcomes,
and the winning Vassell forecast had a frozen-five mismatch. The main S/A grades
were reconstructed historical cards, not authenticated pregame issuance receipts.

Points alternative-line tails merit investigation: all eight primary displayed
selections above +100% model EV lost. This observation is a diagnostic and does
not justify refitting a frozen model from a single correlated slate.

The final-PDF text extraction failure identified during the day review remains a
separate collector issue. The review's independent extraction does not establish
that automated new-season collection or full-game reconciliation has succeeded.

## Implemented behavior

Upcoming Picks defaults to **Confirmed starters only**. Both the card list and
leading-player highlight are restricted using the existing shared
FTBProjectedLineups.teamView and FTBLineups.validConfirmation checks. The complete
five must match the selected fixture/date, fresh NBA confirmation, current roster
identities and five-position requirements. Partial or stale evidence withholds
the team. Started/completed fixtures close their pregame feed.

**Include projected starters · unconfirmed** is an explicit opt-in. It displays
only the shared current projected five. A complete fresh confirmed five replaces
the projection, including changed players. All projected cards retain their
unconfirmed labels. Prior lineups and manual assumptions cannot create a starter.

Existing availability/scenario exclusions still apply. Show excluded starters
can reveal an excluded member of the sourced five, but cannot add bench players.
Historical review, historical grades/denominators, and Parlay/EV/Matchup selection
rules remain unchanged. The existing five-minute lineup refresh, visibility
refresh, confirmation expiry, and thirty-second display clock are reused.

## Verification

- 22 page/integration checks passed, including seven new starter-feed cases.
- 16 shared-lineup checks passed.
- Live-refresh/availability checks passed.
- 23 EV First Team Basket checks passed.
- 44 Parlay checks passed, including frozen model/evidence hashes.
- JavaScript syntax and whitespace checks passed.
- Static publication validation/build passed: 65 public files; existing archive
  and frozen model hashes validated. Candidate:
  .build-tests/starter-feed-release-20261021.

Browser verification used the final local publication build with actual upstream
October 21 schedule, roster and projected-lineup responses. No live NBA-confirmed
five was available at this early hour. The browser showed zero confirmed cards,
then exactly ten projected cards (five per team) for Atlanta at Orlando after
explicit opt-in. The confirmed-five/replacement/expiry cases were exercised with
deterministic inputs by the integration checks, not claimed as live confirmations.

Evidence: confirmed-waiting.png, projected-opt-in.png, browser-cards.json.
The existing responsive styling and team colors were retained; a separate mobile
viewport session was not performed.

## Publication status

Ready for review as a UI change. No production files or model values have been
published. New-season collector recovery is an outstanding separate follow-up.
