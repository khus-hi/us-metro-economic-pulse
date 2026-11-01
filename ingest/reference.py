"""Static reference codes (published code lists, not data values).

- State postal code -> FIPS code and Census division: Census Bureau standard.
- Census division -> BLS CPI area code: from the BLS `cu.area` file.
- Metro CPI area -> CBSA: BLS publishes CPI for 23 areas; we map each to the
  2023 CBSA by its core city. The CPI uses its own 2018 sample design, so the
  boundaries can differ slightly, and the dashboard labels this.
"""

# postal: (state_fips, census_division_code)
# Census divisions: 1 New England, 2 Middle Atlantic, 3 East North Central,
# 4 West North Central, 5 South Atlantic, 6 East South Central,
# 7 West South Central, 8 Mountain, 9 Pacific.
STATES: dict[str, tuple[str, int]] = {
    "AL": ("01", 6), "AK": ("02", 9), "AZ": ("04", 8), "AR": ("05", 7), "CA": ("06", 9),
    "CO": ("08", 8), "CT": ("09", 1), "DE": ("10", 5), "DC": ("11", 5), "FL": ("12", 5),
    "GA": ("13", 5), "HI": ("15", 9), "ID": ("16", 8), "IL": ("17", 3), "IN": ("18", 3),
    "IA": ("19", 4), "KS": ("20", 4), "KY": ("21", 6), "LA": ("22", 7), "ME": ("23", 1),
    "MD": ("24", 5), "MA": ("25", 1), "MI": ("26", 3), "MN": ("27", 4), "MS": ("28", 6),
    "MO": ("29", 4), "MT": ("30", 8), "NE": ("31", 4), "NV": ("32", 8), "NH": ("33", 1),
    "NJ": ("34", 2), "NM": ("35", 8), "NY": ("36", 2), "NC": ("37", 5), "ND": ("38", 4),
    "OH": ("39", 3), "OK": ("40", 7), "OR": ("41", 9), "PA": ("42", 2), "RI": ("44", 1),
    "SC": ("45", 5), "SD": ("46", 4), "TN": ("47", 6), "TX": ("48", 7), "UT": ("49", 8),
    "VT": ("50", 1), "VA": ("51", 5), "WA": ("53", 9), "WV": ("54", 5), "WI": ("55", 3),
    "WY": ("56", 8), "PR": ("72", 0),
}

DIVISION_CPI_AREA = {
    1: "0110", 2: "0120", 3: "0230", 4: "0240", 5: "0350",
    6: "0360", 7: "0370", 8: "0480", 9: "0490",
}

# CPI area code -> CBSA code (2023 delineation), mapped by core city. [verify]
METRO_CPI_AREA = {
    "S11A": "14460", "S12A": "35620", "S12B": "37980", "S23A": "16980",
    "S23B": "19820", "S24A": "33460", "S24B": "41180", "S35A": "47900",
    "S35B": "33100", "S35C": "12060", "S35D": "45300", "S35E": "12580",
    "S37A": "19100", "S37B": "26420", "S48A": "38060", "S48B": "19740",
    "S49A": "31080", "S49B": "41860", "S49C": "40140", "S49D": "42660",
    "S49E": "41740",
}
CBSA_TO_CPI_AREA = {cbsa: area for area, cbsa in METRO_CPI_AREA.items()}


def principal_state(cbsa_title: str) -> str:
    """'Boston-Cambridge-Newton, MA-NH' -> 'MA' (OMB lists the principal state first)."""
    return cbsa_title.rsplit(",", 1)[1].strip().split("-")[0]


def cpi_area_for(cbsa_code: str, state_postal: str) -> tuple[str, str]:
    """Return (cpi_area_code, geo_level) where geo_level is 'metro' or 'division'."""
    if cbsa_code in CBSA_TO_CPI_AREA:
        return CBSA_TO_CPI_AREA[cbsa_code], "metro"
    return DIVISION_CPI_AREA[STATES[state_postal][1]], "division"
