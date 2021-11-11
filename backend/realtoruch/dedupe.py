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
    if not same_address or (distance is not None and distance > 100):
        return None
    same_phone = bool(data.get("phone_hash")) and any(s.phone_hash == data["phone_hash"] for s in sources)
    same_image = bool(set(candidate.images).intersection(data["images"]))
    if same_phone or same_image:
        return "Same building address, area, rooms and " + (
            "contact fingerprint" if same_phone else "image URL"
        )
    return None
