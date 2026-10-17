데이터 키: row_id=계약 기간. claims는 policy_id+사고일이 기간 안에 있는지로 매칭(99.7% 매칭, 중복 매칭 0)
매칭 안 되는 motor 클레임 297건 제외(2020년 사고 198건, 계약 공백 기간 사고 99건)
repudiated 1,711건은 금액이 전부 0이라 제외
renewal_decision은 train에만 있어 누수 변수로 제외. customer_service_contacts는 누수 여부 확인 필요
incurred는 excess 차감 전 금액으로 판단(closed 클레임 중 excess 이하 비율이 peril별 3~32%)
타깃 = Σ max(incurred − excess, 0) − recoveries. 차감 순서를 바꿔도 결과 동일함을 확인
recovery는 own_damage(22%)와 theft(4%)에만 존재
bodily_injury는 long-tail(보고 지연 중앙값 112일), motor 비용의 41%. 2024년 건수가 예년의 약 55%, open 80%
motor 노출당 비용: 2021 374 / 2022 395 / 2023 385 / 2024 302 → 2024년 미성숙으로 판단, 조정 필요

# Decision Log

## 2026-10-16 — Data structure, claims review, motor target

### Data structure
- **Decision:** Use `row_id` as the unit of analysis (one policy period). `policy_id` repeats across renewals and mid-term changes.
  - **Evidence:** `policy_id` is not unique in `policies_motor`; `row_id` matches the submission format.
- **Decision:** Link claims to policy periods by `policy_id` plus `loss_date` falling within `period_start`–`period_end`.
  - **Evidence:** Claims carry only `policy_id`. Date-based matching assigns 99.7% of motor claims to exactly one period, with zero claims matching more than one period.

### Data quality
- **Decision:** Exclude 297 motor claims (0.26%) that fall outside any policy period.
  - **Evidence:** 198 have 2020 loss dates (before any policy starts); 99 fall in gaps between a policy's periods. These are outside cover and do not belong in the target.
- **Decision:** Exclude repudiated claims (1,711 across all lines).
  - **Evidence:** All repudiated claims have zero paid, incurred, and recoveries; the competition target excludes declined claims.
- **Decision:** Exclude `renewal_decision` from modelling.
  - **Evidence:** Present in training data only, not in test; it reflects information known after the policy period (target leakage).
- **Open question:** `customer_service_contacts` may be influenced by claims during the period. To be checked before use.

### Target definition
- **Decision:** Treat `incurred_to_date` as gross of excess; excess = `voluntary_excess` + `compulsory_excess`.
  - **Evidence:** Among closed motor claims, 3–32% (by peril) have incurred at or below the policy excess, which is consistent with ground-up amounts.
- **Decision:** Per-claim net cost = max(incurred − excess, 0) − recoveries, floored at 0; summed per `row_id`. Rows with no claims have target 0.
  - **Evidence:** Compared two deduction orders (excess first vs. recoveries first); total motor net cost is identical under both (385.5m), so the choice does not affect results.
  - **AI use:** The alternative deduction order was raised during AI-assisted review and verified against the data rather than assumed.
- **Observation:** Recoveries occur only for `own_damage` (22% of incurred) and `theft` (4%), consistent with subrogation and recovered stolen vehicles.

### Development / maturity
- **Finding:** `bodily_injury` is long-tailed — median report lag 112 days, 90th percentile 369 days — compared with 4–14 days for other motor perils.
- **Finding:** `bodily_injury` accounts for 41% of motor net cost. Claim counts by loss year: 2022: 2,187 / 2023: 2,053 / 2024: 1,178. Open share: 28% / 49% / 80%.
- **Finding:** Motor net cost per unit of exposure: 2021: 374 / 2022: 395 / 2023: 385 / 2024: 302. The 2024 drop (~22%) is attributed to immaturity (IBNR and open claims), not lower risk.
- **Next step:** Adjust `bodily_injury` for unreported claims and development on open claims before training. Candidate approach: reporting-delay completeness factors from mature loss years, applied by peril.

### Target build — all lines
- **Check:** Refactored target logic into `build_target(line)`; motor output matches the manual calculation exactly.
- **Finding (buildings):** Net cost per exposure rises each year — 2021: 268 / 2022: 292 / 2023: 305 / 2024: 325 — despite 25% of 2024 claims still open. Suggests an upward trend of roughly 6–7% p.a. Flood (29%) and fire (24%) dominate cost.
- **Finding (contents):** 2021: 64 / 2022: 66 / 2023: 73 / 2024: 73. Moderate upward trend; 2024 likely understated (13% open). Theft (43%) and flood (28%) dominate.
- **Implication:** Motor's main issue is development (bodily injury); buildings' main issue is trend projection to 2025 and separating weather effects from inflation.
- **Next step:** Check whether `weather` includes 2025 values for test addresses.

## 1017 가정 확인
1. 데이터 구조
- 분석 단위는 계약 하나로 정함. policyu_ids는 갱신이나 중도변경 때문에 반복. -> 새 계약과 갱신은 플래그로 다르게 할 예정.
- period_end 포함 여부에 따라 갱신일 당일에 난 사고가 이전기간으로 갈지 다음 기간으로 갈지 바뀐다. 
-building contents 매칭 및 미채칭 건수 확인해야함.
- 중도변경행의 exposure를 기간 길이에 맞게 재구성해야함. 

2. 데이터 정리
- 공백기간 99건은 어떻게 처리했는지 확실하지 않음
- repudiated : 보험사가 보장 대상이 아니라고 거절한 건 : 청구를 자주 했다는 것 자체를 중요하게 볼것인지 아니면 어떻게 할 것인지. : 빈도와 청구건수를 다르게 정의한다. 
빈도 = (순비용 > 0인 클레임 수) / 노출
심도 = 순비용 합계 / (순비용 > 0인 클레임 수)


## 1017 16:17 Decision Log

Decision: Recalculate exposure from period dates where it is inconsistent.
Evidence: 0.5% of training rows use a 360-day year (e.g. 1.0139 for a 365-day period) and about 0.1% record exposure in days (e.g. 327). Correcting them reduces total exposure by 25–28% in every line and year. Test data has no such rows.

Finding: Corrected net cost per exposure is about 35% higher than previously reported, but the year-to-year pattern is unchanged.

Decision: Cap individual motor claims at 500,000 for modelling, and reallocate the excess as a loading.
Evidence: The 99.9th percentile of BI incurred is about 420,000. One open 2023 BI claim of 11.9m accounts for 6% of all BI cost. Excluding the amount above 1m, 2023 BI cost (36.9m) is below 2021–2022, showing that 2023 is also immature.

-------

Decision: Remove duplicate claim records (604 across all lines), keeping one of each pair.
Evidence: These claims have different claim_ids but identical policy, peril, loss date, report date, status, and amounts. Almost all (600 of 604) have 2022 loss dates, consistent with a one-off duplication rather than genuine repeat losses. They inflate 2022 cost by about 2% in each line.

Finding: Bodily injury severity dropped by about 19% (mean) and 25% (median) from loss year 2023, with a clear step at 2023 Q1. The drop holds for claims reported within 365 days, and no other motor peril shows it. BI frequency is stable (10.5–11.4 per 1,000 exposures).
Decision: Treat 2023 as a change in the BI cost environment (consistent with a small-claims reform). On-level 2021–2022 BI losses by a factor of about 0.83 before modelling.
Implication: Other motor perils show rising severity and need trending to 2025.

