"""Explicitly synthetic fixtures. Never executed in production startup."""

from datetime import datetime, timedelta
from sqlalchemy import select
from .db import Session, init_db
from .ingest import ingest
from .models import Listing, now
from .schemas import RawListing
from .settings import get_settings

PHOTOS = [
    "photo-1600210492486-724fe5c67fb0",
    "photo-1600607687939-ce8a6c25118c",
    "photo-1600566753086-00f18fb6b3ea",
    "photo-1600210491892-03d54c0aaf87",
    "photo-1600607687920-4e2a09cf159d",
    "photo-1600566753190-17f0baa2a6c3",
]
HOMES = [
    (
        "Light-filled living in a quiet courtyard",
        "Mokotów",
        "ul. Dąbrowskiego 24",
        52.2028,
        21.0094,
        54,
        2,
        3400,
        650,
        "private",
        ["balcony", "furnished", "pets", "dishwasher"],
        "700100101",
    ),
    (
        "A little more room. A lot more light.",
        "Wola",
        "ul. Siedmiogrodzka 5",
        52.2308,
        20.9729,
        62,
        3,
        4200,
        780,
        "private",
        ["balcony", "parking", "lift", "furnished"],
        "700100102",
    ),
    (
        "Your corner of old Warsaw",
        "Śródmieście",
        "ul. Wilcza 18",
        52.2245,
        21.0183,
        38,
        2,
        2950,
        520,
        "private",
        ["furnished", "dishwasher", "pets"],
        "700100103",
    ),
    (
        "Calm mornings by the park",
        "Żoliborz",
        "ul. Krasińskiego 16",
        52.2691,
        20.9836,
        47,
        2,
        3150,
        560,
        "private",
        ["balcony", "pets", "furnished"],
        "700100104",
    ),
    (
        "Modern studio, well connected",
        "Praga-Północ",
        "ul. Ząbkowska 14",
        52.2543,
        21.0425,
        29,
        1,
        2350,
        450,
        "private",
        ["furnished", "lift"],
        "700100105",
    ),
    (
        "Space for your next chapter",
        "Wilanów",
        "ul. Sarmacka 8",
        52.1601,
        21.0739,
        78,
        3,
        5100,
        920,
        "agency",
        ["balcony", "parking", "lift", "pets"],
        "700100106",
    ),
    (
        "An airy apartment near the metro",
        "Mokotów",
        "ul. Puławska 120",
        52.1945,
        21.0252,
        44,
        2,
        2800,
        610,
        "private",
        ["furnished", "lift"],
        "700100107",
    ),
    (
        "A peaceful base in Powiśle",
        "Śródmieście",
        "ul. Dobra 32",
        52.2398,
        21.0270,
        51,
        2,
        3900,
        690,
        "private",
        ["balcony", "dishwasher", "furnished"],
        "700100107",
    ),
    (
        "City living, thoughtfully considered",
        "Wola",
        "ul. Grzybowska 61",
        52.2341,
        20.9870,
        43,
        2,
        3600,
        700,
        "private",
        ["lift", "furnished", "parking"],
        "700100107",
    ),
    (
        "A green outlook in Saska Kępa",
        "Praga-Południe",
        "ul. Francuska 38",
        52.2329,
        21.0604,
        58,
        3,
        3750,
        620,
        "agency",
        ["balcony", "pets", "dishwasher"],
        "700100110",
    ),
    (
        "Compact, comfortable, close to everything",
        "Ochota",
        "ul. Filtrowa 62",
        52.2163,
        20.9912,
        32,
        1,
        2550,
        480,
        "private",
        ["furnished", "pets"],
        "700100111",
    ),
    (
        "An easy place to come home to",
        "Ursynów",
        "ul. Dereniowa 9",
        52.1459,
        21.0413,
        67,
        3,
        3650,
        750,
        "private",
        ["balcony", "lift", "parking"],
        "700100112",
    ),
]


def seed():
    if not get_settings().demo_mode or get_settings().environment == "production":
        raise SystemExit("Set DEMO_MODE=true in development to load synthetic fixtures")
    init_db()
    with Session() as session:
        if session.scalar(select(Listing.id).where(Listing.is_demo.is_(True)).limit(1)):
            print("Demo homes already present; nothing changed")
            return
    current = now()
    for month_ago in reversed(range(6)):
        for index, home in enumerate(HOMES):
            title, district, address, lat, lon, area, rooms, rent, fees, advertiser, amenities, phone = home
            moment = current - timedelta(days=month_ago * 30, minutes=index * 11 + 5)
            price = rent + (month_ago * 50 if index % 3 == 0 else -month_ago * 30)
            sources = ["otodom", "olx"] if index < 5 else [["gratka", "morizon", "otodom", "olx"][index % 4]]
            if index == 0:
                sources.append("gratka")
            for j, source in enumerate(sources):
                raw = RawListing(
                    source=source,
                    external_id=f"demo-{index}",
                    url=f"https://{'www.' if source in ('otodom', 'olx', 'morizon') else ''}{source}.pl/",
                    title=title,
                    description="A fictional rental used to demonstrate the app. A bright, well-proportioned home with a comfortable living area, a fitted kitchen and good connections to the city. Photos are illustrative and do not represent an actual offer. Source prices and availability are sample data.",
                    city="Warszawa",
                    district=district,
                    region="mazowieckie",
                    address=address,
                    lat=lat,
                    lon=lon,
                    area_m2=area,
                    rooms=rooms,
                    floor=2 + index % 4,
                    rent_pln=price + (100 if j == 1 else 0),
                    fees_pln=fees,
                    deposit_pln=rent,
                    commission_pln=rent if advertiser == "agency" else 0,
                    advertiser_type=advertiser,
                    phone=phone,
                    amenities=amenities,
                    images=[
                        f"https://images.unsplash.com/{PHOTOS[index % len(PHOTOS)]}?auto=format&fit=crop&w=1000&q=80",
                        f"https://images.unsplash.com/{PHOTOS[(index + 1) % len(PHOTOS)]}?auto=format&fit=crop&w=1000&q=80",
                    ],
                    observed_at=moment + timedelta(seconds=j),
                    is_demo=True,
                )
                with Session.begin() as session:
                    ingest(session, raw)
    print("Loaded 12 synthetic homes, 18 source listings and six months of example observations")


if __name__ == "__main__":
    seed()
