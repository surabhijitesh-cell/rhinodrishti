"""
periodic_report_config.py — Tunable configuration for the periodic
(monthly + fortnightly) strategic brief generators.

All thresholds for the auto-generated "Commander's Attention Required"
section live here, along with the commander-designated priority lists for
the RAS Sub-PAOI locations and NER Lines of Communication infrastructure.
Nothing in this file is used by the Custom Brief Generator (report agent).
"""

# ── Commander's Attention Required — anomaly detection thresholds ─────────────
ATTENTION_CONFIG = {
    # Non-PAOI faultline whose |score delta| over the period meets this → flag
    "faultline_delta_threshold": 15.0,
    # State Stability Index |score change| vs previous period meets this → flag
    "stability_delta_threshold": 20,
    # Threat-category item count >= spike_ratio × mean of trailing periods → flag
    "category_spike_ratio": 2.0,
    # …but only when the current count is at least this (ignore tiny bases)
    "category_spike_min_count": 10,
    # How many trailing periods form the category baseline
    "category_baseline_periods": 3,
    # Max attention items rendered in the section
    "max_items": 4,
    # Min attention items before the section renders at all (0 = always render)
    "min_items": 1,
}

# ── RAS Sub-PAOI — commander-designated rear-area locations ───────────────────
# Spelling variants included so keyword matching catches common renderings.
RAS_LOCATIONS = [
    "Narangi", "Narengi",
    "Jorhat",
    "Misamari", "Missamari",
    "Likabali", "Lekabali",
    "Panitola",
    "Masimpur", "Mashimpur",
    "Shillong",
]

# ── NER Lines of Communication — commander-designated priority infrastructure ─
# Items matching these are surfaced in P3 Critical Developments even at low
# volume. Highways listed with and without hyphen; rail terms cover the
# Northeast Frontier Railway network including branch lines.
LOC_PRIORITY_HIGHWAYS = [
    "NH-27", "NH 27", "NH27",
    "NH-15", "NH 15", "NH15",
    "NH-17", "NH 17", "NH17",
    "NH-2", "NH 2", "NH2",
    "NH-6", "NH 6", "NH6",
]
LOC_PRIORITY_RAIL = [
    "Northeast Frontier Railway", "NFR", "NF Railway",
    "railway line", "rail line", "railway track", "rail track",
    "railway bridge", "rail bridge", "railway station",
    "Lumding", "Badarpur", "Rangiya", "Katihar",  # major NFR divisions
    "broad gauge", "rail connectivity",
]
LOC_PRIORITY_KEYWORDS = LOC_PRIORITY_HIGHWAYS + LOC_PRIORITY_RAIL
