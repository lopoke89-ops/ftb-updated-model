# Parlay Machine update — October 9, 2026

The Parlay tab now generates one First Team Basket, Points and Three-Pointers Made selection per team. Its dedicated competition selector keeps regular-season and playoff samples separate, while expanded player cards show both sets of season averages. The existing first-team scoring definition includes made free throws.

All markets use equal weights for team scoring by specific position, opponent allowance by specific position and player opportunity. Points requires a positive game-level FGA/FGM correlation; Threes requires a positive 3PA/3PM correlation. Both also use historical minutes, volume and conversion. The evidence score is a descriptive ranking, not a calibrated win probability. Manual sportsbook lines produce historical-mean Over/Under comparisons; no sportsbook prices, expected value or combined parlay probability are supplied.

The supplemental shooting evidence reconciles every played-player record in 1,322 hash-matched saved box-score captures. Regular season contains 1,230 games; playoffs contain 85. Play-in and the standalone Cup final remain outside both Parlay samples. Missing data, unknown specific positions and insufficient samples retain an explicit unavailable market slot. Traded-player stints, dated pregame cutoffs, rolling windows, head-to-head filters and player exclusions are preserved.

The original theme, canonical data and evaluated first-score model remain unchanged. The new ranking weights have not been calibrated as a forecasting model.

Validation: 170 checks passed in the local application workspace. The public website workflow runs its 125 applicable checks, including 22 Parlay regressions and six export checks, before deployment. Browser acceptance verified six market cards, competition switching, manual prop-line comparisons and separate season averages.
