# Report outline (5 pages, covers Part 1 and Part 2)

First draft Oct 20; revised Oct 22 (structure kept, black-box comparison and AI checks woven in; Part 1 results
added the same night). Final report is due at the end of Part 2.

**Thesis:** *AI writes the code; actuaries own the assumptions. A black-box comparison measures what that
ownership is worth.* AI made the coding and the breadth of analysis fast, but it did not guarantee that the
assumptions were right: 24 of its outputs were wrong, 17 of them in judgement rather than code.
Consistency came from transparent models, rules fixed before results, and people questioning every
actuarial assumption against the data. A maximum-accuracy black box (E9) shows the price of that choice in
score, and what it buys in fair prices and traceable errors. Part 2 tests the assumptions and the comparison.

**Structure:** sections follow the pricing process; inside each section, Part 1 first, then what Part 2
showed. Two threads run through every section:
- the **assumption ledger** (section 2), with a Part 2 column;
- one line **"AI did / we checked"** with the AI_USE_LOG entry numbers, so AI use is shown where it
  happened, and section 5 only adds it up.

**Judging weights:** Pricing performance and adaptation 40% (private scores Part 1 + Part 2, equally
weighted, plus the panel's view of modelling choices, adaptation, data quality and uncertainty) · Effective
use of AI 25% · Trust, validation and guardrails 20% · Communication and documentation 15% (Rules 2.4.c).

**Rule for every claim:** it points to a file in the repo (DECISIONS.md, ASSUMPTIONS.md, AI_USE_LOG.md,
a notebook, a tool or a test).

**Written before the Part 2 data (Oct 22), to be checked in Part 2:** *the black box scores higher, but
when it is wrong we cannot say why, and its errors fall on the safest customers.*

**Part 1 result (Oct 22):** the prediction was half right. The black box did *not* score higher: the strongest
stack we built tied v11 on the leaderboard (0.12296 vs 0.12307) and lost on the tails in every line; the one
gain came from actuarial structure, frequency x severity GLMs for motor (v12, 0.12336, the final Part 1 entry).

---

## Part 2 update (Oct 26) — this section wins where it differs from the Part 1 draft below

**Thesis (unchanged):** *AI writes the code; actuaries own the assumptions.* **Part 2 addition:** the largest score gains came from
assumptions, not model capacity: where relativities are learned (E17, 0.112 -> 0.122), the broker-book load (-> 0.141), the claim-amount
definition (-> 0.143). The black box did not beat our GLM in either market; the Oct 22 prediction ("the black box scores higher") was
wrong again.

**Results:** Part 1 final v12 (public 0.12336, private 0.13099). Part 2 final v9 (public 0.14477), rebuilt exactly from a fresh clone
(max difference 0).

**Judging weights:** pricing performance and adaptation 40% (private scores + modelling choices, adaptation, data quality, uncertainty),
effective AI use 25%, trust / validation / guardrails 20%, communication 15%. Task requirement: office premium for each of the 20
reference policies. Rules 2.9: reproducible code (done).

| # | Section | Content | Pages | Criterion | Draft |
|---|---|---|---|---|---|
| 0 | Summary | task, thesis, results, timeline | 1/2 | communication | Krista |
| 1 | Data and target | Part 1 issues; Part 2: excess double deduction (back to Part 1, private -0.0020), sum_insured x1000, row completeness (E22), independent audits (AI 108, 114) | 3/4 | pricing (data quality) | Woojin |
| 2 | Assumption ledger | DECISIONS "Part 2 results" table: held / changed / wrong -> fixed / borrowed / new, with source class (doc / data / LB / dev) | 3/4 | pricing (uncertainty) | Woojin |
| 3 | Model and adaptation | GLMs, developed relativities + emerging level, flat fire, flood GLM, broker-book load, E27 simplification (v9); black-box table Part 1 + Part 2; figures: relativities, deciles | 1 | pricing (modelling, adaptation) | Woojin |
| 4 | Office premium, 20 policies | formula, expense assumptions, the 20-row table (2-6x current premium), six open judgements; Krista's independent spreadsheet check | 1/2 | pricing; task requirement | Krista checks, Woojin writes |
| 5 | Validation and guardrails | rules fixed before results; submission history (6 of 9 inside the written range; v8 withdrawn by its guard; v9 above); Murphy decomposition and new-business band; reproducibility; 51 tests | 1/2 | trust | Woojin, Krista edits |
| 6 | How we used AI | roles (builder AI -> reviewer AI -> team); log counts; questions that caught errors (15, from the question log); one story in depth (the excess); quoted prompts | 3/4 | AI use | Krista drafts |
| 7 | Limitations and lessons | broker-book size from the leaderboard, borrowed severity trends, IBNER not modelled, buildings safest decile over-priced; no claim-file reconciliation | 1/4 | pricing (uncertainty) | both |

**AI log counts (Oct 26, entries 1-116, 113 in table form):** H 42 (team questioned), E 37 (AI errors), A 34 (AI proposed, team verified).
Part 2 (93-116): H 10, E 11, A 3 — AI proposed less, the team questioned more and caught more AI errors.

**Figures (docs/figs):** fig_submission_history.png (section 5), fig_deciles_v9.png (3), fig_relativities_v9.png (3); Part 1 figures as
planned below. Still to make: assumption-ledger summary graphic or table (2), AI roles diagram (6).

**Video (5 min):** keep the Part 1 plan; the last minute becomes "Part 2: assumptions moved the score".

---

## 0. Summary — ½ page (Krista drafts, Woojin checks numbers)
- Task in one sentence: next-year expected claim cost per policy period, net of excess and recoveries.
- The thesis and three supporting points:
  1. **Transparent by default, with the cost measured:** GLM with readable rating tables; a GBM only where
     it passed rules fixed in advance (contents). The black box (E9) shows what we gave up and why.
  2. **AI for code, people for assumptions:** code was checked cheaply with tests and sanity checks;
     assumptions needed questions and experiments. Even a second model's two largest domain claims were
     rebutted by our data.
  3. **Part 2 as a test:** every assumption carried a "would be wrong if" condition, and the black-box
     prediction was written down before the new data.
- Results: Part 1 public 0.12336 (v12); the best black box tied v11 and lost on the tails. Part 2 scores: …
- **Timeline strip:** Oct 16 data and target → Oct 19 first submissions, host answer on excess →
  Oct 20 independent review, E5, mix → Oct 21 pipeline, v11 → Oct 22 black boxes E9, E10; v12 → Part 2 …

## 1. Data and target — ½ page (Woojin)
- **Part 1:** target definition (excess on every peril: host answer); data issues found and fixed as one
  table (exposure in a 360-day year or days, total exposure −25–28%; 604 duplicates; 297 claims outside
  any period; repudiated claims; renewal_decision in train only).
- **AI did / we checked:** AI found the exposure and duplicate issues (8, 9); a code error turned amounts
  into dates and was caught by an implausible output (7); the excess assumption came from AI and was
  settled by the host, not the leaderboard (41).
- **Part 2:** which checks were rerun unchanged (`src/checks.py`), and new data issues.
- **Evidence:** DECISIONS.md Oct 16–17; `src/target.py`; tests; `docs/checks_part1_report.md`.

## 2. Assumptions: bringing past claims to next year's cost — 1 page (Woojin) *[thesis point 2, 3]*
- **Part 1:** how each group was checked:
  - development: report-lag completeness; truncation-corrected estimate (Lynden-Bell) within 0.3 points;
  - frequency: the 2023 drops were **mix**, so no shift (A/E 1.031 → 1.000);
  - severity: trends gross of excess (leverage); **BI reform** step 0.78–0.80, applied as 0.83; the
    apparent post-reform rise comes from open reserves (8.6% all claims, 1.2% closed);
  - large losses: cap + Pareto loading (range 1.2–3.8); the largest BI claims not affected by the reform;
  - weather as location climate (average 2021–24).
- **AI did / we checked:** AI proposed the reform (13) and over-stated the mix effect (67); the team's
  step scan and seasonality questions found what AI had not looked for (64–65).
- **Part 2:** the ledger's right-hand column.
- **Figures:** fig1 (frequency and severity brought to 2025 level, 6 panels); fig1b (BI severity by loss
  quarter, all vs closed claims).
- **Table: assumption ledger** (Part 1 filled; Part 2 filled after Part 2)

| Assumption | Why we believe it | Part 1 evidence | Would be wrong if | Part 2 result |
|---|---|---|---|---|
| Excess on every peril | Contract term, per claim | Host answer | — | |
| Late claims via completeness by peril | Reporting delay by peril | Two estimators within 0.3 points; speed unchanged | Reporting speed changes | |
| No frequency level shift (removed Oct 20) | 2023 drops are mix, already in the features | Drops vanish after all rating features; A/E 1.031 → 1.000 | A drop remains after all features | |
| Severity trends gross of excess, excess fixed | Inflation on ground-up loss; leverage | Net medians rise faster than gross | Rise is a one-off step | |
| BI reform step 0.83, no post-reform trend | Legal change from a loss date | Step 0.78–0.80 in every fit, also on closed claims; post-reform 1.2% on closed claims | Step appears by report date only; trend appears once claims close | |
| Large losses: cap + Pareto loading | Heavy liability tail; chance, not rating | Alpha stable across thresholds; range 1.2–3.8 | Tail not Pareto above the threshold | |
| Weather as location climate | Next year's weather unknown | Validation within 0.001; leaderboard +0.0026 | — | |
| Claim history predicts claims | Experience rating | Past-claim rows under-priced 22–80% before | Gradient disappears out of time | |
| customer_service_contacts is leakage | Contacts caused by claims | 12–72× same-year vs next-year; test distribution differs | — | |
| Relative premium (contents), by start month | Insurer's price holds unseen information; mid-2021 rate step | +0.0010 D² (+0.0003 by month); circular | — | |
| Flood risk is not additive (buildings) | Height and river distance matter within a flood zone | Five flood-geography pairs, +0.0025 D², tails better | Pairs not kept on Part 2 data | |

## 3. Model: transparent by default, with the cost measured — 1 page (Woojin) *[thesis point 1]*
- **Part 1:** ridge-penalised GLMs with banded factors and a balance factor (credibility, level, readable
  tables). Motor: frequency (Poisson) x severity (Gamma) GLMs (v12). Buildings: Tweedie GLM with five flood
  interactions found by a GBM and moved into the GLM (+0.0025, 28% of the GBM's gain). Contents: a shallow,
  regularised LightGBM (passed the tail rule, +0.0106).
- **The measured trade-off:** the buildings blend (E8) gains +0.0072 D² but over-prices the safest 10% by
  about 27%; D² barely penalises this because their expected cost is small. Kept the GLM: over-priced safe
  customers leave.
- **Structure, not capacity:** a Tweedie GLM makes every factor move frequency and severity in the same
  direction. In motor, claim history (frequency up to ×3, severity slightly lower), cover type and voluntary
  excess pull them apart; splitting the two gained +0.0025 with both tails closer to 1. In buildings the main
  factors (flood geography, sum insured) move both the same way, and the split failed the tails.
- **Black boxes vs ours (E9, E10) and the structural gain (v12):** same target and loading throughout.

| | v11 | **v12 (final)** | E10 stack (4 models + network) | E9 black box max |
|---|---|---|---|---|
| Public score | 0.12307 | **0.12336** | 0.12296 | 0.11602 |
| Validation D² vs v11: motor / buildings / contents | — | +0.0025 / 0 / 0 | +0.0016 / −0.0005 / −0.0042 | −0.0068 / −0.0124 / −0.0261 |
| Worst tail distance from 1 (buildings, contents) | 0.15, 0.23 | 0.15, 0.23 | 0.34, 0.42 | 0.64, 0.79 |
| Seed spread per row | 0 (GLM) / 3.7% contents | same | one seed | 7.5–10% |
| Can a miss be traced? | rating table | two tables: more claims or larger claims | no | no |

- **Message:** capacity alone over-fitted (E9); a tuned stack tied but priced the extremes worse (E10); the gain
  came from structure (v12). Be fair in the text: E10 is a reasonably tuned stack (one seed, no search), not an
  exhaustive one; early stopping halted every model after few iterations, which suggests the data supports
  limited complexity.
- **Literature (check the full papers before citing):** CANN (Schelldorfer & Wüthrich, GLM + network
  correction; our Oct 19 "GBM on top of the GLM" is the tree version); Holvoet, Antonio & Henckaerts
  (frequency–severity benchmark of GLM, GBM, network and CANN, with surrogate GLMs as tariffs); Henckaerts et
  al. (tree models in tariff plans). Double lift charts: CAS Monograph 5, section 7.2.2.
- **AI did / we checked:** AI's tie-break rule pointed the wrong way (33); the 3% limit on k had no
  evidence (36); the blend was retested and rejected under the unchanged rule (81); AI carried v11's ridge
  strength into the frequency and severity GLMs and flattened them, caught by a direction table that
  contradicted a known raw result (83).
- **Part 2:** what the same model needed to change, and the comparison repeated (benchmark → diagnose the gap
  with a double lift chart and a surrogate GLM → move what is found into the GLM; at most two cycles).
- **Figure:** fig4 (buildings decile A/E: GLM + interactions vs blend vs GBM); possibly a double lift chart
  v12 vs stack.

## 4. Validation and guardrails — ¾ page (Woojin, Krista edits) *[Trust]*
- Rules fixed before results (table: GBM +0.003 and tails; feature +0.0005; removal −0.0005; leakage
  excluded whatever its score); two out-of-time folds; settings chosen on the last training year only.
- Leaderboard used only to check predictions written before each submission: of 15, 6 inside the range,
  6 within 0.00025, 3 outside (v6 motor level; v8 weather, attributed with a second submission; E9, which the
  validation would have flagged had it been run first).
- Planted-error test (AI's diagnostic rule 3 of 7; model-free checks 6 of 7); leakage caught; tools tested
  on known answers first (the monthly step scan failed its control and was fixed); reproducibility (v9
  rebuilt exactly); one-command pipeline, 46 tests, CI.
- **Part 2:** the same rules reused unchanged (or what changed, and why).
- **Figure:** fig2 (predicted vs observed leaderboard change per submission).

## 5. How we used AI — ¾ page (Krista drafts from AI_USE_LOG) *[AI 25%, Trust 20%]*
- **Roles:** builder AI (code, tests, analyses, hypotheses) → reviewer AI (a second model in a new chat,
  reviews but does not design fixes) → the team (rules and every decision). Figure fig3.
- **Counts (to update at the end of Part 2):** 82 entries to Oct 21: A 32 (AI proposed, team verified), H 27
  (team questioned), E 24 (AI errors: 17 judgement, 7 code); Oct 22 adds the ridge-scale error (83). The AI was rarely wrong about code and often wrong about what numbers meant.
- **Six checking habits, one catch each:** "what was your criterion?" (22); test the AI's own rules (29);
  independent reviewer (58–59); check the source, not the AI (41, 61); domain questions the AI did not
  ask (64–65); numbers that look too familiar (82).
- **One story in depth (same as the video):** the excess (41).
- **What AI made possible:** a hypothesis tested within a day; pipeline and checks tool; 46 tests; an
  expected score written before every submission.
- **What we did not delegate:** target definition, rules, adoption decisions.
- Layout example: `AI_사용로그_정리_및_보고서_레이아웃.pdf` (Oct 22).

## 6. Limitations, uncertainty and lessons — ½ page (both)
- Uncertainty: BI post-reform trend (motor +5.1% if adopted), open-claim development (IBNER), recoveries
  on open claims (2024 −1.6%), large-loss loading range, motor level (features drift with time; under 1%),
  premium circularity, customers with 2+ past claims under-priced, four years of history.
- Lessons: effective use of AI meant knowing where to trust it. Code is cheap to verify; assumptions are
  not. A higher score is not a better price. Strict, pre-set checks kept the work consistent across two
  markets.

## Appendix (outside the 5 pages, in the repo)
- DECISIONS.md, ASSUMPTIONS.md, AI_USE_LOG.md, PART2_PLAYBOOK.md (committed before Part 2), README (how to
  reproduce), tests, tools.

---

## Figures (plan)
| # | File | Shows | Section |
|---|---|---|---|
| 1 | fig1_freq_sev.png | Frequency and severity by year per line: raw vs brought to 2025 level | 2 |
| 1b | fig1b_bi_reform.png | BI severity by loss quarter, all vs closed claims | 2 |
| 2 | fig2_leaderboard.png | Expected range before each submission vs observed | 4 |
| 3 | fig3_ai_roles.png | Builder AI → reviewer AI → team; log entries by type | 5 |
| 4 | fig4_tails.png | Buildings decile A/E: GLM + interactions vs blend vs GBM | 3 |
| 5 | fig5_outliers.png | Perils with the longest tails, largest claims, caps | 2 or appendix |
| — | Black-box table (E9, E10, v11, v12) | Score, tails, stability, traceability | 3 |
| — | Assumption ledger | Status at a glance (table) | 2 |

## Page budget
| Section | Pages |
|---|---|
| 0 Summary | ½ |
| 1 Data and target | ½ |
| 2 Assumptions + ledger | 1 |
| 3 Model + E9 | 1 |
| 4 Validation | ¾ |
| 5 AI | ¾ |
| 6 Limitations and lessons | ½ |
| **Total** | **5** |

## Video (5 minutes)
| # | Content | Time | Who (proposal; open to swapping) |
|---|---|---|---|
| 1 | Thesis | 0:30 | Krista |
| 2 | Adjustments and the assumption ledger | 1:30 | Woojin |
| 3 | Model: structure beat capacity (v12 vs the stack) | 1:00 | Woojin |
| 4 | AI roles and one error in depth (the excess) | 1:00 | Krista |
| 5 | What Part 2 changed | 1:00 | Woojin |
Storyboard, script and recording tool to be decided.
