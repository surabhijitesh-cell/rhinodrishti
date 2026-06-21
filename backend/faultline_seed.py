"""
faultline_seed.py — Faultline ontology seed data for RhinoDrishti.

60+ faultlines across 8 regions (Manipur, Meghalaya, Assam, Tripura,
Mizoram, Nagaland, North Bengal, Bangladesh).

Each faultline has:
  - id: unique slug
  - state: region name matching intelligence_items.regions[] values
  - name: human-readable name
  - description: short description
  - keywords: terms to match in article title/summary/tags
  - tags: existing intelligence_items tag values that signal this faultline
  - signal_buckets: existing signal_bucket values that signal this faultline
  - linked_faultlines: [{id, weight}] — cross-faultline influence graph
  - active: bool
"""

from datetime import datetime, timezone

# Maps faultline state name → intelligence_items regions[] values
STATE_TO_REGIONS = {
    "Manipur": ["Manipur"],
    "Assam": ["Assam"],
    "Meghalaya": ["Meghalaya"],
    "Mizoram": ["Mizoram"],
    "Nagaland": ["Nagaland"],
    "Tripura": ["Tripura"],
    "North Bengal": ["West Bengal / Siliguri Corridor"],
    "Bangladesh": ["Bangladesh"],
    # Cross-state faultlines (LOC, NER-wide)
    "NER": [
        "Assam", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
        "Tripura", "West Bengal / Siliguri Corridor", "Arunachal Pradesh",
    ],
}

FAULTLINES = [
    # ─── MANIPUR ───────────────────────────────────────────────────────────────
    {
        "id": "man_ethnic",
        "state": "Manipur",
        "name": "Meitei-Kuki-Naga ethnic faultlines",
        "description": "Ethnic conflict between Meitei, Kuki-Zo, and Naga communities in Manipur",
        "keywords": [
            "Meitei", "Kuki", "Kuki-Zo", "Zomi", "Naga", "ethnic conflict",
            "tribal", "hill tribe", "valley", "Imphal", "Churachandpur",
            "Kangpokpi", "ITLF", "Kuki-Zo", "ethnic violence", "communal clash",
        ],
        "tags": ["Ethnic / Tribal Tension", "Civil Unrest", "Insurgency / Militancy"],
        "signal_buckets": ["conflict_escalation", "insurgency", "political_instability"],
        "loc_focus": ["NH-37", "NH-2", "Imphal corridor", "Jiribam", "Moreh border"],
        "linked_faultlines": [
            {"id": "man_arms", "weight": 0.5},
            {"id": "man_idp", "weight": 0.6},
            {"id": "man_internet", "weight": 0.4},
            {"id": "man_religious", "weight": 0.3},
            {"id": "nag_peace", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "man_territorial",
        "state": "Manipur",
        "name": "Territorial claims and hill-valley governance dispute",
        "description": "Dispute over Inner Line Permit, hill district autonomy, and hill-valley political power",
        "keywords": [
            "hill district", "valley district", "Inner Line Permit", "ILP",
            "inner line", "hill council", "ADC", "autonomous district",
            "territorial", "governance dispute", "scheduled tribe Manipur",
            "HMAR", "Tribal Solidarity", "protection demand",
        ],
        "tags": ["Political Developments", "Ethnic / Tribal Tension", "Civil Unrest"],
        "signal_buckets": ["political_instability", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "man_ethnic", "weight": 0.5},
            {"id": "man_idp", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "man_idp",
        "state": "Manipur",
        "name": "Internally displaced persons and relief politics",
        "description": "IDP camps, relief fund distribution disputes, and political manipulation of displaced persons",
        "keywords": [
            "displaced", "IDP", "relief camp", "refugee camp", "shelter",
            "relief fund", "rehabilitation", "homeless", "evacuation Manipur",
            "internally displaced", "flood relief Manipur",
        ],
        "tags": ["Civil Unrest", "Ethnic / Tribal Tension"],
        "signal_buckets": ["humanitarian_stress", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "man_ethnic", "weight": 0.4},
            {"id": "man_territorial", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "man_arms",
        "state": "Manipur",
        "name": "Arms circulation and militia activity",
        "description": "Looted arms from police armouries, militia formation, and armed group activity",
        "keywords": [
            "arms", "weapons", "looted arms", "stolen weapons", "armoury",
            "militia", "SoO", "suspension of operations", "UNLF", "PLA Manipur",
            "Meitei Leepun", "Arambai Tenggol", "gun", "ammunition",
            "armed group Manipur", "village defence force",
        ],
        "tags": ["Insurgency / Militancy", "Arms Smuggling", "Military Movement"],
        "signal_buckets": ["insurgency", "extremism", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "man_ethnic", "weight": 0.3},
            {"id": "nag_extortion", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "man_religious",
        "state": "Manipur",
        "name": "Religious polarization and identity narratives",
        "description": "Hindu-Christian religious divide amplifying ethnic conflict in Manipur",
        "keywords": [
            "religious", "Christian Manipur", "Hindu Manipur", "church attack",
            "temple attack Manipur", "communal Manipur", "religious polarization",
            "identity narrative Manipur", "conversion Manipur",
        ],
        "tags": ["Ethnic / Tribal Tension", "Civil Unrest", "Radicalization Indicator"],
        "signal_buckets": ["political_instability", "extremism"],
        "linked_faultlines": [
            {"id": "man_ethnic", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "man_internet",
        "state": "Manipur",
        "name": "Internet shutdowns, information control, and rumor propagation",
        "description": "State-imposed internet bans and resulting information vacuum filled by rumors",
        "keywords": [
            "internet shutdown Manipur", "internet ban Manipur", "internet suspended Manipur",
            "disinformation Manipur", "fake news Manipur", "rumor Manipur",
            "information blackout", "social media ban Manipur", "communication ban",
        ],
        "tags": ["Information Warfare / Narrative", "Civil Unrest"],
        "signal_buckets": ["political_instability", "external_influence"],
        "linked_faultlines": [
            {"id": "man_ethnic", "weight": 0.3},
        ],
        "active": True,
    },

    # ─── MEGHALAYA ─────────────────────────────────────────────────────────────
    {
        "id": "meg_radicalisation",
        "state": "Meghalaya",
        "name": "Radicalisation and external threat",
        "description": "Radicalization of youth and external extremist influence in Meghalaya",
        "keywords": [
            "radicalization Meghalaya", "radicalisation Meghalaya", "extremist Meghalaya",
            "jihadist Meghalaya", "terror module Meghalaya", "sleeper cell Meghalaya",
            "external threat Meghalaya", "recruitment Meghalaya",
        ],
        "tags": ["Radicalization Indicator", "Foreign Influence (China/Pakistan/USA)"],
        "signal_buckets": ["extremism", "external_influence"],
        "linked_faultlines": [
            {"id": "meg_isis", "weight": 0.6},
            {"id": "meg_digital_influence", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "meg_indigenous",
        "state": "Meghalaya",
        "name": "Indigenous vs immigrant sentiment",
        "description": "Tensions between indigenous tribal communities and non-tribal settlers in Meghalaya",
        "keywords": [
            "indigenous Meghalaya", "immigrant Meghalaya", "outsider Meghalaya",
            "settler Meghalaya", "dkhars", "non-tribal Meghalaya", "sons of soil",
            "foreigner Meghalaya", "demographic Meghalaya", "migration Meghalaya",
        ],
        "tags": ["Illegal Immigration", "Ethnic / Tribal Tension", "Civil Unrest"],
        "signal_buckets": ["migration_refugees", "political_instability"],
        "linked_faultlines": [
            {"id": "meg_tribe_conflict", "weight": 0.3},
            {"id": "meg_border", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "meg_tribe_conflict",
        "state": "Meghalaya",
        "name": "Tribe vs tribe conflict",
        "description": "Inter-tribal conflict between Khasi, Garo, and Jaintia communities",
        "keywords": [
            "Khasi", "Garo", "Jaintia", "tribal conflict Meghalaya",
            "inter-tribal Meghalaya", "HNLC", "KSU", "GHADC", "KHADC",
            "tribal tension Meghalaya", "Khasi Hills",
        ],
        "tags": ["Ethnic / Tribal Tension", "Civil Unrest"],
        "signal_buckets": ["conflict_escalation", "political_instability"],
        "linked_faultlines": [
            {"id": "meg_indigenous", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "meg_religion_politics",
        "state": "Meghalaya",
        "name": "Religion and political identity",
        "description": "Faith-based political identity and religious influence on governance",
        "keywords": [
            "religious identity Meghalaya", "Christian Meghalaya", "tribal religion",
            "faith-based politics", "church Meghalaya", "pastor politics",
            "missionary Meghalaya", "faith identity Meghalaya",
        ],
        "tags": ["Political Developments", "Ethnic / Tribal Tension"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "meg_tribe_conflict", "weight": 0.2},
        ],
        "active": True,
    },
    {
        "id": "meg_border",
        "state": "Meghalaya",
        "name": "Border disagreement and resource control",
        "description": "Assam-Meghalaya border dispute and control over border resources",
        "keywords": [
            "border dispute Meghalaya", "Assam Meghalaya border", "boundary Meghalaya",
            "resource Meghalaya", "mining rights Meghalaya", "land dispute Meghalaya",
            "border village Meghalaya", "border tension Meghalaya",
        ],
        "tags": ["Border Security", "Political Developments", "Civil Unrest"],
        "signal_buckets": ["border_security", "political_instability"],
        "linked_faultlines": [
            {"id": "meg_indigenous", "weight": 0.3},
            {"id": "asm_identity", "weight": 0.2},
        ],
        "active": True,
    },
    {
        "id": "meg_environment",
        "state": "Meghalaya",
        "name": "Environment and mining politics",
        "description": "Illegal coal mining, environmental damage, and political economy of extraction",
        "keywords": [
            "coal mine Meghalaya", "mining Meghalaya", "rat-hole mining",
            "illegal mining Meghalaya", "river pollution Meghalaya",
            "deforestation Meghalaya", "NGT Meghalaya", "limestone mining",
            "environmental damage Meghalaya",
        ],
        "tags": ["Political Developments", "Civil Unrest"],
        "signal_buckets": ["political_instability", "trade_logistics_disruption"],
        "linked_faultlines": [],
        "active": True,
    },
    {
        "id": "meg_digital_influence",
        "state": "Meghalaya",
        "name": "Foreign influence in digital space",
        "description": "Social media manipulation, foreign narrative operations, and digital radicalization",
        "keywords": [
            "digital influence Meghalaya", "social media manipulation Meghalaya",
            "Chinese influence Meghalaya", "narrative operation Meghalaya",
            "propaganda Meghalaya", "fake account", "bot network Meghalaya",
            "information operation Meghalaya",
        ],
        "tags": ["Information Warfare / Narrative", "Foreign Influence (China/Pakistan/USA)"],
        "signal_buckets": ["external_influence"],
        "linked_faultlines": [
            {"id": "meg_radicalisation", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "meg_isis",
        "state": "Meghalaya",
        "name": "ISIS influence and radicalization",
        "description": "IS/ISIS-linked radicalization and recruitment networks in Meghalaya",
        "keywords": [
            "ISIS Meghalaya", "IS Meghalaya", "Islamic State Meghalaya",
            "ISKP Meghalaya", "jihadist Meghalaya", "ISIS recruitment",
            "terror module", "IS influence Northeast",
        ],
        "tags": ["Radicalization Indicator", "Foreign Influence (China/Pakistan/USA)"],
        "signal_buckets": ["extremism", "external_influence"],
        "linked_faultlines": [
            {"id": "meg_radicalisation", "weight": 0.7},
        ],
        "active": True,
    },
    {
        "id": "meg_ethnic_dynamics",
        "state": "Meghalaya",
        "name": "Inter ethnic group dynamics",
        "description": "Cross-community dynamics between all tribal and non-tribal groups in Meghalaya",
        "keywords": [
            "inter-ethnic Meghalaya", "community tension Meghalaya",
            "tribal relations Meghalaya", "Khasi Garo", "ethnic relations",
            "tribal council Meghalaya", "inter-community tension",
        ],
        "tags": ["Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["political_instability", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "meg_tribe_conflict", "weight": 0.5},
            {"id": "meg_indigenous", "weight": 0.4},
        ],
        "active": True,
    },

    # ─── ASSAM ─────────────────────────────────────────────────────────────────
    {
        "id": "asm_identity",
        "state": "Assam",
        "name": "Identity threat and demography inversion",
        "description": "Indigenous Assamese identity threat from migration and demographic change",
        "keywords": [
            "indigenous Assam", "Assamese identity", "Bengali Assam", "migrant Assam",
            "demography Assam", "demographic change Assam", "NRC Assam",
            "CAA Assam", "foreigner Assam", "D-voter", "doubtful voter",
            "influx Assam", "illegal immigration Assam",
        ],
        "tags": ["Illegal Immigration", "Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["migration_refugees", "political_instability"],
        "linked_faultlines": [
            {"id": "asm_communalism", "weight": 0.4},
            {"id": "asm_electoral", "weight": 0.5},
            {"id": "asm_land", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "asm_communalism",
        "state": "Assam",
        "name": "Religious communalism",
        "description": "Hindu-Muslim communal tensions, riots, and religious polarization",
        "keywords": [
            "Hindu Muslim Assam", "communal Assam", "religious tension Assam",
            "mosque Assam", "temple Assam", "madrasa Assam", "minority Assam",
            "communal violence Assam", "riot Assam", "communal harmony",
        ],
        "tags": ["Civil Unrest", "Political Developments", "Ethnic / Tribal Tension"],
        "signal_buckets": ["conflict_escalation", "political_instability"],
        "linked_faultlines": [
            {"id": "asm_identity", "weight": 0.4},
            {"id": "bgd_radicalization", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "asm_sub_nationalism",
        "state": "Assam",
        "name": "Ethnic and regional sub nationalism",
        "description": "Assamese sub-nationalist movements and regional autonomy demands",
        "keywords": [
            "sub-nationalism Assam", "Axomiya", "Assamese pride",
            "regional identity Assam", "AASU", "autonomy Assam",
            "self-determination Assam", "regional party Assam",
        ],
        "tags": ["Political Developments", "Civil Unrest", "Ethnic / Tribal Tension"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "asm_identity", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "asm_land",
        "state": "Assam",
        "name": "Land ownership and protection",
        "description": "Land encroachment, evictions, tribal land alienation, and char land disputes",
        "keywords": [
            "land grabbing Assam", "land encroachment Assam", "tribal land Assam",
            "forest land Assam", "land transfer Assam", "eviction Assam",
            "land rights Assam", "encroachment Assam", "char land", "char area",
        ],
        "tags": ["Civil Unrest", "Political Developments", "Ethnic / Tribal Tension"],
        "signal_buckets": ["political_instability", "humanitarian_stress"],
        "linked_faultlines": [
            {"id": "asm_identity", "weight": 0.3},
            {"id": "asm_bodoland", "weight": 0.2},
        ],
        "active": True,
    },
    {
        "id": "asm_misinformation",
        "state": "Assam",
        "name": "Misinformation targeting youth",
        "description": "Fake job offers, drug trafficking, and digital radicalization targeting Assam youth",
        "keywords": [
            "fake job Assam", "employment scam Assam", "drug Assam",
            "narco Assam", "youth radicalization Assam", "fake news youth Assam",
            "drug trafficking Assam", "brown sugar Assam", "social media scam",
        ],
        "tags": ["Information Warfare / Narrative", "Drug Trafficking", "Radicalization Indicator"],
        "signal_buckets": ["extremism", "political_instability", "smuggling"],
        "linked_faultlines": [],
        "active": True,
    },
    {
        "id": "asm_electoral",
        "state": "Assam",
        "name": "Electoral and demography anxiety",
        "description": "Voter list manipulation fears, delimitation concerns, and demographic anxiety around elections",
        "keywords": [
            "election Assam", "voter list Assam", "NRC election", "foreigner voter",
            "electoral roll Assam", "census Assam", "population Assam",
            "demographic anxiety", "delimitation Assam",
        ],
        "tags": ["Political Developments", "Illegal Immigration"],
        "signal_buckets": ["political_instability", "migration_refugees"],
        "linked_faultlines": [
            {"id": "asm_identity", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "asm_insurgency_influence",
        "state": "Assam",
        "name": "Insurgency groups seeking influence",
        "description": "Dormant insurgent groups using politics and threats to regain prominence",
        "keywords": [
            "ULFA influence", "NDFB influence", "insurgent politics Assam",
            "militant political influence", "underground Assam political",
            "banned group influence", "peace talk Assam", "surrender Assam",
        ],
        "tags": ["Insurgency / Militancy", "Political Developments"],
        "signal_buckets": ["insurgency", "political_instability"],
        "linked_faultlines": [
            {"id": "asm_insurgency", "weight": 0.5},
        ],
        "active": True,
    },
    {
        "id": "asm_insurgency",
        "state": "Assam",
        "name": "Insurgency and militancy",
        "description": "Active insurgent attacks, IED blasts, extortion, and abductions in Assam",
        "keywords": [
            "ULFA-I", "ULFA ATF", "NDFB-S", "militant attack Assam",
            "IED Assam", "blast Assam", "abduction Assam",
            "extortion Assam", "insurgency Assam", "armed group Assam",
        ],
        "tags": ["Insurgency / Militancy", "Arms Smuggling", "Civil Unrest"],
        "signal_buckets": ["insurgency", "conflict_escalation", "extremism"],
        "linked_faultlines": [
            {"id": "asm_insurgency_influence", "weight": 0.5},
            {"id": "asm_bodoland", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "asm_economic_environment",
        "state": "Assam",
        "name": "Economic, environmental, and disaster fault lines",
        "description": "Floods, Brahmaputra erosion, dam disputes, and economic distress in Assam",
        "keywords": [
            "flood Assam", "erosion Assam", "disaster Assam", "Brahmaputra",
            "dam Assam", "economic distress Assam", "unemployment Assam",
            "coal mine accident Assam",
        ],
        "tags": ["Floods / Climate Impact", "Civil Unrest"],
        "signal_buckets": ["humanitarian_stress", "trade_logistics_disruption"],
        "loc_focus": ["Brahmaputra", "Barak", "NH-27", "NH-37", "Bogibeel", "Saraighat"],
        "linked_faultlines": [],
        "active": True,
    },
    {
        "id": "asm_bodoland",
        "state": "Assam",
        "name": "Bodoland influence and state politics",
        "description": "Bodo Territorial Region politics, BTC elections, and Bodo influence on Assam governance",
        "keywords": [
            "Bodoland", "BTC", "Bodo", "ABSU", "NDFB", "BTR",
            "Bodo Territorial", "Kokrajhar", "Chirang", "Udalguri",
            "Bodo political", "Bodoland election",
        ],
        "tags": ["Political Developments", "Ethnic / Tribal Tension", "Insurgency / Militancy"],
        "signal_buckets": ["political_instability", "insurgency"],
        "linked_faultlines": [
            {"id": "asm_insurgency", "weight": 0.3},
            {"id": "asm_identity", "weight": 0.2},
        ],
        "active": True,
    },

    # ─── TRIPURA ───────────────────────────────────────────────────────────────
    {
        "id": "tri_ethnic",
        "state": "Tripura",
        "name": "Ethnic divide: Indigenous tribes vs Bengali settlers",
        "description": "Conflict between indigenous Tripuri/Borok tribes and Bengali settler majority",
        "keywords": [
            "tribal Tripura", "Bengali settler Tripura", "indigenous Tripura",
            "Tripuri", "Borok", "TIPRA", "Greater Tipraland", "Twipra",
            "settler conflict Tripura", "ATTF", "NLFT", "ethnic Tripura",
        ],
        "tags": ["Ethnic / Tribal Tension", "Civil Unrest", "Political Developments"],
        "signal_buckets": ["conflict_escalation", "political_instability"],
        "loc_focus": ["NH-8", "Agartala border", "Sonamura", "Sabroom", "Gomati border"],
        "linked_faultlines": [
            {"id": "tri_demographic", "weight": 0.5},
            {"id": "tri_land", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "tri_demographic",
        "state": "Tripura",
        "name": "Demographic inversion",
        "description": "Tribal communities becoming a minority in their own state due to Bengali migration",
        "keywords": [
            "demographic Tripura", "population change Tripura", "Bengali majority",
            "tribal minority Tripura", "demographic change Tripura",
            "migrant population Tripura",
        ],
        "tags": ["Illegal Immigration", "Ethnic / Tribal Tension"],
        "signal_buckets": ["migration_refugees", "political_instability"],
        "linked_faultlines": [
            {"id": "tri_ethnic", "weight": 0.5},
        ],
        "active": True,
    },
    {
        "id": "tri_land",
        "state": "Tripura",
        "name": "Land alienation and economic discontent",
        "description": "Tribal land seizures, economic marginalization, and unemployment-driven discontent",
        "keywords": [
            "land alienation Tripura", "tribal land Tripura", "land encroachment Tripura",
            "economic distress Tripura", "unemployment Tripura", "land rights tribal Tripura",
        ],
        "tags": ["Civil Unrest", "Political Developments", "Ethnic / Tribal Tension"],
        "signal_buckets": ["humanitarian_stress", "political_instability"],
        "linked_faultlines": [
            {"id": "tri_ethnic", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "tri_cultural",
        "state": "Tripura",
        "name": "Cultural identity and Kokborok language",
        "description": "Kokborok script debate and cultural erasure of Tripuri identity",
        "keywords": [
            "Kokborok", "Tripuri language", "script Tripura", "cultural identity Tripura",
            "Borok language", "language rights Tripura", "cultural erasure Tripura",
        ],
        "tags": ["Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "tri_ethnic", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "tri_regionalism",
        "state": "Tripura",
        "name": "Rise of regionalism",
        "description": "TIPRA Motha and Greater Tipraland demand for separate tribal homeland",
        "keywords": [
            "TIPRA Motha", "regionalism Tripura", "Greater Tipraland",
            "separate state Tripura", "autonomy Tripura", "Pradyot Kishore",
            "TTAADC", "Tipraland", "tribal autonomy Tripura",
        ],
        "tags": ["Political Developments", "Civil Unrest"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "tri_ethnic", "weight": 0.4},
            {"id": "tri_cultural", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "tri_communal_conversion",
        "state": "Tripura",
        "name": "Communal narratives on missionary conversions",
        "description": "Anti-conversion narratives targeting Christian missionaries and communal polarization",
        "keywords": [
            "conversion Tripura", "missionary Tripura", "forced conversion Tripura",
            "Christian conversion Tripura", "communal Tripura", "anti-conversion Tripura",
        ],
        "tags": ["Ethnic / Tribal Tension", "Civil Unrest", "Radicalization Indicator"],
        "signal_buckets": ["political_instability", "extremism"],
        "linked_faultlines": [
            {"id": "tri_ethnic", "weight": 0.3},
        ],
        "active": True,
    },

    # ─── MIZORAM ───────────────────────────────────────────────────────────────
    {
        "id": "miz_refugee",
        "state": "Mizoram",
        "name": "Refugee pressure and inter-tribal tension",
        "description": "Myanmar Chin refugee influx straining Mizoram resources and causing tribal tensions",
        "keywords": [
            "Myanmar refugee Mizoram", "Chin refugee", "refugee Mizoram",
            "displaced Myanmar Mizoram", "inter-tribal Mizoram", "refugee camp Mizoram",
            "Chin Mizo", "refugee pressure Mizoram",
        ],
        "tags": ["Illegal Immigration", "Myanmar Instability", "Ethnic / Tribal Tension"],
        "signal_buckets": ["migration_refugees", "humanitarian_stress"],
        "linked_faultlines": [
            {"id": "miz_ethnic_triad", "weight": 0.5},
            {"id": "miz_zo_solidarity", "weight": 0.3},
            {"id": "man_ethnic", "weight": 0.2},
        ],
        "active": True,
    },
    {
        "id": "miz_zo_solidarity",
        "state": "Mizoram",
        "name": "Zo ethnic solidarity vs outsider narrative",
        "description": "Pan-Zo ethnic solidarity movement and tensions with non-Zo communities",
        "keywords": [
            "Zo", "Zomi", "Mizo solidarity", "Chin Mizo solidarity",
            "ethnic solidarity Mizo", "outsider narrative Mizoram",
            "non-Mizo", "Zo unification", "Zo reunification",
        ],
        "tags": ["Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "miz_refugee", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "miz_lingua_franca",
        "state": "Mizoram",
        "name": "Mizo Lingua Franca resistance",
        "description": "Mizo language preservation against foreign dialects and cultural homogenization",
        "keywords": [
            "Mizo language", "Mizo lingua franca", "dialect Mizoram",
            "Chakma language", "language rights Mizoram", "cultural identity Mizoram",
            "language preservation Mizo",
        ],
        "tags": ["Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [],
        "active": True,
    },
    {
        "id": "miz_border",
        "state": "Mizoram",
        "name": "Assam-Mizoram border dispute",
        "description": "Active Assam-Mizoram boundary dispute with periodic violent clashes",
        "keywords": [
            "Assam Mizoram border", "Kolasib Cachar", "border dispute Mizoram",
            "border tension Mizoram", "boundary Mizoram Assam", "Vairengte",
            "Lailapur border",
        ],
        "tags": ["Border Security", "Civil Unrest", "Political Developments"],
        "signal_buckets": ["border_security", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "meg_border", "weight": 0.2},
        ],
        "active": True,
    },
    {
        "id": "miz_bru",
        "state": "Mizoram",
        "name": "Bru-Mizo conflict",
        "description": "Protracted Bru-Reang displacement and resettlement tensions in Mizoram",
        "keywords": [
            "Bru Mizoram", "Reang Mizoram", "Bru Mizo", "Bru settlement",
            "Bru repatriation", "Bru relief", "displaced Bru", "Bru rehabilitation",
        ],
        "tags": ["Ethnic / Tribal Tension", "Civil Unrest", "Illegal Immigration"],
        "signal_buckets": ["conflict_escalation", "humanitarian_stress", "migration_refugees"],
        "linked_faultlines": [],
        "active": True,
    },
    {
        "id": "miz_drugs",
        "state": "Mizoram",
        "name": "Drug influx",
        "description": "Myanmar-origin drug trafficking through Mizoram and local drug crisis",
        "keywords": [
            "drug Mizoram", "heroin Mizoram", "drug trafficking Mizoram",
            "narcotics Mizoram", "drug route Mizoram", "Myanmar drug Mizoram",
            "methamphetamine Mizoram", "yaba Mizoram", "brown sugar Mizoram",
        ],
        "tags": ["Drug Trafficking", "Myanmar Instability", "Arms Smuggling"],
        "signal_buckets": ["smuggling", "extremism"],
        "linked_faultlines": [
            {"id": "miz_ethnic_triad", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "miz_ethnic_triad",
        "state": "Mizoram",
        "name": "Ethnic triad (Myanmar-Bangladesh-Mizoram)",
        "description": "Cross-border ethnic network spanning Myanmar, Bangladesh, and Mizoram enabling smuggling and irregular migration",
        "keywords": [
            "Myanmar Bangladesh Mizoram", "tri-border Mizoram", "cross-border Mizoram",
            "illegal immigration Mizoram", "cross-border network Mizoram",
            "ethnic triad",
        ],
        "tags": ["Cross-border Movement", "Myanmar Instability", "Bangladesh Internal Dynamics"],
        "signal_buckets": ["migration_refugees", "external_influence", "smuggling"],
        "linked_faultlines": [
            {"id": "miz_refugee", "weight": 0.5},
            {"id": "miz_drugs", "weight": 0.4},
        ],
        "active": True,
    },

    # ─── NAGALAND ──────────────────────────────────────────────────────────────
    {
        "id": "nag_identity",
        "state": "Nagaland",
        "name": "Naga identity and tribal unity vs fragmentation",
        "description": "Fragmentation of Naga political unity along tribal and factional lines",
        "keywords": [
            "Naga identity", "Naga unity", "tribal fragmentation Nagaland",
            "Naga tribes", "Angami", "Ao Naga", "Sumi", "Lotha", "Tangkhul",
            "inter-tribal Naga", "Naga political", "Naga tribe conflict",
        ],
        "tags": ["Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["political_instability", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "nag_peace", "weight": 0.5},
        ],
        "active": True,
    },
    {
        "id": "nag_peace",
        "state": "Nagaland",
        "name": "Peace process fragility and ceasefire trust deficit",
        "description": "Fragile Naga peace process, NSCN factionalism, and ceasefire violations",
        "keywords": [
            "Naga peace", "NSCN", "NSCN-IM", "NSCN-K", "NSCN-R",
            "Framework Agreement", "ceasefire Nagaland", "peace talks Naga",
            "Naga solution", "Naga political problem", "NNPG",
            "peace process Nagaland", "NSCN faction",
        ],
        "tags": ["Insurgency / Militancy", "Political Developments"],
        "signal_buckets": ["insurgency", "political_instability"],
        "linked_faultlines": [
            {"id": "nag_identity", "weight": 0.4},
            {"id": "nag_extortion", "weight": 0.5},
            {"id": "man_ethnic", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "nag_extortion",
        "state": "Nagaland",
        "name": "Extortion, arms networks, and underground influence",
        "description": "Naga underground groups running parallel governance through extortion and arms",
        "keywords": [
            "extortion Nagaland", "Naga underground", "parallel government Nagaland",
            "taxation Nagaland", "NSCN extortion", "underground Naga",
            "arms network Nagaland", "weapons Nagaland",
        ],
        "tags": ["Insurgency / Militancy", "Arms Smuggling", "Civil Unrest"],
        "signal_buckets": ["insurgency", "extremism", "conflict_escalation"],
        "linked_faultlines": [
            {"id": "nag_peace", "weight": 0.5},
            {"id": "man_arms", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "nag_border",
        "state": "Nagaland",
        "name": "Border and cross-border movement narratives",
        "description": "Nagaland-Myanmar border porosity, cross-border movement, and border district vulnerabilities",
        "keywords": [
            "Naga border", "Nagaland Myanmar border", "cross-border Nagaland",
            "Mon district Nagaland", "Tuensang", "border movement Nagaland",
            "Nagaland Myanmar",
        ],
        "tags": ["Border Security", "Cross-border Movement", "Myanmar Instability"],
        "signal_buckets": ["border_security", "migration_refugees"],
        "linked_faultlines": [
            {"id": "nag_extortion", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "nag_youth",
        "state": "Nagaland",
        "name": "Youth unemployment and social frustration",
        "description": "Educated youth unemployment driving social frustration and susceptibility to radicalization",
        "keywords": [
            "youth unemployment Nagaland", "social frustration Nagaland",
            "educated unemployment Nagaland", "youth Nagaland",
            "economic opportunity Nagaland",
        ],
        "tags": ["Civil Unrest", "Political Developments"],
        "signal_buckets": ["humanitarian_stress", "political_instability"],
        "linked_faultlines": [
            {"id": "nag_extortion", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "nag_church",
        "state": "Nagaland",
        "name": "Church, morality, and social cohesion narratives",
        "description": "Church authority in Nagaland politics, moral policing, and social cohesion",
        "keywords": [
            "church Nagaland", "Baptist church Nagaland", "Nagaland Baptist",
            "church influence Nagaland", "social cohesion Nagaland",
            "moral policing Nagaland", "Sunday liquor ban Nagaland",
            "church authority Nagaland",
        ],
        "tags": ["Political Developments", "Civil Unrest"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [],
        "active": True,
    },

    # ─── NORTH BENGAL ──────────────────────────────────────────────────────────
    {
        "id": "nbn_disparity",
        "state": "North Bengal",
        "name": "North Bengal and South Bengal disparity",
        "description": "Development, resource allocation, and political representation gap between North and South Bengal",
        "keywords": [
            "North Bengal development", "South Bengal disparity",
            "North Bengal neglect", "underdevelopment North Bengal",
            "economic inequality Bengal", "North Bengal ignored",
        ],
        "tags": ["Political Developments", "Civil Unrest"],
        "signal_buckets": ["political_instability", "humanitarian_stress"],
        "linked_faultlines": [
            {"id": "nbn_separatism", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "nbn_separatism",
        "state": "North Bengal",
        "name": "Separatist and regional identity movements",
        "description": "Gorkhaland, Kamtapur, Greater Cooch Behar, and other regional autonomy/separate state demands",
        "keywords": [
            "Gorkhaland", "Kamtapur", "Greater Cooch Behar", "Koch Rajbongshi",
            "Rajbongshi", "GNLF", "GJM", "Bodoland North Bengal",
            "separate state North Bengal", "Darjeeling statehood",
        ],
        "tags": ["Political Developments", "Civil Unrest", "Ethnic / Tribal Tension"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "nbn_disparity", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "nbn_political_violence",
        "state": "North Bengal",
        "name": "Political violence and accountability",
        "description": "Election-related violence, political murders, and booth capturing in North Bengal",
        "keywords": [
            "political violence Bengal", "TMC violence", "BJP violence Bengal",
            "political murder Bengal", "booth capture Bengal",
            "election violence Bengal", "North Bengal violence",
        ],
        "tags": ["Civil Unrest", "Political Developments"],
        "signal_buckets": ["conflict_escalation", "political_instability"],
        "linked_faultlines": [],
        "active": True,
    },
    {
        "id": "nbn_communal",
        "state": "North Bengal",
        "name": "Communal and ethnic polarisation",
        "description": "Hindu-Muslim and ethnic polarization in North Bengal districts",
        "keywords": [
            "communal North Bengal", "Hindu Muslim Bengal", "communal tension Bengal",
            "ethnic polarisation Bengal", "minority Bengal", "communal violence Bengal",
        ],
        "tags": ["Civil Unrest", "Ethnic / Tribal Tension", "Political Developments"],
        "signal_buckets": ["conflict_escalation", "political_instability"],
        "linked_faultlines": [
            {"id": "nbn_immigration", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "nbn_immigration",
        "state": "North Bengal",
        "name": "Immigration and demographic changes",
        "description": "Bangladeshi immigration driving demographic change and NRC/CAA tensions in North Bengal",
        "keywords": [
            "immigration Bengal", "Bangladeshi immigrant Bengal",
            "illegal immigration Bengal", "demographic change Bengal",
            "NRC Bengal", "CAA Bengal", "foreigner Bengal",
        ],
        "tags": ["Illegal Immigration", "Bangladesh Internal Dynamics", "Ethnic / Tribal Tension"],
        "signal_buckets": ["migration_refugees", "political_instability"],
        "linked_faultlines": [
            {"id": "nbn_communal", "weight": 0.4},
            {"id": "bgd_anti_india", "weight": 0.2},
        ],
        "active": True,
    },
    {
        "id": "nbn_disinformation",
        "state": "North Bengal",
        "name": "Border disinformation campaigns",
        "description": "Cross-border disinformation targeting North Bengal communities and Siliguri Corridor security",
        "keywords": [
            "disinformation Bengal border", "fake news Bengal", "border narrative Bengal",
            "anti-India Bengal narrative", "propaganda Bengal", "Siliguri corridor narrative",
            "border disinformation",
        ],
        "tags": ["Information Warfare / Narrative", "Border Security"],
        "signal_buckets": ["external_influence", "border_security"],
        "linked_faultlines": [
            {"id": "nbn_chinese", "weight": 0.5},
            {"id": "bgd_anti_india", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "nbn_chinese",
        "state": "North Bengal",
        "name": "Chinese influence operations",
        "description": "Chinese narrative operations, proxy influence, and strategic interest in Siliguri Corridor",
        "keywords": [
            "Chinese influence Bengal", "China North Bengal", "PLA Bengal",
            "Siliguri corridor China", "Chinese narrative Bengal",
            "digital influence Bengal Chinese", "Chinese proxy Bengal",
        ],
        "tags": ["Foreign Influence (China/Pakistan/USA)", "Information Warfare / Narrative"],
        "signal_buckets": ["external_influence"],
        "linked_faultlines": [
            {"id": "nbn_siliguri", "weight": 0.6},
            {"id": "nbn_disinformation", "weight": 0.5},
        ],
        "active": True,
    },
    {
        "id": "nbn_siliguri",
        "state": "North Bengal",
        "name": "Siliguri Corridor strategic vulnerability",
        "description": "Demographic, military, and influence threats to the strategic Siliguri Corridor",
        "keywords": [
            "Siliguri corridor", "chicken neck", "Siliguri", "corridor security",
            "strategic corridor", "Siliguri demographics", "corridor vulnerability",
            "Siliguri strategic",
        ],
        "tags": ["Border Security", "Foreign Influence (China/Pakistan/USA)", "Military Movement"],
        "signal_buckets": ["border_security", "military_movement", "external_influence"],
        "loc_focus": [
            "Siliguri Corridor", "chicken neck", "NH-10", "NH-31",
            "NJP", "New Jalpaiguri", "Jalpaiguri", "Teesta",
        ],
        "linked_faultlines": [
            {"id": "nbn_chinese", "weight": 0.6},
            {"id": "nbn_immigration", "weight": 0.3},
        ],
        "active": True,
    },

    # ─── BANGLADESH ────────────────────────────────────────────────────────────
    {
        "id": "bgd_foundational",
        "state": "Bangladesh",
        "name": "Pro-liberation vs anti-liberation foundational divide",
        "description": "Bangladesh's foundational political fault: Awami League (pro-liberation) vs BNP/Jamaat (anti-liberation)",
        "keywords": [
            "Awami League", "BNP Bangladesh", "Jamaat-e-Islami", "liberation war Bangladesh",
            "muktijoddha", "razakar", "war crimes tribunal Bangladesh",
            "Sheikh Hasina", "Khaleda Zia",
        ],
        "tags": ["Bangladesh Internal Dynamics", "Political Developments"],
        "signal_buckets": ["political_instability"],
        "linked_faultlines": [
            {"id": "bgd_election", "weight": 0.5},
            {"id": "bgd_radicalization", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_media",
        "state": "Bangladesh",
        "name": "Media suppression and narrative control",
        "description": "Government control over Bangladeshi media, journalist arrests, DSA use",
        "keywords": [
            "media Bangladesh", "journalist arrested Bangladesh",
            "press freedom Bangladesh", "Digital Security Act Bangladesh",
            "DSA Bangladesh", "media suppression Bangladesh",
            "newspaper ban Bangladesh", "reporter arrested Bangladesh",
        ],
        "tags": ["Information Warfare / Narrative", "Bangladesh Internal Dynamics"],
        "signal_buckets": ["political_instability", "external_influence"],
        "linked_faultlines": [
            {"id": "bgd_china", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_radicalization",
        "state": "Bangladesh",
        "name": "Radicalisation and Islamist narratives",
        "description": "Hefazat-e-Islam, JMB, and Islamist radicalization in Bangladesh",
        "keywords": [
            "Hefazat", "Hifazat-e-Islam", "Islamist Bangladesh", "JMB Bangladesh",
            "radicalization Bangladesh", "Islamist rally Bangladesh",
            "madrasa Bangladesh", "tablighi Bangladesh", "Islamist group Bangladesh",
        ],
        "tags": ["Radicalization Indicator", "Bangladesh Internal Dynamics", "Foreign Influence (China/Pakistan/USA)"],
        "signal_buckets": ["extremism", "political_instability"],
        "linked_faultlines": [
            {"id": "bgd_pakistan", "weight": 0.4},
            {"id": "bgd_military_radical", "weight": 0.5},
            {"id": "asm_communalism", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_minority",
        "state": "Bangladesh",
        "name": "Disinformation on minority persecution",
        "description": "Attacks on Hindu minorities in Bangladesh and information operations around them",
        "keywords": [
            "Hindu Bangladesh", "minority Bangladesh", "temple attack Bangladesh",
            "minority persecution Bangladesh", "Hindu attack Bangladesh",
            "Durga Puja attack Bangladesh", "minority violence Bangladesh",
        ],
        "tags": ["Bangladesh Internal Dynamics", "Information Warfare / Narrative", "Civil Unrest"],
        "signal_buckets": ["conflict_escalation", "political_instability"],
        "linked_faultlines": [
            {"id": "bgd_radicalization", "weight": 0.4},
            {"id": "bgd_anti_india", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_anti_india",
        "state": "Bangladesh",
        "name": "Anti-India rhetoric in Bangladeshi politics",
        "description": "State and non-state anti-India rhetoric, water disputes, and political India-bashing",
        "keywords": [
            "anti-India Bangladesh", "India Bangladesh tension",
            "India interference Bangladesh", "water dispute Bangladesh India",
            "Teesta river", "Farakka Bangladesh", "India rhetoric Bangladesh",
            "anti-India rally Bangladesh",
        ],
        "tags": ["Bangladesh Internal Dynamics", "Political Developments", "Information Warfare / Narrative"],
        "signal_buckets": ["political_instability", "external_influence"],
        "linked_faultlines": [
            {"id": "bgd_border_disinformation", "weight": 0.5},
            {"id": "nbn_disinformation", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "bgd_deepfakes",
        "state": "Bangladesh",
        "name": "AI-generated deepfakes and narrative manipulation",
        "description": "Use of synthetic media, deepfakes, and AI-generated content for political manipulation",
        "keywords": [
            "deepfake Bangladesh", "AI narrative Bangladesh", "synthetic media Bangladesh",
            "fake video Bangladesh", "AI disinformation Bangladesh",
            "deepfake India Bangladesh",
        ],
        "tags": ["Information Warfare / Narrative", "Bangladesh Internal Dynamics"],
        "signal_buckets": ["external_influence"],
        "linked_faultlines": [
            {"id": "bgd_election", "weight": 0.4},
            {"id": "bgd_media", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_election",
        "state": "Bangladesh",
        "name": "Election interference and influence operations",
        "description": "Foreign and domestic interference in Bangladeshi elections and democratic processes",
        "keywords": [
            "election Bangladesh", "vote rigging Bangladesh",
            "electoral fraud Bangladesh", "election violence Bangladesh",
            "influence operation Bangladesh", "foreign election Bangladesh",
        ],
        "tags": ["Political Developments", "Bangladesh Internal Dynamics", "Information Warfare / Narrative"],
        "signal_buckets": ["political_instability", "external_influence"],
        "linked_faultlines": [
            {"id": "bgd_foundational", "weight": 0.5},
        ],
        "active": True,
    },
    {
        "id": "bgd_pakistan",
        "state": "Bangladesh",
        "name": "Pakistani influence and proxy operations",
        "description": "ISI and Pakistani proxy networks operating in Bangladesh for destabilization",
        "keywords": [
            "Pakistan Bangladesh", "ISI Bangladesh", "Pakistani proxy Bangladesh",
            "Pakistan influence Bangladesh", "cross-border terror Bangladesh Pakistan",
            "Lashkar Bangladesh", "JeM Bangladesh",
        ],
        "tags": ["Foreign Influence (China/Pakistan/USA)", "Bangladesh Internal Dynamics", "Cross-border Movement"],
        "signal_buckets": ["external_influence", "extremism"],
        "linked_faultlines": [
            {"id": "bgd_radicalization", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "bgd_china",
        "state": "Bangladesh",
        "name": "Chinese digital infrastructure influence",
        "description": "China's growing digital and telecom infrastructure dominance in Bangladesh",
        "keywords": [
            "China Bangladesh", "Chinese investment Bangladesh", "Huawei Bangladesh",
            "BRI Bangladesh", "Chinese telecom Bangladesh",
            "digital infrastructure Bangladesh China", "Belt Road Bangladesh",
        ],
        "tags": ["Foreign Influence (China/Pakistan/USA)", "Bangladesh Internal Dynamics", "Infrastructure / Logistics"],
        "signal_buckets": ["external_influence"],
        "linked_faultlines": [
            {"id": "bgd_media", "weight": 0.3},
            {"id": "bgd_foreign_influence", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "bgd_foreign_influence",
        "state": "Bangladesh",
        "name": "Foreign influence in politics, infrastructure, and media",
        "description": "Multi-actor foreign influence (US, India, China, Pakistan) competing in Bangladesh",
        "keywords": [
            "foreign influence Bangladesh", "geopolitics Bangladesh",
            "US Bangladesh", "India China Bangladesh competition",
            "foreign funding Bangladesh NGO", "foreign interference Bangladesh",
        ],
        "tags": ["Foreign Influence (China/Pakistan/USA)", "Bangladesh Internal Dynamics", "Political Developments"],
        "signal_buckets": ["external_influence", "political_instability"],
        "linked_faultlines": [
            {"id": "bgd_china", "weight": 0.4},
            {"id": "bgd_pakistan", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_border_disinformation",
        "state": "Bangladesh",
        "name": "Disinformation on border security and incursions",
        "description": "Fake news and disinformation about BSF actions, border incursions, and killings",
        "keywords": [
            "border Bangladesh India", "BSF Bangladesh", "border firing Bangladesh",
            "border incursion Bangladesh", "BGB Bangladesh", "BSF killing Bangladesh",
            "border disinformation Bangladesh",
        ],
        "tags": ["Border Security", "Information Warfare / Narrative", "Bangladesh Internal Dynamics"],
        "signal_buckets": ["border_security", "external_influence"],
        "linked_faultlines": [
            {"id": "bgd_anti_india", "weight": 0.5},
        ],
        "active": True,
    },
    {
        "id": "bgd_cyber",
        "state": "Bangladesh",
        "name": "Cross-border cyber threats and espionage",
        "description": "State and non-state cyber attacks on Indian and Bangladeshi infrastructure",
        "keywords": [
            "cyber attack Bangladesh", "hacking Bangladesh India",
            "espionage Bangladesh", "cyber threat Bangladesh",
            "cyberattack Bangladesh", "data breach Bangladesh",
            "Bangladesh cyber espionage",
        ],
        "tags": ["Information Warfare / Narrative", "Foreign Influence (China/Pakistan/USA)"],
        "signal_buckets": ["external_influence"],
        "linked_faultlines": [
            {"id": "bgd_china", "weight": 0.3},
            {"id": "bgd_pakistan", "weight": 0.3},
        ],
        "active": True,
    },
    {
        "id": "bgd_military",
        "state": "Bangladesh",
        "name": "Military politics and intelligence coordination",
        "description": "Bangladesh military's role in politics, DGFI operations, and military-intelligence nexus",
        "keywords": [
            "Bangladesh army", "DGFI", "RAB Bangladesh", "military Bangladesh politics",
            "military radicalisation Bangladesh", "defence Bangladesh",
            "army coup Bangladesh", "Bangladesh military politics",
        ],
        "tags": ["Military Movement", "Bangladesh Internal Dynamics", "Political Developments"],
        "signal_buckets": ["military_movement", "political_instability"],
        "linked_faultlines": [
            {"id": "bgd_military_radical", "weight": 0.4},
        ],
        "active": True,
    },
    {
        "id": "bgd_military_radical",
        "state": "Bangladesh",
        "name": "Military interlinkages with radical groups",
        "description": "Penetration of Bangladesh military and intelligence by Islamist radical networks",
        "keywords": [
            "military radical Bangladesh", "army Islamist Bangladesh",
            "DGFI Islamist", "military Hefazat Bangladesh",
            "radical military Bangladesh", "army extremist Bangladesh",
        ],
        "tags": ["Radicalization Indicator", "Bangladesh Internal Dynamics", "Military Movement"],
        "signal_buckets": ["extremism", "military_movement"],
        "linked_faultlines": [
            {"id": "bgd_radicalization", "weight": 0.5},
            {"id": "bgd_military", "weight": 0.4},
        ],
        "active": True,
    },

    # ─── NER LINES OF COMMUNICATION (cross-state) ─────────────────────────────
    {
        "id": "ner_loc",
        "state": "NER",
        "name": "NER Lines of Communication",
        "description": (
            "Threats to national highways, railways, bridges, rivers, and logistics "
            "routes across Northeast India that affect security force movement and "
            "rear-area operations. Covers NH network, key rail trunks, "
            "Brahmaputra/Barak crossings, and the Siliguri Corridor."
        ),
        "keywords": [
            "NH-27", "NH-8", "NH-2", "NH-37", "NH-13", "NH-6", "NH-10", "NH-31",
            "rail roko NER", "railway disruption northeast", "bridge collapse northeast",
            "road blockade northeast", "highway blocked northeast",
            "Brahmaputra ferry", "Barak bridge", "Siliguri corridor LOC",
            "chicken neck blockade", "flood closed NH", "landslide NH northeast",
            "sabotage railway NER", "Kaladan corridor", "Imphal corridor",
            "Jiribam route", "Moreh road", "logistics northeast",
        ],
        "tags": [
            "Infrastructure / Logistics Disruption", "Border Security",
            "Civil Unrest", "Floods / Climate Impact", "Insurgency / Militancy",
            "Military Movement",
        ],
        "signal_buckets": [
            "trade_logistics_disruption", "conflict_escalation",
            "border_security", "humanitarian_stress", "military_movement",
        ],
        "loc_focus": [
            "NH-27", "NH-8", "NH-2", "NH-37", "NH-13", "NH-6", "NH-10", "NH-31",
            "Brahmaputra", "Barak", "Bogibeel", "Saraighat", "NJP",
            "Siliguri Corridor", "Jiribam", "Moreh", "Imphal corridor",
        ],
        "linked_faultlines": [
            {"id": "nbn_siliguri", "weight": 0.5},
            {"id": "asm_economic_environment", "weight": 0.4},
            {"id": "man_ethnic", "weight": 0.3},
            {"id": "asm_insurgency", "weight": 0.35},
        ],
        "active": True,
    },
]


async def seed_faultlines(db) -> dict:
    """
    Idempotent seed: upserts all faultlines into db.faultlines.
    Safe to call multiple times — will update existing docs, add new ones.
    Returns {inserted, updated, total}.
    """
    from datetime import datetime, timezone

    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc).isoformat()

    for fl in FAULTLINES:
        doc = {**fl, "updated_at": now}
        result = await db.faultlines.update_one(
            {"id": fl["id"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        elif result.modified_count:
            updated += 1

    return {"inserted": inserted, "updated": updated, "total": len(FAULTLINES)}


def get_state_region_map() -> dict:
    """Returns mapping of faultline state name → intelligence_items regions[] values."""
    return STATE_TO_REGIONS
