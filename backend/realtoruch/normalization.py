import hashlib
import hmac
import re
import unicodedata
from bs4 import BeautifulSoup
from .schemas import RawListing
from .settings import get_settings


def fold(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKD", text.lower().replace("ł", "l"))
        .encode("ascii", "ignore")
        .decode()
        .split()
    )


def clean_text(text: str, *, redact_contacts=True) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    # Contact data belongs in the private evidence store, never in the public description.
    plain = " ".join(soup.stripped_strings)
    if not redact_contacts:
        return plain
    return re.sub(r"(?<!\d)(?:\+?48[\s.-]?)?(?:\d[\s.-]?){9}(?!\d)", "[contact via source]", plain)


def hash_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0048"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "48" + digits
    if len(digits) != 11 or not digits.startswith("48"):
        return None
    return hmac.new(get_settings().phone_hash_key.encode(), digits.encode(), hashlib.sha256).hexdigest()


def normalize(raw: RawListing) -> dict:
    record = raw.model_dump(mode="json", exclude={"phone"})
    record["phone_hash"] = hash_phone(raw.phone) or raw.phone_hash
    record["title"] = clean_text(raw.title)
    record["description"] = clean_text(raw.description)
    record["address"] = " ".join(raw.address.split())
    record["city"] = " ".join(raw.city.split())
    return record
