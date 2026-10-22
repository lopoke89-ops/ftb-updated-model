# FTB Scout

**Website:** https://lopoke89-ops.github.io/ftb-updated-model/

NBA first team score research, including made free throws. The published app preserves the v5 design and the corrected 2025–26 canonical dataset through June 13, 2026.

The website opens in Today · Upcoming on the current Chicago date with the 2026–27 season selected. Use the filters to browse future dates or switch to historical season review.

Player appearances and box-score statistics now use all 1,322 downloaded NBA
gamebook final boxes as the authority. Parlay shows the full stat line with
regular season and playoffs separated. See [the statistical source policy](nba%20ftb%20shi/OFFICIAL_STATS_POLICY.md)
and [the correction release](OFFICIAL_STATS_RELEASE_2026-10-10.md). Original
workbooks, PDFs and source capture archives remain in the local workspace;
they are required for a full source rebuild and are not hosted on this site.

## What works on GitHub Pages

- 1,322 completed games and 2,644 team first scores, including 249 made free throws.
- Historical player grades, scoring and opportunity statistics, expanded player details, and position charts.
- Regular season, playoffs, regular season plus playoffs, play-in and Cup-final filters; independent head-to-head and rolling-history filters.
- Historical review and dated pregame research, keeping selected-game and later results out of pregame evidence.
- Separate 2026–27 history, with prior-season scouting available when the new season has no completed sample.
- Browser requests for ESPN schedules, current rosters, injury reports and play-by-play. Provider availability is shown in the app. Rosters do not confirm upcoming starters.
- Sourced advance depth-chart projections and game-day NBA expected/confirmed lineups in a shared, collapsible panel above Picks and Parlay. See [lineup context and refresh policy](LINEUP_CONTEXT.md).
- **Reload verified history**, using a coherent published JSON snapshot.

The published page has no shared research database. Workbook rebuild/import and verified Parlay research receipts use the local application. GitHub workflows collect verified gamebooks each morning and publish completed-season updates; live lineup and FanDuel price workers check independently. Scheduled starts and upstream feeds are best effort. Stale or unsupported quotes cannot produce EV estimates.

**EV Bets** provides experimental, participation-conditional probabilities for regular-season Points, Made Threes, Assists and Rebounds using FanDuel Tennessee prices. Assists/Rebounds have separate models and validation; Parlay adds separately labeled descriptive cards. See [Assists/Rebounds scope, diagnostics and daily scorecards](ASSISTS_REBOUNDS_IMPLEMENTATION.md). **First Team Basket probability and EV are withheld** after the October 21 audit found future-history leakage in the earlier fit. A repaired retrospective model is preserved but disabled; fresh FTB prices and descriptive research remain available. See [First Team Basket scope and diagnostics](FIRST_TEAM_EV_IMPLEMENTATION.md) and [the repair evidence](audits/2026-10-21-ftb-leakage-repair/REPAIR_REPORT.md). The app saves the supported offer universe, display filters and displayed selection IDs in browser-local research records. **Export saved EV history** preserves a copy; **Grade saved EV history** downloads statistical outcomes from verified NBA final boxes, with pending, review and rule-indicated void states. Earlier FTB receipts keep their outcomes and original forecasts but are flagged as invalid probability evidence. This does not verify sportsbook settlement, actual returns or pregame issuance. Game First Basket and combined-parlay EV are not modeled. See [the implementation policy](EV_IMPLEMENTATION.md).

Historical Parlay grades remain descriptive. The separate EV model is a retrospective research model; prior-season rotation transfer, future calibration and profitable advantage remain unproven.

## Publishing and updating

Pushes to `main` run `.github/workflows/pages.yml`: test the analytics, validate data and model hashes, export an allowlisted `_site` artifact, then deploy through GitHub Pages. Failed checks prevent deployment.

The active website source is `nba ftb shi`. Older files retained elsewhere in this repository are excluded from the public website. The exporter includes only HTML, app JavaScript, styles, verified vendor assets and public dataset snapshots. Workbooks, executables, caches, local journals and server code are excluded from the Pages artifact.

To publish newly verified data, collect/rebuild in the local app first. Bring the coherent `merged_dataset.json`, `analyst_data.json`, `analyst_data.js`, `analyst_evaluation.json`, `analyst_evaluation.js` and embedded canonical preload in `ftb-scout.html` into this source directory together. For 2026–27, also update its manifest and active version under `seasons/2026-27`. Update `site-config.json` with the publication date, run the checks below, then commit and push. Do not hand-edit scoring outcomes or season counts to make validation pass.

## Local static preview

Requires Python 3.10+ and Node.js. No package installation is needed for the exporter and JavaScript checks.

```sh
node "nba ftb shi/tests/test_browser.cjs"
node "nba ftb shi/tests/test_analyst.cjs"
node "nba ftb shi/tests/test_scouting.cjs"
node "nba ftb shi/tests/test_pages.cjs"
node "nba ftb shi/tests/test_lineup_projections.cjs"
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/build_pages.py
python -m http.server 8002 --bind 127.0.0.1 --directory _site
```

Open http://127.0.0.1:8002/ . The exporter requires a new or empty output folder; use `--output` to choose a fresh folder for subsequent builds. `deployment-manifest.json` records published asset hashes and dataset coverage.

First Team Basket retains shared projected/confirmed lineup checks for a future release. Neither lineup basis currently enables a probability or EV. Immutable-history regression checks and an independent Python replay guard the repaired fit; they do not establish a betting edge. Details: [First Team Basket EV](FIRST_TEAM_EV_IMPLEMENTATION.md).
