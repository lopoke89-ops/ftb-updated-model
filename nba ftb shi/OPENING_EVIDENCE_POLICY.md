# Official opening evidence

The Parlay tab offers two independent targets: the team's first score including
made free throws, or its first made field goal excluding free throws. Changing
the target recalculates scorer counts, position shares, starter scoring rates
and the relevant opening-attempt rate. Points and Threes do not change target.

`opening_data.json` is extracted from the downloaded NBA gamebooks. Each game
retains its original NBA URL and PDF SHA-256; each event retains the printed
description, first-quarter clock, page and line. The full first-quarter scoring
sequence must reconcile to the official first-quarter box before publication.
Only opening events through both teams' first made field goals and the events
at the final opening clock are published. Other quarters remain in the PDFs.

An and-one requires the same shooter and clock, a made field goal, an opposing
shooting foul, and a subsequent non-special free throw explicitly labeled
1 of 1. The extra attempt counts as awarded even when missed. Technical,
flagrant and other special one-shot free throws cannot establish an and-one.
A one-shot trip without the required supporting basket/foul remains unconfirmed.
And-one counts describe the team's first made field goals, not every free throw
or every basket in the season. The associated field goal is already a score,
so an and-one extra free throw cannot itself be the team's first score.

Ambiguous abbreviated names are checked against the official first-quarter
shooting totals. Unresolved scorer identities or missing pages prevent release.
An unresolved opening attempt retains all candidate IDs in the source record
and is withheld from the opening-attempt feature's numerator and denominator. No
ESPN opening event is silently substituted for missing NBA opening evidence.

The original analyst model and its evidence-bound evaluation are separate from
the Parlay descriptive rankings. This change does not establish calibrated
forecast probabilities or validate the Points/Threes ranking formula.

Points and Threes display the full selected competition's season average at the
same date cutoff, across historical team stints. The visible whole-number target
is its ceiling. Observed success uses the selected statistical sample; a rolling
or head-to-head filter cannot change the underlying season-average benchmark.
Current rosters and labeled prior-season history remain independent.

Rebuild opening evidence with `build_opening_gamebook_data.py`, rebuild canonical
outputs, then apply `official_stats.apply_analysis` to the analysis. Rebind the
opening ledger's parent evidence hash to the resulting analysis hash, rebuild
with `build_parlay_data.py`, and rerun the evidence-bound analyst evaluation.
The canonical and analysis first scorers must agree with the opening ledger.
The local PDF library and Python pypdf/pypdfium2 packages are needed only for
extraction; saved regression fixtures and the publication checks use no network.
