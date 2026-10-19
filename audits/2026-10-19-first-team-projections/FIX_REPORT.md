# Shared projected lineups for First Team Basket EV

User report: Parlay showed projected starting fives while EV asked for NBA confirmation for every First Team Basket price.

| Finding | Correction | Verification |
|---|---|---|
| EV received shared lineup context but ignored projections in its separate engine | Use the same `FTBProjectedLineups.teamView` as Parlay; fresh confirmations take precedence | Engine integration with real shared resolver; live preview |
| No distinct provisional conditional-lineup scenario | Label projected estimates, preserve all five source records, retain confirmed-only filter and finalized-pick policy | Engine/UI filter and exact-lineup download tests |
| A saved projection could be compared against a different actual five | Grader v3 separates projected research, records actual PDF starters and excludes mismatched fives from conditional probability scoring; ordinary contract result remains available | Matched five, changed teammate, nonstarter void, invalid receipt, old v1 compatibility |
| Expiry and saving only accounted for confirmed lineups | Expire projected scenarios at their provider-specific deadlines; saving rechecks quote and exact lineup | Clock expiry / late-save regression |
| Original frozen model needed preservation | Archive original v1 files with SHA-256 manifest; version operational scenario change as v1.1 | Original files compared byte for byte to original Git commit; regenerated config, baseline, samples and every diagnostic unchanged |

No numerical fitting, same-team support threshold, original Parlay ranking or frozen Points/Threes engine/model/protocol/rules changes. First Team Basket remains experimental. Projected EV assumes the exact five starts; probability of starting/void and unconditional EV are not estimated. Questionable remains provisional; Out/Doubtful/scenario-excluded members block the five. Projected scenarios never enter the confirmed-starter primary promotion cohort.

Verification: all 15 JavaScript suites passed, including 23 first-team and 18 EV UI cases; 65 collector/publication Python tests passed. Publication built 61 coherent assets with matching independent model/source hashes. Live preview on October 19 at approximately 9:28 a.m. Central showed five eligible OKC projected-player estimates (two positive under the default EV filter), with the source five and prior-season history visible. Other teams retained specific missing-history or invalid-depth-source reasons. These are live source observations, not proof of predictive advantage.
