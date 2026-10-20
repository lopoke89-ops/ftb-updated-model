# Full-game play-by-play methodology and operations

This is an additive research pipeline. Verified NBA final boxes continue to supply all existing Matchup totals, shooting counts and minute denominators. The event ledger supplies reconciliation and explicitly labeled event context. It does not feed Parlay rankings, eligibility, EV probabilities, fitted models or saved research.

## Storage and provenance

`scripts/full_game_pbp.py` builds a separate SQLite database with `sources`, `identity_sources`, `parsers`, `revisions`, `events`, `active` and `attempts` tables. Sources contain the immutable original PDF bytes and capture metadata, keyed by SHA-256. Parser source code is retained by hash. A revision binds the game, source, parser/schema and verified appearance identities; active pointers change within the same transaction as their events. Repeated inputs do not duplicate active events. Earlier source/parser evidence remains queryable.

Every interpreted action retains its printed text, original row, page, line span, period, clock, deterministic sequence, logical identity, scores, participant roles and source IDs. Official same-game NBA/ESPN crosswalks are retained where available; missing NBA IDs remain null. Raw page text preserves administrative content and quarter lineup headers. Scores and corrections are retained, not rewritten to force reconciliation.

Identity resolution uses verified participants in that game's team, with normalized initial-plus-name aliases and suffixes. Official period boxes may resolve a credit only when precisely one candidate can receive that credit. Both candidates and the method remain in the record. A surname alone is not sufficient. Where official text remains ambiguous, an immutable, SHA-256 checked ESPN same-game play capture supplies an identity crosswalk only. Matching requires the game and both teams, period, clock, action/role, verified same-game player ID, candidate restrictions, and available score, shot value/result, free-throw ordinal or resolved counterpart. All compatible matches must agree on one actor. Provider statistics never replace PDF credits. Team rebounds/turnovers are excluded from individual identity matching. The source URL, capture time, digest and matched play IDs remain attached to each resolved role; capture hashes participate in revision identity. The release resolves all required identity ambiguities in the 1,322-game downloaded archive.

The published manifest contains bounded summaries and player-credit counts rather than the raw event ledger. Its parent evidence hash, content hash, PDF identities and parser source hash are checked at publication. Raw PDFs and SQLite are not browser assets.

## Acceptance and basketball definitions

The parser checks regulation/overtime end markers, score progression, period shooting summaries or official quarter-only boxes, final score and period count against official box minutes. Supported player FGM/FGA, 3PM/3PA, FTM/FTA, points, assists, steals, blocks, turnovers and rebound splits require exact agreement. Team rebounds and team turnovers remain separate. Explicit printed team names resolve team rebounds printed in an inconsistent column, retaining the source column and interpretation. Printed team heaves establish rebound context without creating individual FGA. Wrapped technical recipients and named team/bench/timeout technical subtypes remain distinct from individual personal fouls. A period-start score snapshot that precredits a subsequent same-clock technical free throw retains its printed score and explicit effective-score interpretation. Offensive/defensive rebound interpretation records the preceding missed-attempt basis and must reconcile to the official splits. It is not a rebound-chance statistic.

Acceptance is per component. A substitution or coach technical ambiguity can leave shooting counts accepted while the entire game stays partial. A missing shooter or scoring correction suppresses affected event features. Missing values never become invented zeros. Personal/technical/team foul totals are not pooled; raw subtypes are retained without claiming a fully reconciled foul model.

A made shot and its assist are related credits, not separate baskets. A blocker-to-miss link requires the same printed row. And-ones require a made basket, opposing shooting foul and subsequent same-shooter, same-clock non-special 1-of-1 free throw. Awarded, attempted and made counts stay separate. Both opening-score definitions and their attempts are checked against the independent opening extract during collection; the archive has a separate independent opening audit.

All full-game chart counts come from final boxes. Shooting conversion is pooled makes divided by pooled attempts; zero attempts is unavailable. Two-point counts are FGM minus 3PM and FGA minus 3PA. Percentages are not normalized by minutes. Points include free throws; opening tendencies are a separate view.

Broad G/F/C preserves historical appearance labels. Strict mode additionally uses complete five-player, five-position, same-game NBA starter role sets with matching date, PDF hash, identity and official source. Bench appearances keep their supported historical labels or Unknown. Current rosters never relabel earlier games. Neither a position nor a block identifies an actual defensive assignment.

Every event feature exposes its own eligible game IDs and through date. These subsets are not presented as complete histories or compared to a full-history baseline. Per-game, share and per-48 pooled player-minute charts retain their existing definitions. Player-minute normalization does not adjust for pace, opponents or lineup interactions. Pregame excludes selected-day and later results; season review is explicitly retrospective.

## Backfill and independent checks

Run from the canonical repository, using an explicit library path:

```powershell
python scripts/full_game_pbp.py --library 'C:\Users\lopok\Desktop\scrapper - Copy\nba_gamebook_library\2025-26' --database '.pbp/archive.sqlite' --output 'nba ftb shi/play_by_play_manifest.json' --workers 6
python scripts/audit_full_game_pbp.py --database '.pbp/archive.sqlite' --library 'C:\Users\lopok\Desktop\scrapper - Copy\nba_gamebook_library\2025-26' --output 'audits/2026-10-19-full-game-pbp/ledger_independent_audit.json'
python scripts/audit_full_game_openings.py
python scripts/audit_matchup_shooting.py
```

The bundled Python path is recorded in the work order. `--workers 1` avoids multiprocessing when the host prohibits worker pipes. `--game-id`, `--limit` and `--force` support review and forced retries. Use the verified collector/box pipeline to update source records when an official PDF changes; a PDF hash that disagrees with its verified box record is rejected, not silently accepted.

For one game, join `active` to `revisions`, then select `events` by revision ordered by sequence. The revision's `pages` and `result` JSON expose original text, period boxes, acceptance and discrepancies. `sources` retains the exact hash-linked PDF. `parser_revision_history.json` indexes previous interpretations and active pointers. The current local database intentionally retains development parser revisions and is larger than an active-only database.

## Morning collection, durability and rollback

`scripts/pbp_collect.py` processes the separate event queue even when box/opening batches are complete. New or revised verified PDFs get new event revisions. Unchanged accepted results are reused; partial work is retryable. A failed fixture does not discard other fixtures. An old event revision is withheld when a newer verified box source has no matching extraction. A failed event or ledger restore does not prevent independently verified box/opening publication.

Compressed, hash-checked SQLite snapshots use the existing release archive. The durable state branch stores the snapshot pointer and manifests, not multi-gigabyte SQLite/PDF files. Restore verifies both compressed and database hashes and writes atomically. The collection snapshot references a content-addressed event summary independently of its existing box/model content hash. Publication with a stale current-season parser/box summary leaves event context unavailable and the verified boxes usable.

The workflows retain five-minute live feed checks and the seven Chicago morning checks at 08:00, 08:30, 09:00, 09:30, 10:00, 10:30 and 11:00. PDF parsing occurs in collection/backfill, never browser refresh. GitHub scheduling remains best effort. Collection checks, successful source captures, extraction times and actual statistics-through dates have distinct meanings.

For rollback, retain the prior public artifact and matching manifests. The release publication status and commit are recorded in the dated audit report. Fitted models and frozen inputs remain unchanged. The prior checkout was clean at dd70188. Reverting the additive code/assets together restores that implementation; do not combine a new manifest with an incompatible parser/UI. Source and earlier event revisions remain recoverable from the separate ledger/archive.

## Remaining scope and forecasting boundary

The downloaded 2025–26 archive has 1,322 verified games and zero remaining required discrepancies. This acceptance concerns the specified statistical and event-identity checks, and does not imply reconstructed defensive assignments, reconciled personal-foul totals, or complete five-position bench evidence. Future unresolved captures remain explicit and affected components stay withheld. See the dated audit report and machine-readable coverage/discrepancy ledgers.

Lineup-stint reconstruction, possessions, pace adjustment, opponent-strength forecasting, training, calibration and EV redesign remain deferred. Possible future forecasting inputs include verified shooting volume/conversion and linked credit context, but they require separate chronological validation, same-observation baselines, uncertainty and prospective criteria. This implementation establishes neither improved predictions nor profitability.
