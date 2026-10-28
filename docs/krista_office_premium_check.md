# Independent check of the office premium (Krista, Oct 27-28)

**Result: Krista's spreadsheet reproduces all 20 reference-policy office premiums of the final model (v9) exactly**
(maximum absolute difference 9e-13, i.e. floating-point rounding). Checked by Woojin on Oct 28.

## What was checked
- Input: `results/office_premium_v9/reference_20.xlsx` (output of `tools/office_premium.py` on `submissions/p2_v9_e27_simplified.csv`).
- Krista rebuilt each office premium in Excel from the formula and the emerging-market expense assumptions only, without the code:
  - risk premium (annual) = risk_row / exposure
  - catastrophe reinsurance = 12% of the risk premium for buildings and contents, 0 for motor
  - fixed expense 85; variable expense 15%; premium tax 8%; profit margin 8%; commission broker 20%, direct 0%
  - office premium = (risk premium + cat reinsurance + fixed) / (1 - variable - commission - tax - profit)
- Her column is compared with `office_annual` row by row (sheet rows 25-44).
- File (not committed, like all xlsx): `results/office_premium_v9/krista_office_premium_check.xlsx`.

## How it went
- First version (Oct 27): two differences. The risk premium was multiplied by `risk_annual` again (it is already
  risk_row / exposure), and catastrophe reinsurance was applied to motor. Both came from our instructions: the column
  explanation was too brief, and the details were spread over several emails.
- Corrected version (Oct 28): both fixed; all 20 rows match.

## Why it matters
- The office premium is computed in one script; this is a second, independent implementation of the same formula by a
  team member who did not write the code. It confirms the formula and the expense assumptions, not the risk premium itself.
