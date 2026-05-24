"""Agentic workflows for the NIL predictor.

Background agents that monitor watchlisted athletes, re-run predictions
on a schedule, and surface alerts when predictions change significantly.

Gated by NIL_ENABLE_AGENTS=true. When disabled, the router and scheduler
are no-ops so the rest of the service is unaffected.
"""
