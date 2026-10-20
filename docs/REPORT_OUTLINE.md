# Report outline (5 pages, covers Part 1 and Part 2)

Draft Oct 20 for discussion with Krista (Thursday 7 pm). Final report is due at the end of Part 2.

**Thesis:** *AI writes the code; actuaries own the assumptions.* AI made the coding and the breadth of
analysis fast, but it did not guarantee that the assumptions were right. Consistency came from transparent
models, rules fixed before results, and people questioning every actuarial assumption against the data.
Part 2 is used as a test of those assumptions.

**Structure:** sections follow the pricing process; inside each section, Part 1 first, then what Part 2
showed. One table — the **assumption ledger** (section 2) — runs through both parts.

**Judging weights:** Pricing performance and adaptation 40% (private scores Part 1 + Part 2, plus the
panel's view of modelling choices, adaptation, data quality and uncertainty) · Effective use of AI 25% ·
Trust, validation and guardrails 20% · Communication and documentation 15%.

**Rule for every claim:** it points to a file in the repo (DECISIONS.md, ASSUMPTIONS.md, AI_USE_LOG.md,
a notebook or a test).

---

## 0. Summary — ½ page (Krista drafts, Woojin checks numbers)
- Task in one sentence: next-year risk premium per policy period, net of excess and recoveries.
- The thesis and three supporting points:
  1. **Transparent by default:** GLM with readable rating tables; a more complex model only where it passed
     rules fixed in advance (contents). The accuracy given up is measured.
  2. **AI for code, people for assumptions:** code was checked cheaply with tests and sanity checks;
     actuarial assumptions needed questions and experiments. Even a stronger model's two largest
     domain claims were rebutted by our data.
  3. **Part 2 as a test:** every assumption carried a "would be wrong if" condition, checked on the new market.
- Results: Part 1 and Part 2 scores.
- **Timeline strip:** Oct 16 data and target → Oct 19 first submissions, host answer on excess →
  Oct 20 independent review, E5 → Part 2 …

## 1. Data and target — ½ page (Woojin)
- **Part 1:** target definition (excess on every peril: host answer); data issues found and fixed as one
  table (exposure in a 360-day year or days, 604 duplicates, 297 claims outside any period, repudiated
  claims, renewal_decision in train only). AI was good at the breadth of these checks.
- **Part 2:** which checks were rerun as they were, and new data issues.
- **Evidence:** DECISIONS.md; `src/target.py`; tests.

## 2. Assumptions: bringing past claims to next year's cost — 1¼ pages (Woojin) *[thesis point 2 and 3]*
- **Part 1:** how each group was checked: development (truncation-corrected estimate within 0.3 points);
  frequency (2023 level shift); severity (trends gross of excess; **BI reform** step 0.78–0.80, the apparent
  post-reform rise comes from open reserves: 1.2% on closed claims); large losses (Pareto tail, range
  1.2–3.8; the largest BI claims not affected by the reform); weather as location climate.
- **Part 2:** the ledger's right-hand columns.
- **Figure 1:** BI mean severity by loss quarter, all vs closed claims.
- **Table: assumption ledger** (Part 1 filled; Part 2 filled after Part 2)

| Assumption | Why we believe it | Part 1 evidence | Would be wrong if | Part 2 result |
|---|---|---|---|---|
| Excess on every peril | Contract term, per claim | Host answer | — | |
| Late claims via completeness by peril | Reporting delay by peril | Two estimators within 0.3 points; speed unchanged | Reporting speed changes | |
| Frequency level shift 2023 (own damage 0.93, TPP 0.95) | A change in 2023, then flat | Within every driver_assist / telematics group; completeness-adjusted | Year effect vanishes in a frequency GLM | |
| Severity trends gross of excess, excess fixed | Inflation on ground-up loss; leverage | Net medians rise faster than gross | Rise is a one-off step | |
| BI reform step 0.83, no post-reform trend | Legal change from a loss date | Step 0.78–0.80 in every fit, also on closed claims; post-reform 1.2% on closed claims | Step appears by report date only; trend appears once claims close | |
| Large losses: cap + Pareto loading | Heavy liability tail; chance, not rating | Alpha stable across thresholds; range 1.2–3.8 | Tail not Pareto above the threshold | |
| Weather as location climate | Next year's weather unknown; one year is noisy | Validation equal; leaderboard +0.0026 | Year factor leaves weather relativities unchanged | |
| Claim history predicts claims | Experience rating | Past-claim rows under-priced 22–80% before | Gradient disappears out of time | |
| customer_service_contacts is leakage | Contacts caused by claims | 12–72× same-year vs next-year; test distribution differs | — | |
| Relative premium (contents) | Insurer's price holds unseen information | +0.0010 D²; circular | — | |

## 3. Model: transparent by default — ¾ page (Woojin) *[thesis point 1]*
- **Part 1:** ridge-penalised Tweedie GLM with banded factors and a balance factor (credibility, level,
  readable tables); claim history; contents uses a shallow LightGBM (passed the tail rule).
  **Measured trade-off:** GBM would raise buildings D² by about 0.009 but over-price the safest 10% by
  15–30%; D² barely penalises this because their expected cost is small. We kept the GLM.
- **Part 2:** what the same model needed to change for a new market.
- **Figure 2:** decile A/E, GLM vs GBM, buildings.

## 4. Validation and guardrails — ¾ page (Woojin, Krista edits) *[Trust; strictness]*
- Rules fixed before results (table); two out-of-time folds.
- Leaderboard used only to check predictions written before each submission: 7 of 9 consistent; the two
  misses explained (v6 motor level; v8 weather, attributed with a second submission).
- Planted-error test; leakage caught; reproducibility (v7 rebuilt within 0.002%); pipeline and CI.
- **Part 2:** the same rules reused unchanged (or what changed, and why).
- **Table:** predicted vs observed leaderboard change per submission.

## 5. How we used AI — ½ page (Krista drafts from AI_USE_LOG) *[AI 25%; thesis point 2]*
- Roles: one model writes code and analysis; a second model (new chat, no shared context) reviews the
  assumptions; the team sets rules and decides.
- **Counts from AI_USE_LOG:** entries by type (AI proposed / team questioned / AI error), and AI errors
  split into code errors (caught by tests and checks) and assumption errors (caught by questions and data).
- Examples: tie-break direction, frequency false alarm, a leaking feature suggested and withdrawn, the
  final-submission rule assumed wrongly, the reviewer's two largest findings rebutted.
- What we did not delegate: target definition, rules, adoption decisions.

## 6. Limitations, uncertainty and lessons — ½ page (both)
- Uncertainty: BI post-reform trend (motor +5.1% if adopted), open-claim development, recoveries on open
  claims (2024 −1.6%), large-loss loading range, premium circularity, four years of history.
- Lessons: effective use of AI meant knowing where to trust it. Code is cheap to verify; assumptions are
  not. Strict, pre-set checks kept the work consistent across two markets.

## Appendix (outside the 5 pages, in the repo)
- DECISIONS.md, ASSUMPTIONS.md, AI_USE_LOG.md, README (how to reproduce), tests.

---

## Page budget
| Section | Pages |
|---|---|
| 0 Summary | ½ |
| 1 Data and target | ½ |
| 2 Assumptions + ledger | 1¼ |
| 3 Model | ¾ |
| 4 Validation | ¾ |
| 5 AI | ½ |
| 6 Limitations and lessons | ½ |
| Figures (2) and timeline | ¼ |
| **Total** | **5** |

## To decide on Thursday
1. Agree the thesis and the three points.
2. Who writes which section, and the drafting deadline before Part 2 starts.
3. Figures: the two above plus at most one more.
4. Video (5 minutes): Krista records; script follows the thesis → ledger → model trade-off → AI roles.
