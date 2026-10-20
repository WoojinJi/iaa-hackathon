# Report outline (5 pages, covers Part 1 and Part 2)

Draft Oct 20 for discussion with Krista (Thursday 7 pm). Final report is due at the end of Part 2.
Page budget follows the judging weights. Each section names the evidence it rests on, so nothing is
claimed that the repo cannot show.

**Judging weights:** Pricing performance and adaptation 40% (private scores Part 1 + Part 2, plus the
panel's view of modelling choices, adaptation, data quality and uncertainty) · Effective use of AI 25% ·
Trust, validation and guardrails 20% · Communication and documentation 15%.

---

## 0. Summary — ½ page (Krista drafts, Woojin checks numbers)
- The task in one sentence: 2025 risk premium per policy period, net of excess and recoveries.
- Approach in three lines: on-level 2021–24 claims to 2025 → penalised Tweedie GLM with banded factors
  (LightGBM for contents) → out-of-time validation with rules fixed before results.
- Results: Part 1 and Part 2 scores; the three judgement calls that mattered most (below).
- One line on AI use: one model builds, a second model reviews independently, humans decide.

## 1. Problem and data quality — ½ page (Woojin)
- Target definition and why it is a risk premium (excess on every peril: host answer).
- Data issues found and fixed, as one table: exposure in a 360-day year or in days (25–28% of exposure),
  604 duplicate claims (2022), 297 claims outside any period, repudiated claims, renewal_decision (train only).
- **Evidence:** DECISIONS.md Oct 16–17; `src/target.py`; tests.

## 2. Bringing 2021–24 to 2025 cost — 1 page (Woojin) *[Pricing: data quality and uncertainty]*
- Development: completeness by peril; checked against a truncation-corrected (Lynden-Bell) estimate:
  ≤ 0.3 points apart. Reporting speed unchanged.
- Frequency: 2023 level shift in own damage and third-party property (0.93 / 0.95); weather perils
  handled through weather, not trends.
- Severity: trends gross of excess with the excess fixed (leverage); **BI 2023 reform** — step 0.78–0.80
  by loss date, also in closed claims; the apparent post-reform rise (8.6%) comes from open reserves
  (1.2% on closed claims). Largest claims (99th percentile) unaffected.
- Large losses: cap, Pareto tail, loading range 1.2–3.8 per weight.
- **Figure 1:** BI mean severity by loss quarter, all vs closed claims (the reform step).
- **Table:** assumption status (verified / judgement / open) — summary of ASSUMPTIONS.md.

## 3. Model and the choices behind it — ¾ page (Woojin) *[Pricing: modelling choices]*
- Ridge-penalised Tweedie GLM, banded factors, balance factor: why (credibility, level, explainable tables).
- Claim history (known by 1 January): the largest single gain; rows with a past claim were under-priced 22–80%.
- Average weather instead of actual 2025 weather: practical and, on the leaderboard, more accurate.
- **Champion vs challenger:** GBM raises buildings D² by about 0.009 but over-prices the safest 10% by
  15–30%; D² barely penalises this. We chose the GLM. Contents uses a shallow GBM (tails within limits).
- Features rejected and why (instability, leakage, circularity).
- **Figure 2:** decile A/E, GLM vs GBM, buildings (shows the trade-off).

## 4. Validation and guardrails — ¾ page (Woojin, Krista edits) *[Trust 20%]*
- Two out-of-time folds; rules fixed before results (table of rules).
- Leaderboard used only to check predictions written before each submission: 7 of 9 consistent; the two
  misses explained (v6 motor level; v8 weather).
- Planted-error test: which diagnostics attribute errors correctly.
- Leakage caught: customer_service_contacts (D² 0.05 → 0.55 alone; test distribution differs).
- Reproducibility: v7 rebuilt from code within 0.002%; pipeline and CI.
- **Table:** predicted vs observed leaderboard change per submission.

## 5. Part 2: adapting to an emerging market — ¾ page (both) *[Pricing: adaptation]*
- To fill in Part 2: what transferred unchanged, what was re-estimated, new data-quality issues, how the
  rules and checks were reused.

## 6. How we used AI — ½ page (Krista drafts from AI_USE_LOG) *[AI 25%]*
- Roles: one model writes code and analysis; a second model (new chat, no shared context) reviews the
  assumptions; humans set rules and decide.
- What AI got wrong and how it was caught (counts and 3–4 examples from AI_USE_LOG: tie-break direction,
  false alarm on frequency, a leaking feature suggested and withdrawn, over-estimated run times).
- Independent review: 8 findings → accepted / tested / rebutted with data.
- What we would not delegate to AI (target definition, adoption decisions).

## 7. Limitations and uncertainty — ¼ page (Woojin)
- BI post-reform trend (sensitivity +5.1% on motor); open-claim development (IBNER); recoveries on open
  claims (2024 −1.6%); large-loss loading range; premium feature circularity; four years of history.

## Appendix (outside the 5 pages, in the repo)
- DECISIONS.md, ASSUMPTIONS.md, AI_USE_LOG.md, how to reproduce (README), tests.

---

## To decide on Thursday
1. Who writes which section (proposal above), and the drafting deadline before Part 2 starts.
2. Figures: the two above plus at most two more.
3. Video (5 minutes): Krista records; script follows sections 0, 2, 3, 4, 6.
4. Tone: actuarial audience (judges) — plain words, numbers with their source.
