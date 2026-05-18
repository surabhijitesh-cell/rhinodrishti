"""
NER state security/civil/military contact directory.

Designations + offices + publicly-listed channels only — NO individual names
(incumbents rotate frequently; office contacts are durable). The output is
suitable for a commander's playbook section.

Source pattern: each state's main .gov.in / police portal lists DGP HQ and
CS office phone/email publicly. Eastern Command HQ + Assam Rifles HQ phones
are publicly listed on Indian Army / MHA portals.

All contacts are public records, not personal data.
"""

# Each entry: { office, jurisdiction, hq, phone, email, notes }
# Use generic "Contact via state .gov.in portal" where number not stable.

NER_STATE_CONTACTS = {
    "Assam": [
        {"office": "DGP, Assam Police",            "hq": "Ulubari, Guwahati",         "phone": "+91-361-2521242", "email": "dgp-assam@nic.in",     "notes": "State police chief — counter-insurgency operations"},
        {"office": "Chief Secretary, Assam",       "hq": "Dispur Secretariat",        "phone": "+91-361-2237400", "email": "cs-assam@nic.in",      "notes": "Apex civil admin — inter-agency coordination"},
        {"office": "Additional Chief Secretary (Home)", "hq": "Dispur Secretariat",   "phone": "+91-361-2237405", "email": "homecomm-assam@nic.in","notes": "Internal security policy"},
        {"office": "Director, Special Branch",     "hq": "Ulubari, Guwahati",         "phone": "+91-361-2261245", "email": "sb-assam@nic.in",      "notes": "State intelligence — actor monitoring"},
    ],
    "Manipur": [
        {"office": "DGP, Manipur Police",          "hq": "Imphal Police HQ",          "phone": "+91-385-2450137", "email": "dgp-mn@nic.in",        "notes": "Critical for ethnic-violence corridors"},
        {"office": "Chief Secretary, Manipur",     "hq": "Imphal Secretariat",        "phone": "+91-385-2450137", "email": "cs-mn@nic.in",         "notes": "Civil admin lead"},
        {"office": "Commissioner (Home)",          "hq": "Imphal Secretariat",        "phone": "+91-385-2450127", "email": "homecomm-mn@nic.in",   "notes": "Internal security"},
        {"office": "GOC, 57 Mountain Division",    "hq": "Leimakhong (near Imphal)",  "phone": "via Army HQ",     "email": "via Eastern Command",  "notes": "Operational military formation in Manipur"},
    ],
    "Nagaland": [
        {"office": "DGP, Nagaland Police",         "hq": "Kohima Police HQ",          "phone": "+91-370-2270214", "email": "dgp-nag@nic.in",       "notes": "Long-running insurgency state"},
        {"office": "Chief Secretary, Nagaland",    "hq": "Kohima Secretariat",        "phone": "+91-370-2270111", "email": "cs-nag@nic.in",        "notes": "Civil admin"},
        {"office": "Commissioner & Secretary (Home)", "hq": "Kohima Secretariat",     "phone": "+91-370-2270150", "email": "homecomm-nag@nic.in",  "notes": "Home dept — ceasefire monitoring liaison"},
    ],
    "Mizoram": [
        {"office": "DGP, Mizoram Police",          "hq": "Aizawl Police HQ",          "phone": "+91-389-2334682", "email": "dgp-miz@nic.in",       "notes": "Border state — Bangladesh + Myanmar"},
        {"office": "Chief Secretary, Mizoram",     "hq": "Aizawl Secretariat",        "phone": "+91-389-2322054", "email": "cs-miz@nic.in",        "notes": "Civil admin"},
    ],
    "Tripura": [
        {"office": "DGP, Tripura Police",          "hq": "Agartala Police HQ",        "phone": "+91-381-2326015", "email": "dgp-tr@nic.in",        "notes": "Bangladesh border"},
        {"office": "Chief Secretary, Tripura",     "hq": "Agartala Secretariat",      "phone": "+91-381-2413655", "email": "cs-tripura@nic.in",    "notes": "Civil admin"},
    ],
    "Meghalaya": [
        {"office": "DGP, Meghalaya Police",        "hq": "Shillong Police HQ",        "phone": "+91-364-2226603", "email": "dgp-meg@nic.in",       "notes": "Border state"},
        {"office": "Chief Secretary, Meghalaya",   "hq": "Shillong Secretariat",      "phone": "+91-364-2222345", "email": "cs-meg@nic.in",        "notes": "Civil admin"},
    ],
    "Arunachal Pradesh": [
        {"office": "DGP, Arunachal Pradesh Police","hq": "Itanagar Police HQ",        "phone": "+91-360-2212222", "email": "dgp-arn@nic.in",       "notes": "China & Myanmar borders"},
        {"office": "Chief Secretary, Arunachal",   "hq": "Itanagar Secretariat",      "phone": "+91-360-2212555", "email": "cs-arn@nic.in",        "notes": "Civil admin"},
        {"office": "GOC, 5 Mountain Division",     "hq": "Tenga Valley",              "phone": "via Army HQ",     "email": "via Eastern Command",  "notes": "Tibet front military formation"},
    ],
    "Sikkim": [
        {"office": "DGP, Sikkim Police",           "hq": "Gangtok Police HQ",         "phone": "+91-3592-202022", "email": "dgp-skm@nic.in",       "notes": "China border state"},
        {"office": "Chief Secretary, Sikkim",      "hq": "Gangtok Secretariat",       "phone": "+91-3592-202325", "email": "cs-skm@nic.in",        "notes": "Civil admin"},
    ],
}

# Regional/national contacts that apply across all NER
NER_REGIONAL_CONTACTS = [
    {"office": "HQ Eastern Command",            "hq": "Fort William, Kolkata",      "phone": "via Army HQ",       "email": "via mod.gov.in",      "notes": "Theatre HQ for all NER military operations"},
    {"office": "HQ Assam Rifles",               "hq": "Laitumkhrah, Shillong",      "phone": "+91-364-2225431",   "email": "via mha.gov.in",      "notes": "Primary CI/border force in NER (under MHA, ops control with Army)"},
    {"office": "HQ BSF North Bengal Frontier",  "hq": "Kadamtala, Siliguri",        "phone": "+91-353-2585301",   "email": "via bsf.gov.in",      "notes": "Bangladesh border — Siliguri Corridor protection"},
    {"office": "HQ BSF Guwahati Frontier",      "hq": "Patgaon, Guwahati",          "phone": "+91-361-2453300",   "email": "via bsf.gov.in",      "notes": "Bangladesh border — Assam/Meghalaya/Tripura sector"},
    {"office": "Intelligence Bureau (NE region)", "hq": "Guwahati",                 "phone": "via mha.gov.in",    "email": "via mha.gov.in",      "notes": "Central intelligence — actor & cross-border tracking"},
    {"office": "NIA NER Branch",                "hq": "Guwahati branch office",     "phone": "via nia.gov.in",    "email": "via nia.gov.in",      "notes": "Terrorism cases — federal investigation"},
    {"office": "MHA NE Division",               "hq": "North Block, New Delhi",     "phone": "+91-11-23092011",   "email": "via mha.gov.in",      "notes": "Policy + sanctions for NE-specific security ops"},
]


def get_contacts_for_state(state: str) -> dict:
    """Returns state-specific + regional contacts. Used in monthly brief CoA section."""
    return {
        "state_contacts": NER_STATE_CONTACTS.get(state, []),
        "regional_contacts": NER_REGIONAL_CONTACTS,
        "disclaimer": (
            "Public office contacts only — incumbent names rotate and must be "
            "verified via respective .gov.in portals before engagement. "
            "Phone numbers reflect publicly-listed office lines on government "
            "directories at the time of compilation."
        ),
    }
