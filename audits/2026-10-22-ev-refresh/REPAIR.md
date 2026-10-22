# EV list freshness gaps — 2026-10-22

Starting release: `65674fddf1e98574d4df741fb783ddc537669fcf` (PR #2). This change repairs refresh timing, with no forecasting changes.

## Confirmed mechanism and source evidence

`ev_probability.js` and `ev_service.js` reject prices older than 300 seconds. The UI schedules an exact expiry wake-up and removes expired offers; this is intentional. Before this repair, `fanduel_odds.run()` targeted 300-second capture starts and `ev_ui.js` used the default 300-second browser poll. A capture interval equal to its permitted age leaves no publication/transport headroom. Unaligned browser reads can retain an expiring snapshot until their next poll. The existing once-per-commit 30-second catch-up helps only if a replacement has published by that read.

At the diagnostic read recorded as `2026-10-22T06:31:59.620871+00:00`, the returned odds branch reference was `7453d72f499becdb92a869529e7c1f41600a0647`. Its 1,290 quotes were captured between `06:25:18.892523Z` and `06:25:21.472428Z`, so none passed the unchanged five-minute age check using this device clock. A subsequent independent clock check found the device approximately 179 seconds fast; therefore this is evidence of early device-based expiry, not proof that the publisher had actually gone more than five real minutes without a capture. Root `errors` was empty. The last 12 branch commits were published about every five minutes (05:30:23 through 06:25:22 UTC). That demonstrates the timing vulnerability; it does not prove the collector was stopped or establish the exact cause of every earlier user incident. The public snapshot, branch history and read summary are preserved outside production under `reports/2026-10-22-ev-feed-disappearance` in the parent workspace.

The worker's GitHub run `39700823183` was active, with its capture step starting at 03:00:13 UTC. A scheduled job's creation time is not its actual worker start time. Do not treat an in-progress long watch job or an eventual issue exit code as evidence that every capture failed.

## Second confirmed contributor: host clock

At local UTC `06:37:31`, fresh query-string HTTP requests to both GitHub API and ESPN returned HTTP Date `Thu, 22 Oct 2026 06:34:32 GMT` (round trips below 0.3 seconds, no Age header; ESPN reported a cache miss). The approximately 179-second offset agrees across two independent servers. `w32tm /query /status` returned `The service has not been started (0x80070426)`. This establishes a clock problem on the inspected computer; it does not establish the clock state of other devices. The existing app uses device time, so this offset prematurely expires quotes. The cadence repair alone cannot eliminate that host-clock problem. Windows synchronization was requested separately because it changes a computer setting outside the app; no clock change is authorized until the user answers.

## Repair

- Active odds worker targets 120-second capture starts; elapsed capture time is subtracted from sleep. Existing bounded four-hour worker lifetime and five-minute scheduled launches stay unchanged.
- EV browser reads use a 120-second interval, with existing no-overlap, visibility-return refresh and cleanup behavior. Other lineup callers retain their 300-second default.
- The interface describes the two-minute cadence and explicitly states that delays/outages can still pause estimates.
- Price age limits, timestamps, model files, mathematical engines, rankings, evidence rules, saved selections and FTB probability withholding are unchanged.

## Acceptance evidence

- Browser EV tests: 32 passed, including a replacement fetched before old-price expiry, cleanup, expired/cached exclusion, catch-up, late-save refusal, all supported markets and unchanged context math.
- Lineup projection tests: 17 passed, including separate EV cadence with default lineup cadence preserved. Live refresh/availability checks passed.
- Odds collector tests: 19 passed. The worker deducts capture time, retries after a failed watch cycle with the original previous snapshot, and handles an overlong cycle without negative sleep or renewed timestamps.
- Publication build tests: 11 passed.
- `independent-cadence-reference.json` uses direct time arithmetic, not the production worker/helper. Every integer-second phase pair is evaluated over an hour with assumed ten-second publication and ten-second read delays. The old 300/300 configuration permits age up to 619 seconds immediately before a read; the repaired 120/120 configuration stays below 260 seconds with no expired intervals in that scenario. These are timing diagnostics, not observed production availability percentages.

## Limits and release acceptance

This creates headroom during successful active-worker cycles. It cannot guarantee uptime through source outages, GitHub/API failures, browser suspension, long captures or worker handoff delays. Expired, cached or started-game quotes must still disappear. It does not establish betting profitability or repair the separately withheld FTB model.

Release acceptance requires successful publication, matching public asset hashes, and a restarted worker from the repaired main revision. Observe consecutive distinct odds commits/capture times at the new cadence; a successful workflow dispatch alone does not prove feed freshness. Record live checks in the parent-workspace evidence directory.
