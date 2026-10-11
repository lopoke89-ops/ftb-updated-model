# Parlay transition model contract v1

Production rankings, targets, grades and sample minimums are unchanged. The
experimental path is off by default and never issues production selections.

The experiment starts with the eligible prior-season candidate pool for each
market, including the existing positional coverage, complete records and grade
checks. No qualifying prior means no early-season research selection. Current
rows use the same date, competition, period, opponent and team-stint rules as
production. Current missing rows withhold an affected candidate rather than
manufacturing zeros. Both supporting positional samples must meet 80% coverage
when they have observations; an empty current sample leaves the prior estimate.
Use one common position resolution for both seasons, both teams and each market.
A current dated role that differs from the historical group withholds that
candidate without fresh fixture-specific confirmation. Projecting a changed
rotation or role is outside this experiment.

Observed minutes, FGA and 3PA means use (prior mean * fitted equivalent games +
current total)/(equivalent games + current observed games). Conversion uses
(prior conversion * fitted equivalent attempts + current makes)/(equivalent
attempts + current attempts). Starting frequency and opening-attempt rate use
the same binomial formula with observed appearances and opening samples.
Starter first-score rate uses observed starts. Positional shares use equivalent
production counts: historical share times fitted equivalent points, made threes
or opening events, plus current production, divided by equivalent production
plus current total. Counts and priors are always displayed separately.

Normalize opportunity volume/minutes among research-eligible candidates only.
Use the existing internal opportunity weights and equal one-third outer weights.
For First Basket use the current observed grade factor when rated; otherwise use
the qualifying prior observed grade. A rated zero-quality current grade withholds
the research candidate. This deliberately retains the low-share safeguard and
can introduce a disclosed grade-basis change; the experiment does not promise a
perfectly smooth ranking or a changed name after each game.

For Points/Threes use prior positive paired correlation below five complete
current pairs, then current correlation at five or more pairs. Undefined,
nonpositive and constant current series withhold. Never blend correlations.
Targets are frozen per candidate from the current production-supporting sample
when that candidate passes all current production requirements, otherwise the
qualifying archive average. Both models use the same candidate target table.
Research output includes the actual season target, current eligibility,
availability, confirmation status, prior/current counts and effective weights.

Fit equivalent-game/attempt strengths offline using an artificial within-season
transition on regular-season games through 2025-12-15: each player's first ten
appearances form history, subsequent appearances form accumulating observations,
and the next appearance is held out. Select grid strengths by next-observation
squared error for volume and binomial log loss for conversion. Fit positional
strengths similarly using a team's first ten games and later next-game shares.
Fit first-score opportunity strengths from player starter/first-score and opening
records in the same development interval. Persist counts, losses, fitting corpus
hash and the selected grid values. This is development evidence, not a genuine
cross-season validation. Playoff fitting is unavailable in that interval; withhold
playoff research rather than silently reusing a regular-season fit.

Browser inference is deterministic. Configuration changes receive new hashes.
No projected rotation, rookie prior, probability, sportsbook or joint-parlay
calculation is part of this model. Future/selected-day rows are excluded by the
existing pregame builder. No final lineup is treated as a pregame announcement.
