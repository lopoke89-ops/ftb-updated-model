# Official NBA statistics policy

The downloaded 2025–26 NBA gamebook final boxes govern every player appearance,
start, minute and box-score statistic. The PDF value wins every conflict with
the former ESPN-derived ledger, as requested on October 10, 2026.

`official_boxscores.json` is the reproducible app input exported from the local
gamebook library. Each game retains its NBA PDF URL and SHA-256 hash. Stable
ESPN player IDs serve only as identity crosswalks. No NBA IDs are fabricated.

The original workbook and ESPN captures are historical evidence. The workbook's
PPG sheet is superseded by this official ledger; workbook first-score events and
specific role references remain separately sourced. `data_model.py` overlays
official season totals during every rebuild. `build_analyst_data.py` replaces
played rows from the same ledger, and `build_parlay_data.py` derives its full
stat supplement from it. A missing or corrupt official ledger fails the rebuild.

Regular season, playoffs, play-in and the Cup final stay separate. DNP rows do
not count toward GP, while valid appearances that print 00:00 remain included.
Minutes are stored in seconds. Percentages use summed makes and attempts; TS%
uses PTS / [2 × (FGA + 0.44 × FTA)]. Current roster membership is independent of
historical team stints.

To refresh this completed archive, validate/download gamebooks first, run
`build_official_gamebook_data.py`, rebuild canonical and Parlay outputs, and
rerun the evidence-bound evaluation and release checks. Original captures and
previous evaluated evidence must remain recoverable. The complete PDFs retain
play-by-play; this statistical ledger extracts the final box only.
