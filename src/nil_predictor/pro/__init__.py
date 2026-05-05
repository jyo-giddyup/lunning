"""Pro-stage prediction targets.

Sibling submodule to the amateur (`nil_predictor`) package per the
stage-separation rule documented in `CLAUDE.md`. Pro-stage models
predict outcomes that are only meaningful for draft-eligible athletes
(football / men's basketball / baseball in the synthetic generator).

Targets:
    pro_contract_value     first pro contract dollars            regression
    pro_career_length      expected pro years                    regression
    pro_all_star           P(all-pro/all-star within 5 yr)       binary
    agent_signed           P(top-tier agent pre-draft)           binary

The pro stage is **disjoint** from the amateur stage:
- separate package (`nil_predictor.pro`)
- separate model card (`MODEL_CARD_PRO.md`)
- separate dataset (`generate()` only emits drafted athletes)
- separate artifact root (`artifacts/pro/...`)
- separate CLI (`python -m nil_predictor.pro.train` / `predict`)

A caller composing both stages must do so explicitly — chain on
`drafted=True` from the amateur predictor before invoking pro.
"""
__version__ = "0.1.0"
