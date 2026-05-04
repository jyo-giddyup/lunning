# nil-predictor fairness audit

_Generated 2026-05-04T03:55:24+00:00 · n=5000 · seed=99 · artifacts=/tmp/nil-artifacts-prod_

Budgets: DP ≤ 0.05, EO ≤ 0.1. Methodology: lunning- `predictions.fairness` (ISO/IEC TR 24027:2021).

Protected attributes are derived from the synthetic data generator. `Power-4` = `{SEC, Big_Ten, ACC, Big_12}`. `Women's` = `{womens_basketball, womens_soccer, softball}` only — `gymnastics` and `volleyball` are excluded because the generator doesn't tag gender for those sports.

**This audit reports, it does not gate.** It is generated on demand and committed for visibility. CI enforcement is a separate follow-up.

## `drafted`

### by Power-4 vs other

| Group | n | base rate | selection | TPR | FPR | accuracy |
|---|---:|---:|---:|---:|---:|---:|
| non-Power-4 | 2329 | 0.166 | 0.176 | 0.628 | 0.085 | 0.867 |
| Power-4 | 2671 | 0.173 | 0.185 | 0.671 | 0.083 | 0.875 |

- Demographic-parity gap: **0.009** (PASS vs budget 0.05)
- Equalized-odds gap: **0.043** (PASS vs budget 0.1)

### by Men's vs Women's sport

| Group | n | base rate | selection | TPR | FPR | accuracy |
|---|---:|---:|---:|---:|---:|---:|
| men's / mixed | 3716 | 0.228 | 0.243 | 0.651 | 0.122 | 0.826 |
| women's | 1284 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |

- Demographic-parity gap: **0.243** (FAIL vs budget 0.05)
- Equalized-odds gap: **0.651** (FAIL vs budget 0.1)
- ⚠️ **Structural caveat**: one group has base rate 0 in the data (no positive labels exist for it). EO/DP gaps measure a label imbalance the model cannot remove and should not be read as bias.

## `portal`

### by Power-4 vs other

| Group | n | base rate | selection | TPR | FPR | accuracy |
|---|---:|---:|---:|---:|---:|---:|
| non-Power-4 | 2329 | 0.168 | 0.000 | 0.000 | 0.001 | 0.832 |
| Power-4 | 2671 | 0.168 | 0.000 | 0.002 | 0.000 | 0.832 |

- Demographic-parity gap: **0.000** (PASS vs budget 0.05)
- Equalized-odds gap: **0.002** (PASS vs budget 0.1)

### by Men's vs Women's sport

| Group | n | base rate | selection | TPR | FPR | accuracy |
|---|---:|---:|---:|---:|---:|---:|
| men's / mixed | 3716 | 0.167 | 0.001 | 0.002 | 0.000 | 0.833 |
| women's | 1284 | 0.171 | 0.000 | 0.000 | 0.000 | 0.829 |

- Demographic-parity gap: **0.001** (PASS vs budget 0.05)
- Equalized-odds gap: **0.002** (PASS vs budget 0.1)

---

To regenerate: `python scripts/fairness_audit.py --artifacts /tmp/nil-artifacts-prod`
