# Main-app EV matchup and opportunity context

Baseline: released leakage repair, main 0b3a35219820180b321d01ad01fbff6eaca9a7dd. This feature is separate from The John Collins Method.

## Behavior

Each supported points, threes, assists and rebounds EV row gains a read-only Matchup & opportunity panel: current/last historical position, opponent allowance versus an excluded-defending-team league comparison, matched credits/minutes, sample/through date/season, historical player minutes and starter status, exact-target historical W/L/push counts, active-model overlap and a visible main concern. It covers PG, SG, SF, PF and C. Missing exact-role samples use an explicitly labeled broader G/F/C cohort when available; unavailable source/stat/minute comparisons remain unavailable. The UI neither selects new bets nor changes existing probabilities, EV, order or support gates.

Role evidence binds an accepted official box hash and five unique starter identities to dated five-position source captures. A source-matched complete supplement takes precedence over sparse embedded role references. Historical labels do not identify a defender or historical pretip confirmation. Exact-role profiles describe recorded starters; broad profiles describe played appearances with known G/F/C. An opponent profile uses its prior regular-season games from the latest accepted season with opponent observations; fallback to an earlier season is labeled. A new season with one game is not silently pooled with the archive and the small current-season sample is called out. The league comparison uses the same season/cohort and excludes that defending team's allowance observations.

Rates pool credits and exact player-minute exposure on the same valid rows. Per48 means per 48 credited player-minutes, not pace/possession/position-slot adjusted. Missing statistics or minutes are excluded together and counted. Unknown roles are reported separately. Observed zero remains zero. Source games link to original PDFs. A favorable mean is not described as support for a specific threshold or an independent probability boost. Broad opponent factors already embedded in each active model are disclosed.

The context adapter copies retained source observations and freezes cached profile objects; later in-place edits cannot silently alter retained evidence. It caches aggregates by source revision, cutoff, defending team, position/cohort and market. Native detail expansion does not fetch, select, re-rank or create records.

## Preserved behavior and records

Count/FTB engines and model manifests, Parlay engines and the existing Matchup calculation are byte-identical to the baseline. FTB v1.2 remains disabled. No collector, fitting, source archive or scheduled-job changes are part of this release.

Existing schema-4 browser research records remain readable without migration. New records include a separate context version/code hash and compact per-row context with profile IDs. Unique profiles are stored once per receipt in contextProfiles. Both context metadata and profiles participate in immutable archive identity, so updated context never overwrites an earlier capture. Full supported evaluated offers retain context before user display filters; original prices, probability/model identities, availability and displayed selection keys remain separate. Browser-local records remain research, not authenticated issuance or sportsbook settlement.

Mobile EV rows stack into readable cards with price/probability/EV labels and full-width evidence. Desktop retains the table. Unknown-role fallback, current-season sample sizes, prior-season transfer, ladder limitations and provisional availability are visible rather than a new confidence badge.

## Verification

- 11 context unit cases: all five positions, independent numerator/exposure example, complete source supplement precedence, missing/source-mismatched rows, broad fallback, strict cutoff/competition, new-season separation, bench cohort, historical targets, immutable snapshots, unknown trust/duplicate fixtures.
- 31 EV UI cases including unchanged price/probability/EV ordering, complete-universe capture, context profile deduplication, old records and changed context-version identity.
- Additional direct Node runs passed: count EV (13), FTB (26), grading (11), scorecard (9), page integration (23), additional-market cases (18), historical role validation (13,210 roles).
- 11 Python publication tests passed; allowlisted/versioned context asset and hosting context hash are verified.
- Independent Python source reconstruction compares 60 cases (all five positions, four markets, three defending teams) against both opponent and league-reference totals/exposures/rates: 120 component comparisons, zero per48 discrepancy. It shares accepted identities/boxes/dated-role captures, not production aggregate helpers. INDEPENDENT_CONTEXT.json records source invariants.
- Local desktop and 390 x 844 mobile browser preview used real history with conspicuously synthetic fixture/lineup/prices, never real recommendations or prospective issuance. Mobile content width fit the viewport without horizontal page overflow; details opened with source/sample/overlap text and no browser errors. Temporary viewport override restored afterward.
- One multiprocess Node runner invocation hit Windows spawn EPERM; direct execution of the same test files completed successfully. CI uses direct commands.

Publication CI must pass before merge; deployed assets and their actual manifest/context hash must be checked after deployment. This document records implementation checks, not a claim that deployment has already occurred.

## Limits

There is no new game-specific minutes forecast, opponent-quality/pace adjustment, causal defender assignment, exact-line matchup probability, changed selection policy, FTB forecast or combined-parlay EV. A raw contextual ratio can be noisy or confounded. Context is explanatory research with source coverage, not proof of a betting edge. Future selection/model changes require separate evaluation.
