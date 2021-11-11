import math
import re

from .normalization import fold


def distance_m(a, b):
    if None in (a.lat, a.lon, b.get("lat"), b.get("lon")):
        return None
    lat1, lat2 = math.radians(a.lat), math.radians(b["lat"])
    delta_lat, delta_lon = lat2 - lat1, math.radians(b["lon"] - a.lon)
    h = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def matching_property(candidate, data, sources):
    """Conservative identity: a phone alone is never evidence of the same home."""
    if candidate.is_demo != data["is_demo"] or fold(candidate.city) != fold(data["city"]):
        return None
    if candidate.rooms != data["rooms"] or candidate.property_type != data["property_type"]:
        return None
    if abs(candidate.area_m2 - data["area_m2"]) > max(0.5, candidate.area_m2 * 0.015):
        return None
    if candidate.floor is not None and data["floor"] is not None and candidate.floor != data["floor"]:
        return None
    address = fold(data["address"])
    same_address = bool(re.search(r"\d", address)) and fold(candidate.address) == address
    distance = distance_m(candidate, data)
    same_phone = bool(data.get("phone_hash")) and any(s.phone_hash == data["phone_hash"] for s in sources)
    images = {image for source in sources for image in source.data.get("images", [])}
    same_image = bool(images.intersection(data["images"]))
    if (
        data["source"] in ("gratka", "morizon")
        and data.get("syndication_key")
        and address
        and fold(candidate.address) == address
        and (distance is None or distance <= 100)
        and any(
            s.source in ("gratka", "morizon")
            and s.source != data["source"]
            and s.data.get("syndication_key") == data["syndication_key"]
            for s in sources
        )
    ):
        return "Shared Morizon–Gratka listing identity, street, area and rooms"
    # A repost may omit the building number. Require two independent corroborating
    # signals plus close coordinates; one shared contact never merges properties.
    if (
        address
        and fold(candidate.address) == address
        and same_phone
        and same_image
        and any(s.source == data["source"] for s in sources)
        and distance is not None
        and distance <= 50
    ):
        return "Same street, contact, photo, area, rooms and nearby location"
    if not same_address or (distance is not None and distance > 100):
        return None
    if same_phone or same_image:
        return "Same building address, area, rooms and " + (
            "contact fingerprint" if same_phone else "image URL"
        )
    return None
