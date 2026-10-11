# NBA collection and live refresh

The website reads verified snapshots. GitHub Actions collects official gamebooks
and publishes new snapshots independently of the local PC.

## Morning collection

`Collect NBA morning gamebooks` runs daily at 8:00, 8:30, 9:00, 9:30, 10:00,
10:30 and 11:00 a.m. in `America/Chicago`, including daylight-saving adjustments.
GitHub scheduling is best effort; runs may start late.

Each run checks the previous Chicago game date and unfinished batches from earlier
days. It discovers fixtures through ESPN, excludes preseason, and tracks postponed
or canceled fixtures separately. Failed schedule requests remain unresolved; they
cannot count as a confirmed day with no games. Games not yet final remain pending.

Completed games require an official NBA PDF with a matching date, teams, printed
final totals, valid player stat lines, unique identities, five starters and verified
opening play-by-play. ESPN supports identity crosswalks and discovery. NBA values
govern final statistics; score differences are retained in each document record.
Missing or ambiguous identities/events remain pending for review.

Original PDFs are retained as hash-named release assets, grouped by season and
month. SQLite snapshots are also attached to those releases. The `automated-data`
branch stores records, final-box text, schedule captures, retry state and versioned
website datasets. PDFs and temporary extraction caches do not enter Git history.
The 2025-26 seed archive is a separate verified download under `nba-2025-26-archive`.

Collection stops for completed batches. Later scheduled jobs skip network collection
for those batches. Missing gamebooks carry into the next morning window. There is
no nightly PDF job. Publication failure leaves the prepared snapshot eligible for
publication on the next check. Original assets and prior data commits are retained.

## Manual collection and corrections

In GitHub, open **Actions > Collect NBA morning gamebooks > Run workflow**.
Leave the date blank to collect yesterday, or supply a Chicago date within the
enabled 2026-27 season. Enable **Recheck a completed batch** to request gamebooks
again and look for official revisions. Previous hash-named PDFs remain archived.
Enable **test an actual NBA PDF download** to exercise both PDF parsers against a
known completed game without adding it to the new season.

Code and morning deployments use the same concurrency group. Ordinary code
deployments restore the durable current-season snapshot before building, so a
code release cannot reset the season to the repository's empty preseason snapshot.
Collection pushes the data branch; it directly runs the website build/deploy steps,
without relying on a bot push to trigger another workflow.

## Live page updates

Upcoming views refresh schedules, rosters, injuries and the published current-season
snapshot every five minutes while open. Background refresh retains matchup filters.
Requests have timeouts; an unfinished polling round cannot overlap another round.
Leaving Upcoming stops its polling timer. Browsers may throttle background tabs.

Out and Doubtful players are excluded from selections. Questionable players stay
provisional until an explicit availability update; omission alone is not clearance.
Failed or stale sources cannot confirm availability. First Basket rankings remain
provisional until the official NBA Daily Lineups feed supplies an explicit Confirmed,
Active five-position lineup matched to the same fixture and current roster. Bench
rows without a position do not count. All five identities must match uniquely.
The record must be captured within five minutes, on today's game date, and before
tipoff. Prior boxes, expected lineups and user assumptions never confirm starters.
Missing, stale or ambiguous NBA data leaves First Basket provisional. A fresh NBA
active-starter confirmation can explicitly clear Questionable; Out and Doubtful
remain excluded until their restriction is explicitly cleared by the injury source.

The NBA endpoint can block direct cross-origin browser requests. The separate
**Refresh official NBA lineups** GitHub workflow checks every five minutes and
captures NBA JSON only when a scheduled pregame fixture is within two hours of
tipoff. It publishes `live-lineups.json` on the small `nba-live-lineups` branch;
no Pages rebuild is needed. The browser can read that response through GitHub raw.
It preserves the NBA capture time and rejects captures older than five minutes.
GitHub scheduling or CDN delays can therefore leave selections provisional.
The bridge never substitutes ESPN or final-box starters for an NBA announcement.
It uses its own concurrency group and does not change the morning archive branch.

The morning collector also retains NBA Daily Lineups JSON and matches its final
starting five to the authoritative PDF starters. Those roles become dated evidence
for later games. They are labeled postgame observations and cannot establish when
a pregame announcement was available. An unavailable role feed does not block an
otherwise verified final box; broad G/F roles stay unknown.

## Verification and limits

Run the Python tests under `scripts`, the opening-gamebook tests and all browser
test scripts before publication. Tests cover partial collection, carryover,
postponements, schedule failure, idempotence, source authority, complete stat lines,
supplement hashes, publication recovery, polling cleanup and availability policy.
The Data tab shows the morning window, checked batch, pending games and schedule
errors. The deployment manifest includes publication time and collection status.

The enabled collector season is 2026-27. Additional seasons require an explicit
rollover update. Completed batches are rechecked for later NBA corrections only
through a manual forced run. Scheduled workflows in public repositories can be
disabled by GitHub after prolonged repository inactivity; check Actions if updates
stop. No new paid service is required by this setup.

## Selection readiness and audit records

Automatic history is assessed for each team/opponent pair and market, in the selected
competition, period and opponent scope. Both teams need five verified games.
First Basket and Points need five player appearances; Threes needs eight.
First Basket also needs five starts and supported scoring-share evidence.
Current-season statistics remain visible before readiness; prior-season selection
evidence is labeled and kept separate. Manual current-only and archive controls
remain available. Empty head-to-head samples stay empty.

First Basket ranking uses the same capped historical-grade policy as Picks.
The equal one-third offense, defense and opportunity score is multiplied by the
capped grade divided by its league baseline, at most one. This prevents a small
conditional starting sample from overpowering low observed scoring share.
Points and Threes retain the requested positive paired correlation requirement.
Season averages use the entire selected competition before the selected date,
independently of the rolling hit-rate sample.

Parlay's **Save selection evidence** downloads JSON and stores the last 20 snapshots
in that browser. A record includes filter assumptions, source capture status,
NBA confirmation, dataset and PDF hashes, player samples, targets, scores,
provisional status and exclusions. This is a local audit trail, not shared storage
or a prospective performance claim.

Run `node scripts/evaluate_readiness.cjs` to regenerate the policy and evaluation
after changing selection code or its archived evidence. The saved protocol separates
development dates through December 15, 2025 from later tests. The report includes
coverage, DNP counts, descriptive intervals, fixture and weekly bootstrap sensitivity,
traded-player slices, and separate conditional known-starter analysis. The builder
rejects stale model, evaluator or report hashes.

The retrospective tests did not establish consistent gains from positional or
correlation signals. Threes underperformed the simple attempt-volume baseline.
Pregame dated specific-role coverage is sparse; later season-role references are
excluded from that test. Completed-archive analysis may apply reviewed season roles
retrospectively, which does not prove each game's exact position. No verified
2024-25 archive exists here to validate cross-season transfer. The app exposes these
limits in Data and retains the user-requested weights without claiming calibrated
matchup or joint probabilities.
