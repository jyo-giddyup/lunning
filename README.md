# lunning

Prediction-model work for this org follows a fair, efficient, and compliant
baseline. The reference implementation lives in `jyo-giddyup/lunning-` on the
`claude/fair-efficient-models-g9gC3` branch.

## Standards baseline

Any prediction model added to this repo MUST:

| Concern    | Standard                | Requirement                                              |
| ---------- | ----------------------- | -------------------------------------------------------- |
| Fairness   | ISO/IEC TR 24027:2021   | Report demographic-parity + equalized-odds gaps in CI    |
| Risk       | ISO/IEC 23894:2023      | Maintain a risk register in the model card               |
| Governance | ISO/IEC 42001:2023      | Ship a model card; emit audit-log events on eval/predict |
| Trust      | ISO/IEC TR 24028:2020   | Document intended use + limitations                      |
| Data qual. | ISO/IEC 25012:2008      | Declared schema, provenance, quality dimensions          |
| Security   | ISO/IEC 27001:2022      | Append-only audit trail, no PII in logs                  |
| Privacy    | ISO/IEC 27701:2019      | DPIA required before any real-personal-data use          |

Fairness budgets are enforced as a CI gate — a build fails when the gap
exceeds the model card's declared threshold.
