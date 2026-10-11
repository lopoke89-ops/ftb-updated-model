# Operating the Parlay transition research release

Production stays selected by default. In Parlay, choose 2026–27, Upcoming game, Automatic statistics history and a regular-season matchup. Expand **Current-season readiness and refresh details** to inspect actual progress. The optional **Compare experimental gradual updates** checkbox displays a separate research comparison. It resets to off on reload and does not change the three production selections.

## What a refresh means

A verified game updates descriptive current-season averages immediately. Production may continue using the labeled prior season until the relevant team, player, shooting and position requirements pass. Readiness follows the current candidate path; the displayed archive player's count cannot block a different eligible current player. The current descriptive average does not silently replace an archive-supported prop target. A failed check retains the last verified dataset and reports missing coverage.

Live inputs retain the five-minute page-open refresh. NBA PDFs retain the 8–11 a.m. Chicago schedule at half-hour intervals, completed-batch skipping and unresolved-work retries. Later official corrections require the existing forced collector recheck; completed historical PDFs are not repeatedly downloaded automatically. GitHub can start jobs later than their intended schedule.

## Local receipts and NBA PDF outcomes

Install `scripts/requirements-collector.txt` in the Python environment used for collection. Run commands from the repository root. This workspace also has a bundled Python runtime; use its full executable path if system Python lacks the dependencies.

1. Enable the research comparison for one scheduled regular-season game. Save selection evidence within 15 minutes before verified tipoff. Preserve the downloaded JSON. Browser storage keeps only the newest 20 snapshots and is not the durable research journal.
2. Download the matching published `data/seasons/2026-27.json` from the same release. The evidence and code hashes must match. Record the export promptly; the runner allows 60 seconds from browser capture and independently checks current fixture status and scheduled tipoff with ESPN.

```powershell
python scripts/parlay_journal.py record --input "C:/path/ftb-selections-2026-10-20.json" --snapshot "C:/path/2026-27.json"
```

The receipt's UTC time is recorded by the local runner. It retains the full snapshot, schedule capture, code/configuration/protocol hashes, all six market slots, target table, availability and confirmation status. A finalized first-score record additionally requires a fresh fixture-matched NBA starter confirmation. Provisional records are retained and reported separately. First valid receipt per fixture/market/model/FT definition is the evaluation checkpoint; subsequent receipts link to the preceding revision and never replace that original checkpoint.

For an older schema, historical review or late save, import without a pregame claim:

```powershell
python scripts/parlay_journal.py import --input "C:/path/old-export.json"
```

After the morning collector has published the verified NBA final PDFs, settle against the matching season JSON and evaluate:

```powershell
python scripts/parlay_journal.py settle --input "C:/path/2026-27.json"
python scripts/evaluate_parlay_transition.py --output PARLAY_PROSPECTIVE_STATUS.json
```

The default store is `.parlay-research/`, excluded from Git. Back it up, including `receipts.jsonl`, `outcomes.jsonl` and `snapshots/`. Records carry integrity hashes and linked revisions. These detect accidental changes; a local clock and hashes are not an external timestamping or cryptographic attestation service. The existing analyst journal remains separate.

Unresolved, cancelled or postponed fixtures stay pending; they cannot become misses merely because no final PDF exists. DNP counts as a miss for issued selections; participating-only rates are secondary. Official PDF corrections append outcome revisions. Evaluation rejects altered records and excludes other code/configuration/protocol releases. Keep the frozen release checkout to evaluate its cohort after future code changes.

## Reproducing development and diagnostic results

```powershell
node scripts/fit_parlay_transition.cjs
node scripts/diagnose_parlay_transition.cjs
python scripts/evaluate_parlay_transition.py --diagnostic PARLAY_TRANSITION_DIAGNOSTIC.json --output PARLAY_TRANSITION_DIAGNOSTIC.json
```

Fitting uses only observations through December 15, 2025. The later diagnostic uses strict pregame cutoffs within the same season. Run fitting only to reproduce this frozen release or to start a separately versioned experiment; never tune this version in response to its evaluation outcomes. Publication rejects a changed fit script, mismatched browser configuration or a default-enabled experiment.

The simple Points/Threes volume baseline ranks estimated attempts; the mean baseline ranks the frozen actual average. First-score baselines rank estimated starter scoring rate and positional scoring share. Feature removal tests are restricted to the qualifying historical pool: removing correlation does not remove that pool's original historical correlation eligibility gate. These are conditional comparisons, not unconstrained forecasts.

## Validation and rollback

Run the JS suites listed in `.github/workflows/pages.yml`, Python discovery under `scripts`, and `test_opening_gamebooks.py` under the app tests. Build with `python scripts/build_pages.py --output <new-empty-folder>`. Production hashes and the authoritative archive remain authenticated.

Turning the research checkbox off returns the display to production alone; reloading also disables it. Retain the last verified data snapshot and release commit for rollback. No evaluation command automatically promotes the experiment. The frozen protocol requires adequate paired selections, fixture counts, early-season coverage, uncertainty and a genuine season transition before a market can be considered for promotion. Playoff research is withheld because its priors have not been fitted.
