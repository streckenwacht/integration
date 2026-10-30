"""Constants for the Streckenwacht integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "streckenwacht"

# Keep in sync with manifest.json (checked by tests/test_manifest.py).
VERSION: Final = "0.9.2"
USER_AGENT: Final = (
    f"Streckenwacht/{VERSION} (+https://github.com/streckenwacht/integration)"
)

# Times in the source texts are German local time.
LOCAL_TZ: Final = ZoneInfo("Europe/Berlin")

REQUEST_TIMEOUT: Final = 30  # seconds

# Config entry options
CONF_SOURCES: Final = "sources"  # entry option up to 0.2.0, migrated to the areas
CONF_SCAN_INTERVAL: Final = "scan_interval"  # minutes
CONF_INCLUDE_INRIX: Final = "include_inrix"
CONF_MERGE_DUPLICATES: Final = "merge_duplicates"

DEFAULT_SCAN_INTERVAL: Final = 15
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 60
DEFAULT_INCLUDE_INRIX: Final = True
DEFAULT_MERGE_DUPLICATES: Final = True

# Observation area subentries
SUBENTRY_AREA: Final = "area"
CONF_LOCATION: Final = "location"
CONF_RADIUS: Final = "radius"  # meters, as returned by the location selector
CONF_ROADS: Final = "roads"
CONF_AREA_SOURCES: Final = "sources"  # per area (since entry minor version 2)
CONF_DIRECTIONS: Final = "directions"
CONF_TYPES: Final = "types"  # per area; None/missing means all
CONF_JAM_THRESHOLD: Final = "jam_threshold"  # minutes

DEFAULT_RADIUS: Final = 10_000
# geo.py's flat-earth approximation is accurate up to roughly 100 km.
MAX_RADIUS: Final = 100_000
# Traffic jams count as a disruption from this travel time loss on, so that
# minor slowdowns on long routes do not keep "disruption active" on.
DEFAULT_JAM_THRESHOLD: Final = 10

# Consecutive failed polls of a provider before a repair issue is raised
# (3 x 15 min): a short API hiccup should not alarm anyone.
FAILURES_BEFORE_ISSUE: Final = 3


class Source(StrEnum):
    """Data sources (one provider each)."""

    AUTOBAHN = "autobahn"
    MOBIDATA_BW = "mobidata_bw"
    STUTTGART = "stuttgart"
    NORDDEUTSCHLAND = "norddeutschland"
    BERLIN = "berlin"
    BRANDENBURG = "brandenburg"
    SACHSEN_ANHALT = "sachsen_anhalt"
    SACHSEN = "sachsen"
    RHEINLAND_PFALZ = "rheinland_pfalz"
    MUENCHEN = "muenchen"
    KOELN = "koeln"
    FRANKFURT = "frankfurt"
    DORTMUND = "dortmund"
    AACHEN = "aachen"
    DUISBURG = "duisburg"
    MUENSTER = "muenster"
    LUXEMBURG = "luxemburg"
    KARLSRUHE = "karlsruhe"
    ROSTOCK = "rostock"
    KIEL = "kiel"
    INGOLSTADT = "ingolstadt"
    FREIBURG = "freiburg"
    LMS_BW = "lms_bw"


# Proper names, used as translation placeholders (not translatable).
SOURCE_NAMES: Final[dict[Source, str]] = {
    Source.AUTOBAHN: "Autobahn GmbH",
    Source.MOBIDATA_BW: "MobiData BW",
    Source.STUTTGART: "Stadt Stuttgart",
    Source.NORDDEUTSCHLAND: "Baustelleninformationen Norddeutschland",
    Source.BERLIN: "VIZ Berlin",
    Source.BRANDENBURG: "Landesbetrieb Straßenwesen Brandenburg",
    Source.SACHSEN_ANHALT: "Sperrinfo Sachsen-Anhalt",
    Source.SACHSEN: "Baustelleninformationssystem Sachsen",
    Source.RHEINLAND_PFALZ: "Mobilitätsatlas Rheinland-Pfalz",
    Source.MUENCHEN: "Landeshauptstadt München",
    Source.KOELN: "Stadt Köln",
    Source.FRANKFURT: "Stadt Frankfurt am Main",
    Source.DORTMUND: "Stadt Dortmund",
    Source.AACHEN: "Stadt Aachen",
    Source.DUISBURG: "Stadt Duisburg",
    Source.MUENSTER: "Stadt Münster",
    Source.LUXEMBURG: "Ponts et Chaussées Luxemburg",
    Source.KARLSRUHE: "Mobilitätsportal Technologieregion Karlsruhe",
    Source.ROSTOCK: "Hanse- und Universitätsstadt Rostock",
    Source.KIEL: "Landeshauptstadt Kiel",
    Source.INGOLSTADT: "Stadt Ingolstadt",
    Source.FREIBURG: "Stadt Freiburg im Breisgau",
    Source.LMS_BW: "Landesmeldestelle Baden-Württemberg",
}

# Attribution required by the data licenses (see docs/ENTWICKLUNG.md, section 4).
ATTRIBUTION: Final[dict[Source, str]] = {
    Source.AUTOBAHN: "Die Autobahn GmbH des Bundes",
    Source.MOBIDATA_BW: "MobiData BW, Datenlizenz Deutschland – Namensnennung 2.0",
    Source.STUTTGART: "© Landeshauptstadt Stuttgart, CC BY 4.0",
    Source.NORDDEUTSCHLAND: "LBV.SH Baustelleninformationen, © Geokompetenz/LVermGeo SH/CC BY 4.0",
    Source.BERLIN: (
        "Digitale Plattform Stadtverkehr Berlin / Baustellen, Sperrungen und sonstige "
        "Störungen von besonderem verkehrlichem Interesse, dl-de/by-2-0"
    ),
    Source.BRANDENBURG: "© Landesbetrieb Straßenwesen Brandenburg, dl-de/by-2-0",
    # The service allows non-commercial use only (WFS AccessConstraints).
    Source.SACHSEN_ANHALT: (
        "Sperrinfo, Ministerium für Landesentwicklung und Verkehr Sachsen-Anhalt; "
        "nur nichtkommerzielle Nutzung"
    ),
    Source.SACHSEN: "Baustelleninformationssystem Sachsen, CC BY 4.0",
    # Published without a license on the Mobilithek (rights: NO_LICENSE).
    Source.RHEINLAND_PFALZ: "Landesbetrieb Mobilität Rheinland-Pfalz (Mobilitätsatlas)",
    Source.MUENCHEN: "dl-de/by-2-0: Landeshauptstadt München – opendata.muenchen.de",
    Source.KOELN: "Stadt Köln, Verkehrskalender, dl-de/zero-2-0",
    # The WFS states no license (GeoServer default "AccessConstraints: YES").
    Source.FRANKFURT: "Stadt Frankfurt am Main (geowebdienste.frankfurt.de)",
    Source.DORTMUND: "Stadt Dortmund, dl-de/zero-2-0",
    Source.AACHEN: "Stadt Aachen, dl-de/by-2-0",
    Source.DUISBURG: "Stadt Duisburg, CC BY 3.0 DE",
    Source.MUENSTER: "Stadt Münster, dl-de/by-2-0",
    Source.LUXEMBURG: "Administration des Ponts et Chaussées, Luxemburg, CC0",
    Source.KARLSRUHE: "Stadt Karlsruhe / Mobilitätsportal Technologieregion Karlsruhe, CC BY 4.0",
    Source.ROSTOCK: "Hanse- und Universitätsstadt Rostock, CC0",
    Source.KIEL: "Landeshauptstadt Kiel, CC BY 4.0",
    Source.INGOLSTADT: "Stadt Ingolstadt, CC BY 4.0",
    Source.FREIBURG: "Stadt Freiburg i. Br. – Garten- und Tiefbauamt, Datenlizenz Deutschland – Namensnennung 2.0",
    Source.LMS_BW: "Landesmeldestelle Baden-Württemberg / MobiData BW, Datenlizenz Deutschland – Namensnennung 2.0",
}

# Additional attribution for data the source got from a third party.
UPSTREAM_INRIX: Final = "inrix"
UPSTREAM_ATTRIBUTION: Final[dict[str, str]] = {
    UPSTREAM_INRIX: "Verkehrslage: INRIX",
}

# Bounding box as (south, west, north, east) in degrees.
type Bounds = tuple[float, float, float, float]

BADEN_WUERTTEMBERG: Final[Bounds] = (47.5, 7.5, 49.8, 10.5)
STUTTGART: Final[Bounds] = (48.69, 9.03, 48.87, 9.32)
SCHLESWIG_HOLSTEIN_HAMBURG: Final[Bounds] = (53.35, 7.8, 55.1, 11.4)
MECKLENBURG_VORPOMMERN: Final[Bounds] = (53.1, 10.5, 54.7, 14.5)
NIEDERSACHSEN: Final[Bounds] = (51.29, 6.6, 53.9, 11.6)
BERLIN: Final[Bounds] = (52.33, 13.08, 52.68, 13.77)
BRANDENBURG: Final[Bounds] = (51.35, 11.26, 53.56, 14.77)
# Finer parts for offering sources (a few boxes per state): the single boxes
# above reach far into neighbouring states (Dortmund would get Niedersachsen,
# Magdeburg Brandenburg). Areas near a border may still get both states.
_NIEDERSACHSEN_PARTS: Final = (
    (52.25, 6.6, 53.9, 10.95),
    (51.29, 8.9, 52.25, 10.95),
    (52.75, 10.95, 53.3, 11.6),
)
_BRANDENBURG_PARTS: Final = (
    (51.75, 12.2, 53.56, 14.77),
    (51.35, 13.2, 51.75, 14.77),
    (52.75, 11.26, 53.4, 12.2),
)
_SACHSEN_ANHALT_PARTS: Final = (
    (50.93, 10.56, 52.0, 12.6),
    (52.0, 10.9, 53.05, 12.6),
    (51.4, 12.6, 52.1, 13.19),
)
_RHEINLAND_PFALZ_PARTS: Final = (
    (48.96, 6.11, 50.6, 8.51),
    (50.6, 7.3, 50.95, 8.2),
)
SACHSEN_ANHALT: Final[Bounds] = (50.93, 10.56, 53.05, 13.19)
SACHSEN: Final[Bounds] = (50.17, 11.87, 51.69, 15.04)
RHEINLAND_PFALZ: Final[Bounds] = (48.96, 6.11, 50.95, 8.51)
MUENCHEN: Final[Bounds] = (48.06, 11.36, 48.25, 11.72)
KOELN: Final[Bounds] = (50.83, 6.77, 51.09, 7.17)
FRANKFURT: Final[Bounds] = (50.01, 8.47, 50.23, 8.80)
DORTMUND: Final[Bounds] = (51.41, 7.30, 51.60, 7.64)
AACHEN: Final[Bounds] = (50.68, 5.97, 50.86, 6.22)
DUISBURG: Final[Bounds] = (51.33, 6.62, 51.56, 6.83)
MUENSTER: Final[Bounds] = (51.84, 7.47, 52.06, 7.78)
LUXEMBURG: Final[Bounds] = (49.44, 5.73, 50.19, 6.53)
KARLSRUHE: Final[Bounds] = (48.75, 7.85, 49.30, 8.75)
ROSTOCK: Final[Bounds] = (54.03, 11.95, 54.25, 12.30)
KIEL: Final[Bounds] = (54.25, 10.03, 54.43, 10.25)
INGOLSTADT: Final[Bounds] = (48.70, 11.30, 48.83, 11.52)
FREIBURG: Final[Bounds] = (47.90, 7.66, 48.08, 7.94)

# Rough regions of the regional sources: an area is offered the sources whose
# region its circle touches. Sources without a region (the Autobahn) cover all
# of Germany.
SOURCE_REGIONS: Final[dict[Source, tuple[Bounds, ...]]] = {
    Source.MOBIDATA_BW: (BADEN_WUERTTEMBERG,),
    Source.STUTTGART: (STUTTGART,),
    Source.NORDDEUTSCHLAND: (
        SCHLESWIG_HOLSTEIN_HAMBURG,
        MECKLENBURG_VORPOMMERN,
        *_NIEDERSACHSEN_PARTS,
    ),
    Source.BERLIN: (BERLIN,),
    Source.BRANDENBURG: _BRANDENBURG_PARTS,
    Source.SACHSEN_ANHALT: _SACHSEN_ANHALT_PARTS,
    Source.SACHSEN: (SACHSEN,),
    Source.RHEINLAND_PFALZ: _RHEINLAND_PFALZ_PARTS,
    Source.MUENCHEN: (MUENCHEN,),
    Source.KOELN: (KOELN,),
    Source.FRANKFURT: (FRANKFURT,),
    Source.DORTMUND: (DORTMUND,),
    Source.AACHEN: (AACHEN,),
    Source.DUISBURG: (DUISBURG,),
    Source.MUENSTER: (MUENSTER,),
    Source.LUXEMBURG: (LUXEMBURG,),
    Source.KARLSRUHE: (KARLSRUHE,),
    Source.ROSTOCK: (ROSTOCK,),
    Source.KIEL: (KIEL,),
    Source.INGOLSTADT: (INGOLSTADT,),
    Source.FREIBURG: (FREIBURG,),
    Source.LMS_BW: (BADEN_WUERTTEMBERG,),
}
