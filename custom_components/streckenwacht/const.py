"""Constants for the Streckenwacht integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "streckenwacht"

# Keep in sync with manifest.json (checked by tests/test_manifest.py).
VERSION: Final = "0.1.0"
USER_AGENT: Final = (
    f"Streckenwacht/{VERSION} (+https://github.com/streckenwacht/integration)"
)

# Times in the source texts are German local time.
LOCAL_TZ: Final = ZoneInfo("Europe/Berlin")

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=15)
REQUEST_TIMEOUT: Final = 30  # seconds


class Source(StrEnum):
    """Data sources (one provider each)."""

    AUTOBAHN = "autobahn"
    MOBIDATA_BW = "mobidata_bw"
    STUTTGART = "stuttgart"


# Attribution required by the data licenses (see docs/HANDOVER.md, section 8).
ATTRIBUTION: Final[dict[Source, str]] = {
    Source.AUTOBAHN: "Die Autobahn GmbH des Bundes",
    Source.MOBIDATA_BW: "MobiData BW, Datenlizenz Deutschland – Namensnennung 2.0",
    Source.STUTTGART: "© Landeshauptstadt Stuttgart, CC BY 4.0",
}
