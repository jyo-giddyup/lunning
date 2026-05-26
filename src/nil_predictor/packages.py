"""Syncofy package catalog — single source of truth for service offerings.

Every package definition includes pricing, Stripe metadata, and contract
fields so the checkout and contract APIs can auto-fill without hardcoding.
"""
from __future__ import annotations

import os
from typing import Any


PACKAGES: dict[str, dict[str, Any]] = {
    "explorer": {
        "slug": "explorer",
        "name": "Explorer",
        "price": 0,
        "currency": "usd",
        "display_price": "Free",
        "cadence": "forever",
        "mode": "free",
        "tier": "kol_free",
        "stripe_price_env": None,
        "tagline": "Get started with KOL intelligence — no credit card required.",
        "features": [
            "Top 100 KOL browser",
            "Basic KPS scores",
            "Limited to hematology-oncology",
        ],
        "contract_fields": {
            "service_type": "Free Tier",
            "deliverable": "Platform access — Explorer tier (read-only KOL browser)",
            "sla_response": "Best effort",
            "term": "Unlimited",
        },
    },
    "pro": {
        "slug": "pro",
        "name": "Individual Pro",
        "price": 9900,
        "currency": "usd",
        "display_price": "$99",
        "cadence": "month",
        "mode": "subscription",
        "tier": "paid",
        "stripe_price_env": "STRIPE_PRICE_PRO",
        "tagline": "For independent Medical Affairs professionals.",
        "features": [
            "Full KOL search across 112,000+ physicians",
            "KPS scoring across 7 weighted dimensions",
            "AI-drafted pre-call profile briefs",
            "Basic conversational chat with KOL context",
            "50 chat queries per month",
            "Signal detection alerts (FDA, trials, conferences)",
        ],
        "contract_fields": {
            "service_type": "SaaS Subscription",
            "deliverable": "Platform access — Individual Pro tier",
            "sla_response": "48 hours",
            "term": "Monthly, auto-renewing",
        },
    },
    "small_team": {
        "slug": "small_team",
        "name": "Small Team",
        "price": 49900,
        "currency": "usd",
        "display_price": "$499",
        "cadence": "month",
        "mode": "subscription",
        "tier": "paid",
        "stripe_price_env": "STRIPE_PRICE_SMALL_TEAM",
        "tagline": "For Medical Affairs teams up to 10 seats.",
        "features": [
            "Everything in Individual Pro",
            "Shared KOL lists and saved territories",
            "Territory heat maps with team rollups",
            "500 chat queries per month",
            "Priority email support",
            "Team-level signal feed and analytics",
        ],
        "contract_fields": {
            "service_type": "SaaS Subscription",
            "deliverable": "Platform access — Small Team tier (up to 10 seats)",
            "sla_response": "24 hours",
            "term": "Monthly, auto-renewing",
        },
    },
    "msl_brief": {
        "slug": "msl_brief",
        "name": "MSL Brief",
        "price": 29500,
        "currency": "usd",
        "display_price": "$295",
        "cadence": "physician",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_MSL_BRIEF",
        "tagline": "Per-physician deep-dive brief for MSL field engagement.",
        "features": [
            "NPI-verified credentialing + practice profile",
            "Career trajectory and research focus mapping",
            "Publication portfolio + key paper extraction with sponsor relevance",
            "MSL talking points + engagement recommendation",
            "CMS Open Payments + competitive entanglement + FMV benchmark",
            "PDF deliverable in 2 business days",
        ],
        "contract_fields": {
            "service_type": "One-Time Deliverable",
            "deliverable": "MSL Brief — per-physician intelligence report (2-page PDF)",
            "sla_response": "2 business days",
            "term": "One-time",
            "compliance": "STRIDE-ready, PhRMA Code, Sunshine Act aware",
        },
    },
    "toc_map": {
        "slug": "toc_map",
        "name": "TOC Map",
        "price": 79500,
        "currency": "usd",
        "display_price": "$795",
        "cadence": "institution",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_TOC_MAP",
        "tagline": "Total Office Call map — every provider, APP, and key role at a target institution.",
        "features": [
            "Every physician + APP at the institution, NPI-verified",
            "Network chain analysis — warm-intro paths between KOLs",
            "Research infrastructure (registries, IRB, trial PIs)",
            "Pharmacy, fellowship, and support-staff roster",
            "Fellow-to-Founder Prediction Score (FFPS) for emerging KOLs",
            "Engagement priority matrix (T1/T2/T3) with suggested cadence",
            "PDF deliverable in 3 business days",
        ],
        "contract_fields": {
            "service_type": "One-Time Deliverable",
            "deliverable": "TOC Map — institutional KOL mapping report (multi-page PDF)",
            "sla_response": "3 business days",
            "term": "One-time",
            "compliance": "NPI-verified, PhRMA Code, Sunshine Act aware",
        },
    },
    "engagement_intel": {
        "slug": "engagement_intel",
        "name": "Engagement Intelligence",
        "price": 295000,
        "currency": "usd",
        "display_price": "$2,950",
        "cadence": "sponsor",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_ENGAGEMENT_INTEL",
        "tagline": "Sponsor-level field intelligence brief — Med Affairs + Commercial in one pass.",
        "features": [
            "Rising Investigator Radar (FFPS algorithm, 5-10 yr forward lookahead)",
            "Advisory Board pipeline + automated compliance (EOC / FMV / Sunshine Act)",
            "Competitor Pipeline Intelligence (ClinicalTrials.gov site-overlap)",
            "MSL Field Intelligence (scientific exchange capture, KOL sentiment)",
            "ATC Network + Market Access (MS-DRG, NTAP, payer denials)",
            "Speaker Programs + NCCN / Congress Calendar",
            "8-page PDF prepared in 5 business days",
        ],
        "contract_fields": {
            "service_type": "One-Time Deliverable",
            "deliverable": "Engagement Intelligence — sponsor-level field intelligence (8-page PDF)",
            "sla_response": "5 business days",
            "term": "One-time",
            "compliance": "FMV certified, PhRMA Code, OIG, Sunshine Act, Med Affairs / Commercial firewall",
        },
    },
    "report": {
        "slug": "report",
        "name": "Trial Brief",
        "price": 250000,
        "currency": "usd",
        "display_price": "$2,500",
        "cadence": "one-time",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_REPORT",
        "tagline": "Bespoke 5-KOL intelligence package for site selection or advisory boards.",
        "features": [
            "Bespoke 5-KOL intelligence report",
            "KPS rankings + engagement windows",
            "Industry payment + grant disclosure summary",
            "PDF + structured data export",
            "Delivered in 5 business days",
        ],
        "contract_fields": {
            "service_type": "One-Time Deliverable",
            "deliverable": "Trial Brief — 5-KOL intelligence report (PDF + data export)",
            "sla_response": "5 business days",
            "term": "One-time",
        },
    },
    "advisory_board_design": {
        "slug": "advisory_board_design",
        "name": "Advisory Board Design",
        "price": 495000,
        "currency": "usd",
        "display_price": "$4,950",
        "cadence": "board",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_ADVISORY_BOARD",
        "tagline": "End-to-end advisory board planning — KOL selection, compliance, and logistics.",
        "features": [
            "KOL selection with diversity scoring and COI screening",
            "FMV rate card benchmarking (2026 Syncofy Rate Card)",
            "EOC template with pre-populated agenda",
            "Sunshine Act / PhRMA Code pre-filing checklist",
            "Invitation package with per-KOL personalization",
            "Post-board insights summary and engagement recommendations",
        ],
        "contract_fields": {
            "service_type": "Professional Services",
            "deliverable": "Advisory Board Design — KOL selection, compliance, invitation package",
            "sla_response": "7 business days",
            "term": "One-time per advisory board",
            "compliance": "FMV certified, EOC, OIG, Sunshine Act",
        },
    },
    "signal_feed": {
        "slug": "signal_feed",
        "name": "Signal Feed",
        "price": 199900,
        "currency": "usd",
        "display_price": "$1,999",
        "cadence": "quarter",
        "mode": "subscription",
        "tier": "paid",
        "stripe_price_env": "STRIPE_PRICE_SIGNAL_FEED",
        "tagline": "Real-time engagement signals — FDA, trials, conferences, publications.",
        "features": [
            "Automated FDA approval + label change alerts",
            "ClinicalTrials.gov readout + enrollment tracking",
            "Conference monitoring (ASCO, ASH, SITC, AACR)",
            "KOL publication alerts with sponsor-pipeline relevance",
            "Weekly digest + real-time webhook option",
            "Customizable watchlist by NPI, institution, or TA",
        ],
        "contract_fields": {
            "service_type": "Data Subscription",
            "deliverable": "Signal Feed — real-time engagement signal delivery",
            "sla_response": "24 hours (alert latency < 4 hours)",
            "term": "Quarterly, auto-renewing",
        },
    },
    "competitive_landscape": {
        "slug": "competitive_landscape",
        "name": "Competitive Landscape Report",
        "price": 395000,
        "currency": "usd",
        "display_price": "$3,950",
        "cadence": "indication",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_COMPETITIVE_LANDSCAPE",
        "tagline": "Per-indication competitive intelligence — pipeline, KOL share, trial site overlap.",
        "features": [
            "Competitive pipeline mapping",
            "KOL share-of-voice analysis",
            "Trial site overlap and exclusive recruitment",
            "Payer landscape + formulary positioning",
            "NCCN guideline positioning",
            "10-page PDF + data export",
        ],
        "contract_fields": {
            "service_type": "One-Time Deliverable",
            "deliverable": "Competitive Landscape Report — per-indication intelligence (10-page PDF + data)",
            "sla_response": "7 business days",
            "term": "One-time",
        },
    },
    "drug_target_analysis": {
        "slug": "drug_target_analysis",
        "name": "Drug Target Analysis",
        "price": 750000,
        "currency": "usd",
        "display_price": "$7,500",
        "cadence": "target",
        "mode": "payment",
        "tier": "report_access",
        "stripe_price_env": "STRIPE_PRICE_DRUG_TARGET",
        "tagline": "AI-powered drug discovery intelligence — target validation, compounds, cohorts.",
        "features": [
            "Target to disease association mapping (Open Targets)",
            "Compound bioactivity analysis (ChEMBL)",
            "Patient cohort expression profiling (UCSC Xena)",
            "BioNeMo structure prediction + docking",
            "Tractability + safety signal assessment",
            "KOL network overlay for the target",
        ],
        "contract_fields": {
            "service_type": "Research Services",
            "deliverable": "Drug Target Analysis — target validation + compound profiling + cohort data",
            "sla_response": "10 business days",
            "term": "One-time per target",
        },
    },
    "enterprise": {
        "slug": "enterprise",
        "name": "Enterprise Platform",
        "price": None,
        "currency": "usd",
        "display_price": "From $150K",
        "cadence": "year",
        "mode": "contract",
        "tier": "enterprise",
        "stripe_price_env": None,
        "tagline": "Full platform deployment with dedicated infrastructure, SSO, and compliance coverage.",
        "features": [
            "Full platform access — all products included",
            "SSO / SAML integration",
            "Dedicated infrastructure (single-tenant option)",
            "Custom data feeds + CRM integration",
            "Compliance coverage (SOC 2, HIPAA BAA)",
            "Dedicated CSM + quarterly business reviews",
            "Unlimited users and queries",
        ],
        "contract_fields": {
            "service_type": "Enterprise Contract",
            "deliverable": "Enterprise Platform — full deployment per Statement of Work",
            "sla_response": "Per SLA agreement (99.9% uptime)",
            "term": "Annual, custom",
        },
    },
}


def resolve_package(slug: str) -> dict[str, Any] | None:
    return PACKAGES.get(slug)


def resolve_stripe_price(slug: str) -> str | None:
    pkg = PACKAGES.get(slug)
    if not pkg or not pkg.get("stripe_price_env"):
        return None
    return os.environ.get(pkg["stripe_price_env"])


def package_for_checkout(slug: str) -> dict[str, Any] | None:
    pkg = resolve_package(slug)
    if not pkg:
        return None
    price_id = resolve_stripe_price(slug)
    if not price_id and pkg["mode"] not in ("contract", "free"):
        return None
    return {**pkg, "price_id": price_id or ""}


def contract_fields_for_package(
    slug: str, overrides: dict[str, str] | None = None
) -> dict[str, Any] | None:
    pkg = resolve_package(slug)
    if not pkg:
        return None
    fields = {
        "package_name": pkg["name"],
        "package_slug": pkg["slug"],
        "price_display": pkg["display_price"],
        "cadence": pkg["cadence"],
        "currency": pkg["currency"],
        "features": pkg["features"],
        **pkg["contract_fields"],
    }
    if overrides:
        fields.update(overrides)
    return fields


def list_self_serve_packages() -> list[dict[str, Any]]:
    return [
        p for p in PACKAGES.values()
        if p["mode"] in ("subscription", "payment", "free")
    ]
