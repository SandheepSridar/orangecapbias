# TNPL 2025 data-quality report

## 1. Structural checks
- Matches in schedule: **32**, deliveries scraped: **7439**
- PASS — every scheduled match scraped
- PASS — no duplicate deliveries (match, innings, over, ball)
- PASS — ball numbers consecutive within each over
- PASS — over numbers consecutive within each innings
- PASS — non-final overs have at least 6 deliveries
- PASS — per-ball values in range (0<=runs_total<=8, 0<=runs_batter<=6, extras>=0, 0<=wickets<=2)
- PASS — player names resolved (no bare athlete ids)
- PASS — wickets carry a dismissal kind

## 2. Innings totals vs official scores (summary header)
- Innings reconciled exactly: **64**
- PASS — every innings total (runs & wickets) matches the official score

## 3. External cross-checks
- Season top-5 run scorers (scraped):
    - Tushar Raheja: 488 runs, SR 186
    - Baba Aparajith: 412 runs, SR 158
    - VP Amit Sathvik: 340 runs, SR 139
    - Shivam Singh: 327 runs, SR 142
    - Ravichandran Ashwin: 297 runs, SR 154
- PASS — run leader matches espncricinfo report (Tushar Raheja, 488 runs, SR 186)

**VERDICT: all checks passed — dataset reconciles with official scorecards and external reports.**
