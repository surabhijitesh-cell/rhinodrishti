"""
priority_areas_seed.py — Commander's Priority Areas of Interest (PAOI).

A curated overlay on top of the 66 faultlines. Each PAOI is a high-level
commander concern that aggregates one or more faultlines (and/or keyword pulls)
and gets RED treatment in briefs + daily-brief news tags.

PAOIs (commander-defined):
  P1 India-Bangladesh Border
  P2 Jamaat-e-Islami spread + radicalisation
  P3 NER Lines of Communication        (keyword pull — no faultline backing;
                                        NH-27/15/17/2/6 + NFR rail priority)
  Rear Area Internal Security Scan (RAS) — parent grouping of two sub-PAOIs:
    P4 Meghalaya Internal Security      (commander's location)
    P5 RAS Locations                    (Narangi, Jorhat, Misamari, Likabali,
                                         Panitola, Masimpur, Shillong)
  P6 Tribal Dynamics — Meghalaya

Each PAOI:
  id, rank, name, description
  geography           — regions/districts in scope
  actors_of_interest  — named actors to watch
  linked_faultline_ids— existing faultlines that feed this PAOI
  keyword_pull        — optional {keywords[], regions[], exclude_keywords[]}
                        for faultline-less topics (P3 LOC, RAS locations) —
                        matches articles directly
  priority_keywords   — optional commander-designated terms that boost an
                        article into Critical Developments even at low volume
  parent_group        — optional display grouping (RAS sub-PAOIs share one)
  watch_geography     — secondary watch areas (monitored, not primary)
  color               — "red" (all PAOIs render red by default)

Seeding also tags faultlines.priority_area_ids[] so any faultline in a PAOI
can be RED-flagged everywhere (daily brief chips, faultline cards, alerts).
"""
from datetime import datetime, timezone

from periodic_report_config import LOC_PRIORITY_KEYWORDS, RAS_LOCATIONS

RAS_PARENT_GROUP = "Rear Area Internal Security Scan"


PRIORITY_AREAS = [
    # ─── P1 — India-Bangladesh Border ─────────────────────────────────────────
    {
        "id": "P1_india_bangladesh_border",
        "rank": 1,
        "name": "India-Bangladesh Border",
        "description": (
            "Border security along the India-Bangladesh frontier. PRIMARY focus: "
            "North Bengal (Jalpaiguri, Siliguri Corridor, Cooch Behar), Assam, "
            "Meghalaya, Tripura, Mizoram. Watch BGB, ISI, and foreign collaborators. "
            "Infiltration, illegal trade routes (arms/drugs), border-security gaps."
        ),
        "geography": [
            "North Bengal", "Siliguri Corridor", "Jalpaiguri", "Cooch Behar",
            "Assam", "Meghalaya", "Tripura", "Mizoram",
        ],
        "actors_of_interest": ["BGB", "ISI", "foreign collaborators", "smuggling networks"],
        "linked_faultline_ids": [
            "nbn_siliguri", "nbn_immigration", "nbn_disinformation",
            "meg_border", "meg_indigenous",
            "tri_demographic", "tri_ethnic",
            "miz_ethnic_triad", "miz_refugee", "miz_drugs",
            "asm_identity",
            "bgd_border_disinformation", "bgd_anti_india", "bgd_cyber",
        ],
        "keyword_pull": {
            "keywords": [
                "BGB", "border outpost", "BoP", "infiltration", "illegal crossing",
                "smuggling", "cattle smuggling", "arms smuggling border", "fencing",
                "BSF border", "Indo-Bangladesh border", "border haat", "trans-border",
                "border gap", "unfenced border", "riverine border",
            ],
            "regions": ["North Bengal", "Assam", "Meghalaya", "Tripura", "Mizoram", "Bangladesh"],
        },
        "watch_geography": ["West Bengal Muslim-heavy districts"],
        "color": "red",
    },

    # ─── P2 — Jamaat-e-Islami spread + radicalisation ─────────────────────────
    {
        "id": "P2_jamaat_radicalisation",
        "rank": 2,
        "name": "Jamaat-e-Islami Spread & Radicalisation",
        "description": (
            "Jamaat-e-Islami (JeI) consolidation in Bangladesh and catalysing of "
            "radicalisation among the Muslim population — especially in the military "
            "and India-bordering areas. JeI won 68 seats in BD border regions, "
            "mirroring Muslim-heavy WB border districts. Cross-border JeI activity, "
            "illegal arms/drug trade routes, military penetration. PRIMARY border "
            "concern remains NER-adjacent (N.Bengal, Assam, Meghalaya, Tripura, "
            "Mizoram); WB border districts are a monitored secondary."
        ),
        "geography": [
            "Bangladesh", "Bangladesh border divisions",
            "North Bengal", "Assam", "Meghalaya", "Tripura", "Mizoram",
        ],
        "actors_of_interest": [
            "Jamaat-e-Islami", "JeI", "Hefazat-e-Islam", "ISI",
            "Bangladesh military", "DGFI", "radical clerics",
        ],
        "linked_faultline_ids": [
            "bgd_radicalization", "bgd_military_radical", "bgd_foundational",
            "bgd_pakistan", "bgd_minority", "bgd_anti_india",
        ],
        "keyword_pull": {
            "keywords": [
                "Jamaat", "Jamaat-e-Islami", "JeI", "Hefazat", "Islamist Bangladesh",
                "radicalisation", "radicalization", "madrasah", "madrasa funding",
                "infiltration", "Murshidabad", "Malda", "Dinajpur", "Nadia",
                "24 Parganas", "minority affairs funding", "military radical",
                "cross-border terror", "arms route", "drug route",
            ],
            "regions": ["Bangladesh", "North Bengal", "Assam", "Meghalaya", "Tripura", "Mizoram"],
        },
        # WB Muslim-heavy border districts from commander's map (68 JeI seats mirror these)
        "watch_geography": [
            "Uttar Dinajpur", "Dakshin Dinajpur", "Malda", "Murshidabad",
            "Birbhum", "Nadia", "North 24 Parganas", "South 24 Parganas",
            "Purba Bardhaman",
        ],
        "intel_notes": (
            "JeI won 68 seats in BD border regions (radical Islamist outfit). "
            "WB Minority Affairs + Madrasah funding rose 1111% (2011-12 -> Rs 5,713.61 cr). "
            "Maximum infiltration in green (Muslim-heavy) WB border districts."
        ),
        "color": "red",
    },

    # ─── P3 — NER Lines of Communication (keyword pull, entire NER) ────────────
    {
        "id": "P3_ner_lines_of_communication",
        "rank": 3,
        "name": "NER Lines of Communication",
        "description": (
            "Status of major lines of communication across the entire NER — "
            "national highways, state roads, railway lines, and the Siliguri "
            "Corridor. Any disruption from civil unrest, blockade, bandh, natural "
            "calamity, or insurgency is of concern, anywhere in NER. "
            "Commander-designated priority infrastructure: NH-27, NH-15, NH-17, "
            "NH-2, NH-6 and all major Northeast Frontier Railway lines including "
            "branch lines."
        ),
        "geography": [
            "Assam", "Meghalaya", "Mizoram", "Manipur", "Nagaland",
            "Tripura", "Arunachal Pradesh", "North Bengal", "Siliguri Corridor",
        ],
        "actors_of_interest": ["insurgent groups", "agitating CSOs", "blockade organisers"],
        "linked_faultline_ids": [],  # keyword-driven, no faultline backing per commander
        "keyword_pull": {
            "keywords": [
                "highway", "national highway", "NH-", "NH ", "NH2", "NH37", "NH6",
                "railway", "rail line", "train", "track", "bridge", "bridge collapse",
                "road block", "roadblock", "blockade", "economic blockade", "bandh",
                "landslide", "flood road", "washed away", "Siliguri corridor",
                "chicken neck", "highway blockade", "rail blockade", "convoy",
                "supply line", "logistics disruption",
            ],
            "regions": [
                "Assam", "Meghalaya", "Mizoram", "Manipur", "Nagaland",
                "Tripura", "Arunachal Pradesh", "North Bengal",
            ],
        },
        "priority_keywords": LOC_PRIORITY_KEYWORDS,
        "watch_geography": [],
        "color": "red",
    },

    # ─── P4 — Meghalaya Internal Security (RAS sub-PAOI) ──────────────────────
    {
        "id": "P4_meghalaya_internal_security",
        "rank": 4,
        "name": "Meghalaya Internal Security",
        "description": (
            "Internal security of Meghalaya (commander's location). Inter-tribal "
            "tensions (Khasi-Garo-Jaintia), District Autonomous Councils (KHADC, "
            "GHADC, JHADC), tribal vs non-tribal issues, crime, and cross-border "
            "smuggling."
        ),
        "geography": ["Meghalaya"],
        "actors_of_interest": [
            "KSU", "HNLC", "FKJGP", "KHADC", "GHADC", "JHADC",
            "Khasi", "Garo", "Jaintia", "non-tribal settlers",
        ],
        "linked_faultline_ids": [
            "meg_tribe_conflict", "meg_indigenous", "meg_ethnic_dynamics",
            "meg_border", "meg_religion_politics", "meg_environment",
        ],
        "keyword_pull": {
            "keywords": [
                "Meghalaya", "Khasi", "Garo", "Jaintia", "KSU", "HNLC", "FKJGP",
                "KHADC", "GHADC", "JHADC", "autonomous district council", "ADC Meghalaya",
                "ILP Meghalaya", "non-tribal", "dkhar", "Shillong", "Tura",
                "inner line permit", "tribal land Meghalaya", "smuggling Meghalaya",
            ],
            "regions": ["Meghalaya"],
        },
        "parent_group": RAS_PARENT_GROUP,
        "watch_geography": [],
        "color": "red",
    },

    # ─── P5 — RAS Locations (RAS sub-PAOI, location-based only) ───────────────
    {
        "id": "P5_ras_locations",
        "rank": 5,
        "name": "RAS Locations",
        "description": (
            "Location-based security status of commander-designated rear-area "
            "stations: Narangi, Jorhat, Misamari, Likabali, Panitola, Masimpur, "
            "and Shillong. Tracks any intelligence tagged to these locations "
            "regardless of threat category, even at low volume. Highway and "
            "railway disruption is excluded — that remains with NER Lines of "
            "Communication (P3)."
        ),
        "geography": [
            "Narangi", "Jorhat", "Misamari", "Likabali",
            "Panitola", "Masimpur", "Shillong",
            "Assam", "Arunachal Pradesh", "Meghalaya",
        ],
        "actors_of_interest": [
            "insurgent groups", "radical networks", "criminal syndicates",
            "agitating CSOs",
        ],
        "linked_faultline_ids": [],  # location keyword-driven, no faultline backing
        "keyword_pull": {
            "keywords": RAS_LOCATIONS,
            "regions": ["Assam", "Arunachal Pradesh", "Meghalaya"],
            # LoC coverage stays with P3 — keep highway/rail stories out of RAS
            "exclude_keywords": [
                "highway", "national highway", "NH-", "railway", "rail line",
                "road block", "roadblock", "blockade",
            ],
        },
        "priority_keywords": RAS_LOCATIONS,
        "parent_group": RAS_PARENT_GROUP,
        "watch_geography": [],
        "color": "red",
    },

    # ─── P6 — Tribal Dynamics — Meghalaya ────────────────────────────────────
    {
        "id": "P5_meghalaya_tribal_dynamics",
        "rank": 6,
        "name": "Tribal Dynamics — Meghalaya",
        "description": (
            "Intra-tribal and tribal-vs-non-tribal tensions within Meghalaya. "
            "Three primary axes: (1) Khasi-Garo-Jaintia inter-tribal land and "
            "administrative boundary disputes; (2) tribal versus non-tribal settler "
            "conflict — ILP agitation, dkhar evictions, KSU-led actions in Shillong, "
            "Tura, Jowai; (3) traditional authority structures (Dorbar Shnong, KHADC, "
            "GHADC, JHADC) under stress from political mobilisation, coal mining "
            "grievances, and religious identity politics. Secondary: HNLC, GNLA, and "
            "ANVC armed group activity with tribal community backing."
        ),
        "geography": [
            "East Khasi Hills", "West Khasi Hills", "Ri Bhoi",
            "South West Khasi Hills", "Eastern West Khasi Hills",
            "East Jaintia Hills", "West Jaintia Hills",
            "East Garo Hills", "West Garo Hills", "South Garo Hills",
            "North Garo Hills", "Shillong",
        ],
        "actors_of_interest": [
            "KSU", "HNLC", "GNLA", "ANVC", "FKJGP",
            "KHADC", "GHADC", "JHADC",
            "Dorbar Shnong", "Nokmas", "non-tribal settler associations",
        ],
        "linked_faultline_ids": [
            "meg_tribe_conflict", "meg_indigenous", "meg_ethnic_dynamics",
            "meg_religion_politics", "meg_environment", "meg_border",
        ],
        "keyword_pull": {
            "keywords": [
                "Khasi", "Garo", "Jaintia", "Pnar", "KSU", "HNLC", "GNLA", "ANVC",
                "FKJGP", "KHADC", "GHADC", "JHADC", "autonomous district council Meghalaya",
                "ILP Meghalaya", "inner line permit Meghalaya", "dkhar",
                "non-tribal Meghalaya", "tribal land Meghalaya", "Dorbar Shnong",
                "Syiem", "Nokma", "inter-tribal Meghalaya", "eviction Meghalaya",
                "settler Meghalaya", "Khasi Students Union", "Garo National Liberation Army",
                "Seng Khasi", "traditional religion Meghalaya", "Laitsohpliah",
                "rat-hole mining Jaintia", "coal mining Meghalaya",
                "tribal council Meghalaya", "Khasi Hills Autonomous",
            ],
            "regions": ["Meghalaya"],
        },
        "watch_geography": [
            "Ri Bhoi", "Byrnihat", "Balpakram", "Jowai",
            "Khliehriat", "Phulbari", "Tura",
        ],
        "color": "red",
    },
]


async def seed_priority_areas(db) -> dict:
    """
    Idempotent seed of PAOIs + tag faultlines with priority_area_ids[].
    Returns {priority_areas_upserted, faultlines_tagged}.
    """
    now = datetime.now(timezone.utc).isoformat()

    # 1. Upsert priority areas
    pa_upserted = 0
    for pa in PRIORITY_AREAS:
        doc = {**pa, "enabled": True, "updated_at": now}
        result = await db.priority_areas.update_one(
            {"id": pa["id"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if result.upserted_id or result.modified_count:
            pa_upserted += 1

    # 2. Tag faultlines with the PAOIs that reference them.
    #    First clear all tags, then re-apply (idempotent + handles removals).
    await db.faultlines.update_many({}, {"$set": {"priority_area_ids": []}})

    faultline_to_paois: dict[str, list] = {}
    for pa in PRIORITY_AREAS:
        for fl_id in pa.get("linked_faultline_ids", []):
            faultline_to_paois.setdefault(fl_id, []).append(pa["id"])

    tagged = 0
    for fl_id, paoi_ids in faultline_to_paois.items():
        result = await db.faultlines.update_one(
            {"id": fl_id},
            {"$set": {"priority_area_ids": paoi_ids, "updated_at": now}},
        )
        if result.matched_count:
            tagged += 1

    return {
        "priority_areas_upserted": pa_upserted,
        "total_priority_areas": len(PRIORITY_AREAS),
        "faultlines_tagged": tagged,
    }


def get_priority_faultline_ids() -> set:
    """All faultline ids that belong to any PAOI (for RED-flagging)."""
    ids = set()
    for pa in PRIORITY_AREAS:
        ids.update(pa.get("linked_faultline_ids", []))
    return ids
