# Milestone compatibility and FTB research visibility

FanDuel's current full-game milestone labels omit the older "To Score", "To Record" and "Made" wording. The collector now accepts the observed short labels and existing long labels only when they agree with the exact unchanged market type and integer target. Source labels, market/selection/player IDs, prices and capture timestamps are retained verbatim. Ordinary over/under parsing is unchanged.

The website loads `ev_offers.js` after the original `ev_service.js`. This adapter validates a temporary canonical-label copy through the original guards and retains the original quote object. The original validator asset remains byte-identical for the independently locked local betting trial. The trial checkout and its local collector are not upgraded by the website release.

The EV tab now distinguishes:

- Milestone offers not captured, offers captured but unavailable/stale, model-supported offers, and offers hidden by display filters.
- Exact First Team Basket prices not captured or no longer current, versus probability and EV withheld by model policy.
- Retained same-team first-score/start counts versus a forecast probability. Prices and descriptive history remain visible in a research-only panel even when a count-market/bet-type filter is selected.

`firstTeamResearch` snapshots retain the source quotes and descriptive counts with an evaluation timestamp. The existing browser export retains these captures. Compatibility version and code hash accompany new records; legacy records retain their original service-validation path. The browser archive identity includes the new research content but excludes its changing evaluation timestamp, preserving deduplication of identical input evidence.

FTB remains each team's first score including free throws, conditional on the selected player starting. Whole-game First Basket and Method of First Basket are not substitutes. The published `ev-first-team-v1.2` model remains disabled, with unchanged weights, release gate, model hash and temporal-leakage notice. Count-model weights and tail-support gates are also unchanged. No odds ranking or descriptive count becomes a recommendation or validated EV claim.

Regression coverage includes the four observed short labels, legacy labels, wrong threshold/stat/period/source/identity rejection, stale and suspended markets, source quote immutability, UI filter visibility, absent versus withheld status, new-record grading, rejection of unknown compatibility versions, and continued invalidation of the retired FTB forecasts.

Release verification must confirm restored publication data is not older than the previously published season, the exact original validator hash remains available to the local trial, the collector begins publishing milestone quotes, and FTB remains disabled after deployment.
