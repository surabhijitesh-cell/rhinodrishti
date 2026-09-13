"""
IOD registry — the four OSINT collection centres, their faultline watch-lists,
and named-user assignments. See memory/plans/iod-scoping-plan.md for the full
design (this file implements the "Faultline mapping table" and "User -> IOD
mapping" sections verbatim).

Every faultline id below was verified against the current faultline_seed.py
registry before being written here — no new faultlines needed.
"""

IOD_1 = "IOD-1"
IOD_4 = "IOD-4"
IOD_5 = "IOD-5"
IOD_CIJ = "IOD-CIJ"

ALL_IODS = [IOD_1, IOD_4, IOD_5, IOD_CIJ]

# Shared Assam faultline set — IOD-4 and IOD-5 both watch the SAME 10 ids.
# A faultline's score is objective ground truth; copies would double scoring
# cost and let the two drift. Do not duplicate.
_ASSAM_FAULTLINES = [
    "asm_identity", "asm_communalism", "asm_sub_nationalism", "asm_land",
    "asm_misinformation", "asm_electoral", "asm_insurgency_influence",
    "asm_insurgency", "asm_economic_environment", "asm_bodoland",
]

_TRIPURA_FAULTLINES = [
    "tri_ethnic", "tri_demographic", "tri_land", "tri_cultural",
    "tri_regionalism", "tri_communal_conversion",
]

_MIZORAM_FAULTLINES = [
    "miz_refugee", "miz_zo_solidarity", "miz_lingua_franca", "miz_border",
    "miz_bru", "miz_drugs", "miz_ethnic_triad",
]

_NAGALAND_FAULTLINES = [
    "nag_border", "nag_church", "nag_extortion", "nag_identity",
    "nag_peace", "nag_youth",
]

_MANIPUR_FAULTLINES = [
    "man_arms", "man_ethnic", "man_idp", "man_internet", "man_religious",
    "man_territorial",
]

_NORTH_BENGAL_FAULTLINES = [
    "nbn_disparity", "nbn_separatism", "nbn_political_violence",
    "nbn_communal", "nbn_immigration", "nbn_disinformation", "nbn_chinese",
    "nbn_siliguri",
]

_BANGLADESH_FAULTLINES_CIJ = [
    "bgd_foundational", "bgd_media", "bgd_radicalization", "bgd_minority",
    "bgd_deepfakes", "bgd_anti_india", "bgd_election", "bgd_pakistan",
    "bgd_china", "bgd_foreign_influence",
]

# IOD -> faultline watch-list. IOD-1 has no explicit list: it is the
# fallback and sees everything (today's behavior, unchanged).
IOD_FAULTLINE_WATCHLIST: dict[str, list[str]] = {
    IOD_4: (
        _ASSAM_FAULTLINES + _TRIPURA_FAULTLINES + _MIZORAM_FAULTLINES
        + _NAGALAND_FAULTLINES + _MANIPUR_FAULTLINES
    ),
    IOD_5: _NORTH_BENGAL_FAULTLINES + _ASSAM_FAULTLINES,
    IOD_CIJ: _BANGLADESH_FAULTLINES_CIJ,
}

# Named user -> IOD. Any user not listed here defaults to IOD-1 (see
# resolve_user_iod below) — no explicit assignment needed for existing or
# future users outside these four centres.
USER_IOD_ASSIGNMENTS: dict[str, str] = {
    "iod4_1": IOD_4, "iod4_gs": IOD_4,
    "iod5_1": IOD_5, "iod5_gs": IOD_5,
    "cij_1": IOD_CIJ, "cij_2": IOD_CIJ, "cij_3": IOD_CIJ, "iodc_1": IOD_CIJ,
}


def resolve_user_iod(username: str) -> str:
    """A user with no explicit assignment falls back to IOD-1 — today's
    unfiltered, all-67-faultline view."""
    return USER_IOD_ASSIGNMENTS.get(username, IOD_1)


def get_iod_faultline_ids(iod: str) -> list[str] | None:
    """None means "no filter" (IOD-1: see everything)."""
    return IOD_FAULTLINE_WATCHLIST.get(iod)
