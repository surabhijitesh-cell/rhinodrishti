"""
subissue_seed.py — Sub-issue (micro-faultline) ontology for RhinoDrishti.

Sub-issues are concrete, observable manifestations of parent faultlines that
appear directly in news: actors, events, locations, LOC assets, narratives.

Pattern mirrors faultline_seed.py — SUBISSUE_SEED is a list of dicts,
seeded via POST /api/faultlines/seed-subissues.

Field notes:
  - faultline_id: references FAULTLINES.id in faultline_seed.py
  - default_weight: 0.0–1.0; LOC sub-issues use 0.85–0.95 (commander priority)
  - actor_types / event_types: controlled vocabulary (see lists below)
  - loc_focus: NH names, river names, corridor names that anchor Stage 2 scoring
"""

# ── Controlled vocabularies ───────────────────────────────────────────────────
ACTOR_TYPES = [
    "ethnic_org", "insurgent_group", "church_body", "state_police", "paramilitary",
    "border_force", "railway_authority", "road_authority", "flood_authority",
    "smuggler_network", "madrasa_network", "political_party", "chinese_entity",
    "isl_outfit",
]

EVENT_TYPES = [
    "protest", "blockade", "riot", "militant_attack", "explosion_ied",
    "smuggling_case", "illegal_migration_case", "land_acquisition",
    "infra_development", "flood", "landslide", "bridge_collapse", "road_closure",
    "train_disruption", "rail_roko", "arson", "arrest", "encounter",
    "demolition",
]

SUBISSUE_SEED = [

    # ═══ NER LINES OF COMMUNICATION (ner_loc) ════════════════════════════════
    {
        "faultline_id": "ner_loc", "state": "NER",
        "name": "NH blockade choking NER corridor",
        "description": (
            "Any national highway blockade >12h cutting security force movement "
            "or civilian logistics across NER."
        ),
        "keywords": [
            "NH-27 blocked", "NH-8 blockade", "NH-37 closed", "highway blocked northeast",
            "road blockade NH", "truckers strike NER", "NH-2 disruption",
            "highway siege northeast", "blockade highway Assam", "road closed northeast",
            "highway blockade", "road blockade", "highway blocked", "blockade",
            "economic blockade", "bandh", "fuel crisis", "fuel shortage",
            "LPG shortage", "supply disruption", "essential supplies",
            "road siege", "highway closed", "highway disruption",
        ],
        "actor_types": ["ethnic_org", "insurgent_group", "political_party"],
        "event_types": ["blockade", "road_closure"],
        "narrative_markers": [
            "stranded trucks", "supply disruption", "movement restricted",
            "road closed indefinitely", "highway siege", "lorry stranded",
            "fuel crisis", "LPG prices", "supply shortage", "essential goods",
            "highway blockade", "road blockade",
        ],
        "loc_focus": ["NH-27", "NH-8", "NH-37", "NH-2", "NH-13", "NH-6", "NH-10", "NH-31"],
        "default_weight": 0.92,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "ner_loc", "state": "NER",
        "name": "Railway disruption on NER trunk routes",
        "description": (
            "Train sabotage, protest rail-roko, or accident blocking key NER "
            "rail lines for >6 hours."
        ),
        "keywords": [
            "rail roko northeast", "railway disruption Assam", "train cancelled northeast",
            "sabotage railway NER", "track blast northeast", "railway blocked Manipur",
            "train derailment northeast", "rail disruption Tripura",
        ],
        "actor_types": ["insurgent_group", "ethnic_org", "political_party"],
        "event_types": ["train_disruption", "rail_roko", "explosion_ied"],
        "narrative_markers": [
            "rail roko", "trains cancelled", "passengers stranded",
            "track damaged", "railway disruption", "train derailed",
        ],
        "loc_focus": [
            "Lumding junction", "Guwahati station", "NJP", "New Jalpaiguri",
            "Jiribam line", "Barak Valley rail", "Katihar line", "Siliguri Junction",
        ],
        "default_weight": 0.90,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "ner_loc", "state": "NER",
        "name": "Bridge failure or closure on LOC route",
        "description": (
            "Structural failure, flood damage, or sabotage of a key bridge on "
            "a security-critical corridor."
        ),
        "keywords": [
            "bridge collapse northeast", "bridge closed NER", "Brahmaputra bridge damaged",
            "Barak bridge", "bridge flood northeast", "Bogibeel bridge",
            "Saraighat bridge", "bridge washed away NER",
        ],
        "actor_types": ["flood_authority", "road_authority"],
        "event_types": ["bridge_collapse", "flood", "landslide"],
        "narrative_markers": [
            "bridge washed away", "bridge closed", "alternative route",
            "cut off", "bridge collapse", "spanning damaged",
        ],
        "loc_focus": [
            "Bogibeel", "Saraighat", "Barak bridge", "Jiribam bridge",
            "Zokhawthar bridge", "Moreh bridge", "Jiri bridge",
        ],
        "default_weight": 0.92,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "ner_loc", "state": "NER",
        "name": "Riverine logistics disruption",
        "description": (
            "Ferry closure, river port disruption, or Brahmaputra/Barak "
            "crossing unavailability affecting military logistics."
        ),
        "keywords": [
            "Brahmaputra ferry closed", "Dhubri ferry", "river crossing disrupted northeast",
            "ferry service suspended Assam", "Barak waterway blocked",
            "river port closed northeast",
        ],
        "actor_types": ["flood_authority"],
        "event_types": ["flood", "road_closure"],
        "narrative_markers": [
            "ferry suspended", "river crossing halted", "boat service stopped",
            "no ferry service", "river blocked",
        ],
        "loc_focus": ["Brahmaputra", "Barak", "Dhubri", "Dhansiri", "Kopili"],
        "default_weight": 0.80,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "ner_loc", "state": "NER",
        "name": "Flood or landslide closing NER highway",
        "description": "Natural disaster event directly cutting a national highway for >6 hours.",
        "keywords": [
            "flood NH northeast", "landslide blocked NH", "highway washed out northeast",
            "road cut landslide NER", "flash flood NH-27", "landslide NH Assam",
            "road washed away northeast",
        ],
        "actor_types": ["flood_authority"],
        "event_types": ["flood", "landslide", "road_closure"],
        "narrative_markers": [
            "washed out", "road cut", "NH blocked flood", "buried by landslide",
            "road cave-in", "highway submerged",
        ],
        "loc_focus": ["NH-27", "NH-8", "NH-37", "NH-13", "NH-6", "Jiribam route"],
        "default_weight": 0.88,
        "cross_border_relevance": False,
        "enabled": True,
    },

    # ═══ SILIGURI CORRIDOR (nbn_siliguri) ════════════════════════════════════
    {
        "faultline_id": "nbn_siliguri", "state": "North Bengal",
        "name": "Siliguri Corridor NH threat",
        "description": (
            "Threat to NH-10, NH-31, or feeder roads into Siliguri Corridor "
            "from protest, blockade, or physical damage."
        ),
        "keywords": [
            "Siliguri corridor blocked", "NH-10 blocked", "NH-31 disruption",
            "chicken neck road blocked", "Jalpaiguri highway", "Siliguri NH threat",
            "corridor access blocked", "Siliguri access threatened",
        ],
        "actor_types": ["ethnic_org", "political_party", "insurgent_group"],
        "event_types": ["blockade", "road_closure", "militant_attack"],
        "narrative_markers": [
            "chicken neck", "corridor choked", "Siliguri access blocked",
            "corridor threatened",
        ],
        "loc_focus": ["NH-10", "NH-31", "Jalpaiguri", "Siliguri", "Bagdogra"],
        "default_weight": 0.95,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "nbn_siliguri", "state": "North Bengal",
        "name": "Siliguri rail trunk vulnerability",
        "description": (
            "Disruption to NJP–Guwahati rail line or Katihar feeder that "
            "cuts the corridor's rail link."
        ),
        "keywords": [
            "NJP disruption", "New Jalpaiguri rail blocked", "Katihar line disruption",
            "Siliguri Junction blocked", "northeast rail disruption Bengal",
            "rail roko Siliguri",
        ],
        "actor_types": ["insurgent_group", "political_party", "railway_authority"],
        "event_types": ["train_disruption", "rail_roko", "explosion_ied"],
        "narrative_markers": [
            "NJP trains cancelled", "Siliguri rail blocked", "northeast rail cut",
            "corridor rail disrupted",
        ],
        "loc_focus": ["NJP", "New Jalpaiguri", "Siliguri Junction", "Katihar line"],
        "default_weight": 0.90,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "nbn_siliguri", "state": "North Bengal",
        "name": "Chinese-linked infrastructure threat to Siliguri",
        "description": (
            "Chinese-funded or proxy-enabled projects that affect strategic "
            "geometry around Siliguri Corridor."
        ),
        "keywords": [
            "Chinese project Siliguri", "China infrastructure Bengal",
            "BRI corridor Bengal", "Chinese land North Bengal",
            "PLA activity corridor", "Chinese influence Siliguri",
        ],
        "actor_types": ["chinese_entity"],
        "event_types": ["infra_development", "land_acquisition"],
        "narrative_markers": [
            "Chinese investment corridor", "BRI Bengal", "Chinese company corridor",
            "proxy influence Siliguri",
        ],
        "loc_focus": ["Siliguri Corridor", "chicken neck", "Chumbi Valley"],
        "default_weight": 0.87,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "nbn_siliguri", "state": "North Bengal",
        "name": "Siliguri flood or bridge failure",
        "description": (
            "Flood or structural failure blocking Teesta/Mahananda crossings "
            "critical to Siliguri Corridor."
        ),
        "keywords": [
            "Teesta flood Siliguri", "Mahananda flood", "bridge Siliguri flood",
            "NH-31 washed Siliguri", "corridor flooded",
        ],
        "actor_types": ["flood_authority"],
        "event_types": ["flood", "bridge_collapse", "landslide"],
        "narrative_markers": [
            "Siliguri cut off", "corridor flooded", "Teesta overflow",
            "Siliguri isolated",
        ],
        "loc_focus": ["Teesta", "Mahananda", "NH-31", "Siliguri", "NJP"],
        "default_weight": 0.88,
        "cross_border_relevance": False,
        "enabled": True,
    },

    # ═══ ASSAM LOC + IBB (asm_economic_environment + asm_communalism) ════════
    {
        "faultline_id": "asm_economic_environment", "state": "Assam",
        "name": "Brahmaputra bridge or ferry disruption",
        "description": (
            "Closure or damage to key Brahmaputra crossings (Bogibeel, Saraighat) "
            "affecting Guwahati–Dibrugarh LOC corridor."
        ),
        "keywords": [
            "Bogibeel bridge closed", "Saraighat bridge Assam", "Brahmaputra crossing disrupted",
            "ferry Brahmaputra suspended Assam", "Dhubri ferry Assam",
            "Brahmaputra flood bridge Assam",
        ],
        "actor_types": ["flood_authority", "road_authority"],
        "event_types": ["bridge_collapse", "flood", "road_closure"],
        "narrative_markers": [
            "bridge closed Assam", "Brahmaputra flooded", "ferry suspended Assam",
            "crossing disrupted",
        ],
        "loc_focus": ["Bogibeel", "Saraighat", "Brahmaputra", "Dhubri", "Tezpur bridge"],
        "default_weight": 0.90,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "asm_economic_environment", "state": "Assam",
        "name": "Assam NH blockade (Guwahati–Dibrugarh corridor)",
        "description": (
            "Blockade or closure of NH-27 or NH-37 disrupting the main Assam "
            "logistics spine toward Upper Assam and Arunachal Pradesh."
        ),
        "keywords": [
            "NH-27 blocked Assam", "NH-37 blockade Assam", "Guwahati Dibrugarh road blocked",
            "highway protest Assam", "truckers Assam blockade", "supply chain Assam NH",
        ],
        "actor_types": ["ethnic_org", "political_party"],
        "event_types": ["blockade", "road_closure"],
        "narrative_markers": [
            "NH-27 closed", "supply disruption Assam", "trucker strike Assam",
            "highway blocked Assam",
        ],
        "loc_focus": ["NH-27", "NH-37", "Dibrugarh", "Tinsukia", "Jorhat"],
        "default_weight": 0.88,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "asm_communalism", "state": "Assam",
        "name": "ISI-linked madrasa network near Assam IBB",
        "description": (
            "ISI-connected or externally funded madrasa / radical network "
            "operating near Assam–Bangladesh border."
        ),
        "keywords": [
            "ISI Assam", "madrasa Assam border", "radical network Assam Bangladesh",
            "Islamist Assam border", "sleeper cell Assam", "jihad Assam border",
            "ISI module Assam",
        ],
        "actor_types": ["madrasa_network", "isl_outfit"],
        "event_types": ["arrest", "militant_attack"],
        "narrative_markers": [
            "ISI link Assam", "madrasa network border", "Pakistan-backed Assam",
            "sleeper cell Assam", "radical outfit Assam",
        ],
        "loc_focus": ["Karimganj", "Cachar", "Barak Valley", "Silchar border", "Dhubri"],
        "default_weight": 0.92,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "asm_communalism", "state": "Assam",
        "name": "Narcotics or arms smuggling across Assam IBB",
        "description": (
            "Drug or arms trafficking across the Assam–Bangladesh border, "
            "indicating active corridor use."
        ),
        "keywords": [
            "drug Assam Bangladesh border", "arms smuggling Assam border",
            "yaba Assam", "heroin Assam border", "contraband Assam Bangladesh",
            "smuggling Cachar border",
        ],
        "actor_types": ["smuggler_network", "border_force"],
        "event_types": ["smuggling_case", "arrest"],
        "narrative_markers": [
            "seized at border Assam", "smuggling route Assam", "BSF seized Assam",
            "narcotics border Assam",
        ],
        "loc_focus": ["Karimganj", "Cachar", "Dhubri", "Barak Valley border"],
        "default_weight": 0.85,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "asm_communalism", "state": "Assam",
        "name": "BGB infrastructure build-up opposite Assam border",
        "description": (
            "Bangladesh Border Guard road construction, post establishment, "
            "or land acquisition near Assam IBB."
        ),
        "keywords": [
            "BGB post Assam border", "Bangladesh border construction Assam",
            "BGB activity Assam", "new BGB outpost Assam",
            "BGB infrastructure Assam",
        ],
        "actor_types": ["border_force"],
        "event_types": ["infra_development", "land_acquisition"],
        "narrative_markers": [
            "new BGB post Assam", "BGB road Assam", "observation tower Bangladesh Assam",
            "BGB activity Assam border",
        ],
        "loc_focus": ["Karimganj district border", "Dhubri border", "Cachar border"],
        "default_weight": 0.90,
        "cross_border_relevance": True,
        "enabled": True,
    },

    # ═══ TRIPURA IBB + NH-8 (tri_ethnic) ═════════════════════════════════════
    {
        "faultline_id": "tri_ethnic", "state": "Tripura",
        "name": "Drug or contraband smuggling across Tripura IBB",
        "description": (
            "Yaba, cattle, arms, or timber smuggling across Tripura–Bangladesh "
            "border indicating active corridor use."
        ),
        "keywords": [
            "drug Tripura Bangladesh border", "yaba Tripura", "cattle smuggling Tripura",
            "contraband Tripura border", "smuggling Sonamura", "BSF seized Tripura border",
        ],
        "actor_types": ["smuggler_network", "border_force"],
        "event_types": ["smuggling_case", "arrest"],
        "narrative_markers": [
            "seized at border Tripura", "Sonamura route", "smuggling corridor Tripura",
            "cattle seized Tripura",
        ],
        "loc_focus": ["Sonamura", "Agartala border", "Gomati border", "Sabroom", "Belonia"],
        "default_weight": 0.88,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "tri_ethnic", "state": "Tripura",
        "name": "Illegal migration from Bangladesh into Tripura",
        "description": (
            "Detected or alleged illegal migration from Bangladesh across "
            "Tripura border segments."
        ),
        "keywords": [
            "illegal migration Tripura", "Bangladeshi migrant Tripura",
            "undocumented Tripura border", "border crossing Tripura illegal",
        ],
        "actor_types": ["border_force"],
        "event_types": ["illegal_migration_case", "arrest"],
        "narrative_markers": [
            "pushed back Tripura", "detained Bangladeshi Tripura",
            "migration Tripura border",
        ],
        "loc_focus": ["Agartala border", "Sonamura", "Tripura Bangladesh border"],
        "default_weight": 0.83,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "tri_ethnic", "state": "Tripura",
        "name": "BGB posture and infrastructure near Tripura border",
        "description": (
            "BGB patrol changes, post construction, or land acquisition "
            "opposite Tripura."
        ),
        "keywords": [
            "BGB Tripura border", "Bangladesh border guard Tripura", "BGB post Tripura",
            "BGB activity near Tripura", "Bangladesh military Tripura border",
        ],
        "actor_types": ["border_force"],
        "event_types": ["infra_development", "land_acquisition"],
        "narrative_markers": [
            "new BGB post Tripura", "BGB road Tripura", "BGB patrol Tripura border",
        ],
        "loc_focus": ["Agartala border", "Sonamura", "Gomati district border"],
        "default_weight": 0.90,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "tri_ethnic", "state": "Tripura",
        "name": "NH-8 Tripura blockade or disruption",
        "description": (
            "Blockade or disruption of NH-8 — the primary NH into/out of Tripura."
        ),
        "keywords": [
            "NH-8 Tripura blocked", "NH-8 Tripura disruption", "blockade Tripura highway",
            "Tripura road blocked", "Agartala highway blocked",
        ],
        "actor_types": ["ethnic_org", "political_party", "insurgent_group"],
        "event_types": ["blockade", "road_closure", "militant_attack"],
        "narrative_markers": [
            "NH-8 closed Tripura", "Tripura cut off", "supply route Tripura blocked",
        ],
        "loc_focus": ["NH-8", "Udaipur Tripura", "Sabroom", "Agartala highway"],
        "default_weight": 0.87,
        "cross_border_relevance": False,
        "enabled": True,
    },

    # ═══ MANIPUR — LOC + Myanmar cross-border (man_ethnic + man_arms) ════════
    {
        "faultline_id": "man_ethnic", "state": "Manipur",
        "name": "NH-37 / Imphal–Jiribam corridor blockade",
        "description": (
            "Ethnic-group-imposed blockade on NH-37 (Imphal–Jiribam) — "
            "the main LOC into Manipur valley."
        ),
        "keywords": [
            "NH-37 blockade Manipur", "Imphal Jiribam road blocked",
            "Manipur highway blockade", "economic blockade Manipur",
            "NH-2 Manipur blocked",
        ],
        "actor_types": ["ethnic_org"],
        "event_types": ["blockade", "road_closure"],
        "narrative_markers": [
            "NH-37 closed", "Imphal cut off", "economic blockade Manipur",
            "Jiribam road blocked", "valley cut off",
        ],
        "loc_focus": ["NH-37", "NH-2", "Imphal corridor", "Jiribam", "Kangpokpi road"],
        "default_weight": 0.92,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "man_ethnic", "state": "Manipur",
        "name": "Ethnic violence diverting security forces from NER",
        "description": (
            "Scale of Manipur conflict requiring redeployment of security forces "
            "that weakens rear-area cover elsewhere in NER."
        ),
        "keywords": [
            "CAPF Manipur deployed", "forces redeployed Manipur",
            "security reinforcement Manipur", "CRPF Manipur deployment",
            "additional troops Manipur",
        ],
        "actor_types": ["paramilitary", "state_police"],
        "event_types": ["riot", "militant_attack", "protest"],
        "narrative_markers": [
            "additional forces deployed Manipur", "forces rushed Manipur",
            "paramilitary reinforced Manipur",
        ],
        "loc_focus": ["Imphal", "Churachandpur", "Kangpokpi", "Bishnupur"],
        "default_weight": 0.75,
        "cross_border_relevance": False,
        "enabled": True,
    },
    {
        "faultline_id": "man_arms", "state": "Manipur",
        "name": "Myanmar-linked militant supply route into Manipur",
        "description": (
            "Cross-border flow of arms, militants, or supplies from Myanmar "
            "through Manipur border."
        ),
        "keywords": [
            "Myanmar militant Manipur", "Kuki militant Myanmar",
            "arms from Myanmar Manipur", "cross-border Manipur Myanmar",
            "militant camp Myanmar Manipur border",
        ],
        "actor_types": ["insurgent_group"],
        "event_types": ["smuggling_case", "militant_attack", "arrest", "encounter"],
        "narrative_markers": [
            "from Myanmar Manipur", "cross-border supplies Manipur",
            "militant camp Myanmar Manipur",
        ],
        "loc_focus": ["Moreh border", "Tedim road", "Churachandpur Myanmar", "Zokhawthar"],
        "default_weight": 0.90,
        "cross_border_relevance": True,
        "enabled": True,
    },

    # ═══ BANGLADESH → IBB faultlines (bgd_radicalization) ════════════════════
    {
        "faultline_id": "bgd_radicalization", "state": "Bangladesh",
        "name": "Islamist radicalization network with NER IBB linkage",
        "description": (
            "Hefazat/JMB/ISI-linked networks in Bangladesh with active "
            "connections to madrasa or radical cells near IBB."
        ),
        "keywords": [
            "Islamist Bangladesh border NER", "JMB NER link",
            "ISI Bangladesh NER link", "radical Bangladesh India IBB",
            "Hefazat India link",
        ],
        "actor_types": ["isl_outfit", "madrasa_network"],
        "event_types": ["arrest", "militant_attack"],
        "narrative_markers": [
            "Bangladesh link ISI", "cross-border radicalization NER",
            "ISI handler Bangladesh NER",
        ],
        "loc_focus": ["Sylhet corridor", "Chittagong link", "Comilla border"],
        "default_weight": 0.88,
        "cross_border_relevance": True,
        "enabled": True,
    },
    {
        "faultline_id": "bgd_radicalization", "state": "Bangladesh",
        "name": "BGB infrastructure build-up opposite NER IBB sectors",
        "description": (
            "Bangladesh Border Guard road construction, post establishment, "
            "or land acquisition near NER IBB sectors."
        ),
        "keywords": [
            "BGB post construction NER", "BGB road Bangladesh border NER",
            "BGB new post IBB", "Bangladesh border infrastructure NER",
            "BGB land acquisition IBB",
        ],
        "actor_types": ["border_force"],
        "event_types": ["infra_development", "land_acquisition"],
        "narrative_markers": [
            "new BGB post IBB", "BGB road extended NER", "BGB land acquired IBB",
            "observation tower Bangladesh IBB",
        ],
        "loc_focus": [
            "Hili border", "Sylhet corridor", "Comilla border",
            "Karimganj opposite", "Meghalaya opposite Bangladesh",
        ],
        "default_weight": 0.90,
        "cross_border_relevance": True,
        "enabled": True,
    },

    # ═══ MEGHALAYA — Tribal Dynamics sub-issues ══════════════════════════════

    # Sub-issue 1: Dorbar Shnong authority under stress (parent: meg_tribe_conflict)
    {
        "faultline_id": "meg_tribe_conflict", "state": "Meghalaya",
        "name": "Dorbar Shnong & traditional authority under stress",
        "description": (
            "Pressure on Meghalaya's traditional governing bodies — Dorbar Shnong "
            "(Khasi village councils), Nokma headmen (Garo), Dolloi/Lyngdoh (Jaintia) "
            "— from state encroachment, political party interference, and contested "
            "succession disputes. Any move by state or courts to override customary "
            "authority, or intra-community power struggles over Syiemship or Rangbah "
            "Shnong positions, signals structural fragility in community self-governance."
        ),
        "keywords": [
            "Dorbar Shnong", "Syiem Meghalaya", "Nokma", "Lyngdoh Meghalaya",
            "Rangbah Shnong", "traditional council Meghalaya", "headman Meghalaya",
            "village authority Meghalaya", "customary law Meghalaya", "Syiemship",
            "Dolloi", "Elaka Meghalaya", "clan dispute Meghalaya",
            "village headman Meghalaya", "tribal council dispute Meghalaya",
            "customary court Meghalaya",
        ],
        "actor_types": ["ethnic_org", "political_party", "state_police"],
        "event_types": ["protest", "riot", "land_acquisition", "arson"],
        "narrative_markers": [
            "Dorbar Shnong order", "headman removed", "Syiem controversy",
            "village council dissolved", "customary law challenged",
            "traditional authority violated", "Nokma dispute",
        ],
        "loc_focus": [
            "East Khasi Hills", "West Khasi Hills", "Ri Bhoi",
            "East Jaintia Hills", "West Garo Hills",
        ],
        "default_weight": 0.75,
        "cross_border_relevance": False,
        "enabled": True,
    },

    # Sub-issue 2: ILP agitation & non-tribal settler evictions (parent: meg_indigenous)
    {
        "faultline_id": "meg_indigenous", "state": "Meghalaya",
        "name": "ILP agitation and non-tribal settler evictions",
        "description": (
            "Organised agitation by KSU and Confederation of Meghalaya Social "
            "Organisations (CoMSO) for Inner Line Permit implementation; targeted "
            "eviction drives against non-tribal (dkhar) settlers in Shillong, Tura, "
            "and Jowai. Key flashpoints: Republican Colony, Punjabi Lane (Shillong), "
            "Laitumkhrah market. MRSSA (Meghalaya Residents Safety and Security Act) "
            "enforcement gaps. Any eviction notice, demolition drive, or KSU-led "
            "march targeting non-tribal commercial establishments."
        ),
        "keywords": [
            "ILP Meghalaya", "inner line permit Meghalaya", "dkhar",
            "non-tribal eviction Meghalaya", "KSU agitation", "KSU rally",
            "Punjabi Lane Shillong", "Republican Colony Shillong",
            "MRSSA", "CoMSO", "outsider eviction Shillong",
            "settler eviction Meghalaya", "non-tribal land Meghalaya",
            "dkhar eviction", "indigenous rights Meghalaya",
            "Laitumkhrah eviction", "Iewduh market", "Shillong non-tribal",
            "foreigner Meghalaya eviction",
        ],
        "actor_types": ["ethnic_org", "political_party", "state_police"],
        "event_types": ["protest", "demolition", "riot", "arson", "blockade"],
        "narrative_markers": [
            "eviction notice Meghalaya", "demolition drive Shillong",
            "non-tribal removed", "ILP demand", "dkhar asked to leave",
            "KSU deadline", "settler shops closed", "outsider targeted",
        ],
        "loc_focus": [
            "Shillong", "Laitumkhrah", "Iewduh", "Punjabi Lane",
            "Republican Colony", "Tura", "Jowai",
        ],
        "default_weight": 0.80,
        "cross_border_relevance": False,
        "enabled": True,
    },

    # ═══ MEGHALAYA LOC focus (meg_environment) ═══════════════════════════════
    {
        "faultline_id": "meg_environment", "state": "Meghalaya",
        "name": "Coal corridor and transport route disruption",
        "description": (
            "Blockades, protests, or NGT orders disrupting coal and goods "
            "transport on NH connections through Meghalaya."
        ),
        "keywords": [
            "coal transport Meghalaya blocked", "NH Meghalaya blockade",
            "mining protest road Meghalaya", "NH-6 Meghalaya blocked",
            "Shillong bypass blocked",
        ],
        "actor_types": ["ethnic_org", "political_party"],
        "event_types": ["blockade", "protest", "road_closure"],
        "narrative_markers": [
            "coal trucks halted Meghalaya", "NH Meghalaya closed",
            "transport blocked Meghalaya",
        ],
        "loc_focus": ["NH-6", "Shillong bypass", "Jowai road", "Tura road Meghalaya"],
        "default_weight": 0.78,
        "cross_border_relevance": False,
        "enabled": True,
    },
]


async def seed_subissues(db) -> dict:
    """
    Idempotent seed: upserts all sub-issues into db.faultline_subissues.
    Keyed on (faultline_id, name) pair — safe to call multiple times.
    Returns {inserted, updated, total}.
    """
    from datetime import datetime, timezone

    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc).isoformat()

    for si in SUBISSUE_SEED:
        doc = {**si, "updated_at": now}
        result = await db.faultline_subissues.update_one(
            {"faultline_id": si["faultline_id"], "name": si["name"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        elif result.modified_count:
            updated += 1

    return {"inserted": inserted, "updated": updated, "total": len(SUBISSUE_SEED)}
