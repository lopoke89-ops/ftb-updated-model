# NBA gamebook statistical correction — October 10, 2026

The downloaded NBA PDFs are now the project's authority for 2025–26 appearances
and box-score statistics. All 41 NBA/ESPN stat-field conflicts are resolved in
favor of the printed NBA values, while both source values remain traceable.

The active analysis ledger, canonical player summaries, embedded site data and
Parlay supplement have been rebuilt from 1,322 official final boxes. Twenty-two
false appearance rows are excluded and one missing Lachlan Olbrich appearance
is included, producing 28,716 played rows for 582 athletes. Minutes use the
printed seconds for every appearance. Full stat lines now include rebounds,
assists, steals, blocks, plus/minus, shooting counts, turnovers, fouls and
offensive/defensive rebounds. Shooting percentages and TS% use summed counts.

The Parlay comparison displays the full stat line in separate regular-season
and playoff columns. Games played, averages, minutes-based opportunity and
attempts/makes correlations use the corrected appearances. The three market
slots per team and equal positional/opportunity weights are preserved.

| Regular-season example | Before | Corrected |
|---|---:|---:|
| Nikola Vucevic GP | 65 | 64 |
| Nikola Vucevic PPG | 14.8462 | 15.0781 |
| Lachlan Olbrich GP | 36 | 37 |
| Lachlan Olbrich rebounds / assists | 96 / 31 | 112 / 42 |
| Lachlan Olbrich FGA / 3PA | 72 / 15 | 77 / 19 |

The independent database comparison checked 976,344 released stat values,
921 player/competition summaries and all 2,644 final team scores. All 1,322 PDF
hashes remain unchanged. All 5,288 stored first-score/first-field-goal actor
references are retained, with their separately labeled opening-play sources;
this release extracts final boxes, not a new structured play-by-play dataset.

Browser, analyst, scouting, hosted-mode, Parlay and static-build checks pass.
The dated model evaluation was rerun against the corrected evidence under the
existing protocol and retains the opportunity model. Original workbooks,
captures and previous evaluated evidence remain recoverable. The historical
workbook's PPG sheet is superseded by the official ledger during every rebuild;
a missing or corrupt ledger fails instead of restoring the old statistics.

The library ZIP was updated with the resolved source policy and passed its CRC
check. Current rosters, detailed role references, opening-play events and future
seasons retain their separately labeled sources and scopes.
