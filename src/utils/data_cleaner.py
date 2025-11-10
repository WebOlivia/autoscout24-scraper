import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)

def ensure_directory(path: Path) -> None:
    """Create parent directory if needed."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        return

def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None

def extract_number(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    digits = re.findall(r"\d+", str(value).replace(".", "").replace(" ", ""))
    if not digits:
        return None
    try:
        return int("".join(digits))
    except ValueError:
        return None

def parse_price(price_str: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """
    Extract numeric price and currency from a price string.
    Example: "€ 31,980" -> (31980, "EUR")
    """
    if not price_str:
        return None, None

    s = price_str.strip()
    currency = None

    if "€" in s or "EUR" in s.upper():
        currency = "EUR"
    elif "$" in s or "USD" in s.upper():
        currency = "USD"
    elif "CHF" in s.upper():
        currency = "CHF"

    # Remove non-digit separators except comma/dot used as thousand separator
    raw_digits = re.sub(r"[^\d]", "", s)
    if not raw_digits:
        return None, currency

    try:
        price_int = int(raw_digits)
    except ValueError:
        log.debug("Failed to parse price from %s", s)
        return None, currency

    return price_int, currency

def parse_mileage(mileage_str: Optional[str]) -> Optional[int]:
    """
    Parse mileage string like "161,415 km" into integer kilometers.
    """
    return extract_number(mileage_str)

def parse_power(power_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse engine power string into kW and hp.
    Example: "240 kW (326 hp)" -> (240, 326)
    """
    if not power_str:
        return None, None

    kW = None
    hp = None

    kw_match = re.search(r"(\d+)\s*kW", power_str)
    hp_match = re.search(r"(\d+)\s*hp", power_str, flags=re.IGNORECASE)

    if kw_match:
        try:
            kW = int(kw_match.group(1))
        except ValueError:
            pass

    if hp_match:
        try:
            hp = int(hp_match.group(1))
        except ValueError:
            pass

    return kW, hp

def normalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and enrich a raw listing dict with additional derived fields.
    """
    listing = dict(listing)

    # Clean basic text fields
    for key in [
        "title",
        "url",
        "mark",
        "model",
        "modelVersion",
        "location",
        "dealerName",
        "dealerRatings",
        "price",
        "milage",
        "gearbox",
        "firstRegistration",
        "fuelType",
        "power",
        "seller",
        "contactName",
        "contactPhone",
        "bodyType",
        "drivetrain",
        "seats",
        "engineSize",
        "gears",
        "emissionClass",
        "colour",
        "manufacturerColour",
        "productionDate",
    ]:
        listing[key] = clean_text(listing.get(key))

    # Price breakdown
    raw_price, currency = parse_price(listing.get("price"))
    if raw_price is not None:
        listing["rawPrice"] = raw_price
    if currency is not None:
        listing["currency"] = currency

    # Mileage numeric
    mileage_km = parse_mileage(listing.get("milage"))
    if mileage_km is not None:
        listing["mileageKm"] = mileage_km

    # Power breakdown
    kW, hp = parse_power(listing.get("power"))
    if kW is not None:
        listing["powerKW"] = kW
    if hp is not None:
        listing["powerHP"] = hp

    # Seats, engine size, gears as numbers when possible
    for src, dest in [
        ("seats", "seatsNum"),
        ("engineSize", "engineSizeCC"),
        ("gears", "gearsNum"),
    ]:
        val = extract_number(listing.get(src))
        if val is not None:
            listing[dest] = val

    # Feature lists (comfort/media/safety/extras) as lists of strings
    for feature_key in ["comfort", "media", "safety", "extras"]:
        value = listing.get(feature_key)
        if isinstance(value, list):
            listing[feature_key] = [clean_text(v) for v in value if clean_text(v)]
        elif isinstance(value, str):
            parts = [clean_text(p) for p in re.split(r"[;,]", value) if clean_text(p)]
            listing[feature_key] = parts
        elif value is None:
            listing[feature_key] = []
        else:
            listing[feature_key] = [clean_text(str(value))]

    # Images as unique non-empty strings
    images = listing.get("images") or []
    if isinstance(images, str):
        images = [images]
    if isinstance(images, list):
        seen = set()
        normalized = []
        for img in images:
            img = clean_text(img)
            if img and img not in seen:
                seen.add(img)
                normalized.append(img)
        listing["images"] = normalized
    else:
        listing["images"] = []

    return listing