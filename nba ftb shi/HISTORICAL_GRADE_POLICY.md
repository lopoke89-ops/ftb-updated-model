# Historical grade and ranking policy

Grades describe observed first-team-score evidence, including made free throws.
They are not matchup probabilities. Forecast model outputs remain separate.

For the selected team, competition, statistical window and opponent scope:

1. Validate the player's starts, starter first scores, appearances, total first
   scores and scoring-share denominator. Require at least five starts.
2. Calculate the adjusted starting rate:
   `(starterFirstScores + 20 * leagueStarterRate) / (starts + 20)`.
3. Calculate the observed scoring share: total first scores / selected team
   games. Prior-season history combining team stints uses first scores /
   appearances instead; full-season game totals from old teams are not added.
4. The grading score is the lower of the adjusted starting rate and observed
   scoring share. Historical-grade sorting uses this score.

S requires a grading score >=25%; A >=18%; B >=12%; C >=6%; D <6%.
Fewer than 20 starts remains a small sample, marked with an asterisk. Incomplete
or contradictory share counts receive NR rather than bypassing the share cap.

This prevents a player with a few successful starts from receiving an elite
grade despite a low full-sample scoring share. Mohamed Diawara's archived
2025–26 all-competition record is the regression example: four first scores in
seven starts (57.1%), but four in 102 NYK team games (3.9%). His adjusted starting
rate previously produced S*. The grading score is now capped at 3.9%, giving D*.
His four scores, seven starts, 75 appearances and original rates stay intact.

The cap is applied to every player, rather than a player-name exception, and is
recomputed after competition, rolling-window or opponent-history changes.
Starter-only sorting remains available as an explicit descriptive comparison.

The analysis controls use a native disclosure panel, closed by default, with a
compact summary of current scope and matchup. Collapsing the panel keeps all
selections and leaves the results available. It does not reset or refetch data.
