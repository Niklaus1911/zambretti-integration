import logging

from .dictionaries import REGIONS

_LOGGER = logging.getLogger(__name__)

REGION_LABELS_IT = {
    "azores": "Azzorre",
    "british isles": "Isole Britanniche",
    "western europe coast": "Costa Europa Occidentale",
    "north sea baltic": "Mare del Nord e Baltico",
    "mediterranean nw": "Mediterraneo Nord-Ovest",
    "mediterranean sw": "Mediterraneo Sud-Ovest",
    "mediterranean ne": "Mediterraneo Nord-Est",
    "mediterranean se": "Mediterraneo Sud-Est",
    "caribbean": "Caraibi",
    "american east coast": "Costa Est Americana",
    "north atlantic": "Atlantico del Nord",
    "unknown": "Sconosciuto",
}


def determine_region(lat, lon):
    """Determine which region a location falls into and return the region name & URL."""
    # A set of coordinates (lat,lon) might land in multiple regions. The REGIONS dictionary
    # is order from small regions to large regions and this function picks the first one.
    # So 'british isles' is picked, not 'north_atlantic' (british_isles are in the north_atlantic).

    for region, values in REGIONS.items():
        lat_min, lat_max, lon_min, lon_max, url = values  # ✅ Correct unpacking
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            region_name_raw = region.replace("_", " ")
            region_name = REGION_LABELS_IT.get(
                region_name_raw.lower(), region_name_raw.title()
            )
            _LOGGER.debug(
                f"✅ Location ({lat}, {lon}) identified as {region}, url {url}."
            )
            return region, region_name, url
    _LOGGER.debug(f"✅ Location ({lat}, {lon}) no region.")
    return "unknown", "Sconosciuto", "none"
