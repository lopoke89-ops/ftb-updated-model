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
provisional until a current starter confirmation is supplied. Prior boxes and user
lineup assumptions never confirm starters. A verified pregame starter source is not
currently connected, so automatic refresh alone does not finalize First Basket.

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

This implements collection, storage, live refresh and eligibility status. The
broader opening-night work order's transition backtesting and ranking validation
remain separate work.
