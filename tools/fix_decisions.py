import sys
from pathlib import Path

d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "IAA" / "DECISIONS.md"
s = d.read_text()

RULE1 = """### Rule 1 applied: new business against the developed market [notebook 22_part2_new_business]
- **Credibility formula (fixed before running):** if the emerging relativity differs from the developed one by
  more than two standard errors, use Z x emerging + (1 - Z) x developed on the log scale, with limited-fluctuation
  credibility Z = min(1, sqrt(n / 1,082)), n = emerging new-business claims (full credibility: 90% within ±5%).
- **Method:** GLM on 2023–24 (emerging) and 2021–24 (developed) with the same features (developed ages banded
  like the emerging age bands; buildings without fire in both); emerging standard error by bootstrap over
  policies (30 resamples).
- **Result:** new_business relativity motor 1.110 vs 1.086 (0.8 SE), buildings 1.059 vs 1.037 (0.5 SE),
  contents 1.077 vs 0.983 (1.5 SE). **No line differs by more than two standard errors; the emerging values
  are kept (no change from p2_v1).** The raw gaps (e.g. motor 1.17 age-standardised vs 1.36–1.43) were
  portfolio mix, explained by the other rating factors.
- **Note:** renewal_count is 0 for every new-business row, so part of the new-business effect sits in its 0 level;
  the comparison is like for like (same structure in both markets), but the total new-business loading for the
  report must combine both factors.

"""

E12_REJUDGED = """### E12 re-judged under the Oct 24 tail rule — C adopted [notebook 23_part2_flood_rule]
- Reading a (all perils, as on Oct 23) reproduced exactly: A 0.662 / 1.660, C 0.514 / 0.767.
- Reading b (modelled part, the rule above): A 0.742 / 1.884; B 0.521 / 1.839 (fails); C 0.926 / 0.783
  (passes); D 0.948 / 0.788 (passes). D² (all perils): A 0.0257, B 0.0411, C 0.0631, D 0.0433.
- **Adopted: C** (highest D² among those passing): buildings = flood GLM (12 flood-related features + Part 1's five
  flood-geography pairs, alpha 0.5 by CV inside 2023) + other-perils GLM (alpha 10) + fire at the developed rate.
  In the pipeline: `tools/patch_part2_oct24c.py` (values fixed from this notebook).
- With fire excluded, C prices the safest decile closer to cost than the baseline (0.93 vs 0.74): the Oct 23 failure
  came from the flat fire rate, not from over-pricing safe customers.
- Note: E13 found no out-of-time gain from pairs on flood frequency, but on cost C (pairs) beats D (none) by 0.020;
  the pairs may act through claim size (e.g. sum insured × flood zone).

"""


def cut_block(text, heading, stop_markers):
    """Remove the block starting at `heading` up to the first of `stop_markers` after it; return (text, block)."""
    i = text.find(heading)
    if i < 0:
        return text, ""
    ends = [text.find(m, i + len(heading)) for m in stop_markers]
    j = min(e for e in ends if e >= 0)
    return text[:i] + text[j:], text[i:j].rstrip() + "\n\n"


REG = "## Assumptions register"
STOPS = ["\n### ", "\nStatus: **verified**", "\n## "]
s, fix = cut_block(s, "### Part 1 correction: relative premium", STOPS)
s, e12 = cut_block(s, "### E12: buildings flood (Oct 23 evening)", STOPS)
s, rule = cut_block(s, "### Rule change: tail condition with flat-rated parts", STOPS)
assert fix and e12 and rule, "one of the three blocks was not found"

# the register heading must be followed directly by its status line
r = s.find(REG)
line_end = s.find("\n", r)
s = s[:line_end + 1] + s[line_end + 1:].lstrip("\n").lstrip(" \n")

# Oct 23 blocks go before "### Submission p2_v1" (Rule 1 only if missing)
k = s.find("### Submission p2_v1")
assert k >= 0, "'### Submission p2_v1' not found"
add23 = ("" if "### Rule 1 applied" in s else RULE1) + fix + e12
s = s[:k] + add23 + s[k:]

# Oct 24 section goes just before the register
r = s.find(REG)
head24 = "## 2026-10-24 — Tail rule for flat-rated parts; E12 re-judged\n\n"
before = s[:r].rstrip("\n") + "\n\n"
assert "E12 re-judged under the Oct 24" not in s
s = before + head24 + rule + E12_REJUDGED + s[r:]

d.write_text(s)
for h in ["### Rule 1 applied", "### Part 1 correction", "### E12: buildings flood", "### E9-P2", "### E13",
          "### Submission p2_v1", "## 2026-10-24", "### Rule change", "### E12 re-judged", REG, "Status: **verified**"]:
    print(f"{s.find(h):7d}  {h}")
