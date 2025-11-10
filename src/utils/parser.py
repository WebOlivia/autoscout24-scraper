import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from .data_cleaner import clean_text

log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - environment issue
    raise RuntimeError(
        "BeautifulSoup4 is required. Install with `pip install beautifulsoup4`."
    ) from exc

class ListingParser:
    """
    Responsible for turning Autoscout24 HTML into structured listing records.
    """

    def __init__(self) -> None:
        self.log = logging.getLogger(self.__class__.__name__)

    def _soup(self, html: str) -> "BeautifulSoup":
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:  # noqa: BLE001
            soup = BeautifulSoup(html, "html.parser")
        return soup

    def parse_search_page(
        self, html: str, base_url: str
    ) -> Tuple[List[str], Optional[str]]:
        """
        Extract listing URLs and optional link to next search results page.
        """
        soup = self._soup(html)
        listing_urls: List[str] = []

        # Common pattern: anchors pointing to detail /offers/ or /angebote/ routes
        for a in soup.select('a[href*="/angebote/"], a[href*="/offers/"], a[data-item-name="detail-page-link"]'):
            href = a.get("href")
            if not href:
                continue
            full_url = urljoin(base_url, href)
            if full_url not in listing_urls:
                listing_urls.append(full_url)

        # Best-effort detection of "next page" link
        next_link = (
            soup.select_one('a[rel="next"]')
            or soup.select_one('a[aria-label*="Next"]')
            or soup.select_one('a[aria-label*="Weiter"]')
        )
        next_url = None
        if next_link and next_link.get("href"):
            next_url = urljoin(base_url, next_link["href"])

        self.log.debug(
            "Parsed search page: %d listing URLs, next page: %s",
            len(listing_urls),
            "yes" if next_url else "no",
        )
        return listing_urls, next_url

    def _select_text(self, soup: "BeautifulSoup", selectors: List[str]) -> Optional[str]:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                text = clean_text(el.get_text(" ", strip=True))
                if text:
                    return text
        return None

    def _select_all_texts(
        self, soup: "BeautifulSoup", selectors: List[str]
    ) -> List[str]:
        results: List[str] = []
        for sel in selectors:
            for el in soup.select(sel):
                text = clean_text(el.get_text(" ", strip=True))
                if text and text not in results:
                    results.append(text)
        return results

    def parse_listing_page(self, html: str, url: str) -> Dict[str, Optional[str]]:
        """
        Parse a single listing detail page into a dictionary.

        The keys match the README description for compatibility.
        """
        soup = self._soup(html)

        title = self._select_text(
            soup,
            [
                'h1[data-testid="heading"]',
                "h1",
                'h2[data-item-name="car-title"]',
            ],
        )

        price = self._select_text(
            soup,
            [
                '[data-testid="price-label"]',
                "div.price-block span",
                "span[data-item-name=price]",
            ],
        )

        location = self._select_text(
            soup,
            [
                '[data-testid="seller-address"]',
                "div.seller-address",
                "span[itemprop=address]",
            ],
        )

        dealer_name = self._select_text(
            soup,
            [
                '[data-testid="seller-name"]',
                "div.dealer-info h2",
                ".cldt-vendor-contact-box h2",
            ],
        )

        dealer_ratings = self._select_text(
            soup,
            [
                '[data-testid="rating-count"]',
                "span.dealer-rating-count",
            ],
        )

        mark = self._select_text(
            soup,
            [
                '[data-testid="makeLabel"]',
                "span[itemprop=brand]",
            ],
        )

        model = self._select_text(
            soup,
            [
                '[data-testid="modelLabel"]',
                "span[itemprop=model]",
            ],
        )

        model_version = self._select_text(
            soup,
            [
                '[data-testid="versionLabel"]',
                "span.model-version",
            ],
        )

        milage = self._select_text(
            soup,
            [
                '[data-testid="mileage-label"]',
                "span.mileage",
                "dl[data-item-name=vehicle-details] dd:nth-of-type(1)",
            ],
        )

        gearbox = self._select_text(
            soup,
            [
                '[data-testid="transmission-label"]',
                "span.gearbox",
            ],
        )

        first_registration = self._select_text(
            soup,
            [
                '[data-testid="first-registration-label"]',
                "span.first-registration",
            ],
        )

        fuel_type = self._select_text(
            soup,
            [
                '[data-testid="fuel-label"]',
                "span.fuel",
            ],
        )

        power = self._select_text(
            soup,
            [
                '[data-testid="power-label"]',
                "span.power",
            ],
        )

        seller = self._select_text(
            soup,
            [
                '[data-testid="seller-type-label"]',
                "span.seller-type",
            ],
        )

        contact_name = self._select_text(
            soup,
            [
                '[data-testid="seller-contact-name"]',
                ".cldt-vendor-contact-box span",
            ],
        )

        contact_phone = self._select_text(
            soup,
            [
                '[data-testid="seller-phone"]',
                "a[href^='tel:']",
            ],
        )

        body_type = self._select_text(
            soup,
            [
                '[data-testid="body-type-label"]',
                "span.body-type",
            ],
        )

        drivetrain = self._select_text(
            soup,
            [
                '[data-testid="drive-type-label"]',
                "span.drivetrain",
            ],
        )

        seats = self._select_text(
            soup,
            [
                '[data-testid="num-seats-label"]',
                "span.seats",
            ],
        )

        engine_size = self._select_text(
            soup,
            [
                '[data-testid="cubic-capacity-label"]',
                "span.engine-size",
            ],
        )

        gears = self._select_text(
            soup,
            [
                '[data-testid="gears-label"]',
                "span.gears",
            ],
        )

        emission_class = self._select_text(
            soup,
            [
                '[data-testid="emission-class-label"]',
                "span.emission-class",
            ],
        )

        colour = self._select_text(
            soup,
            [
                '[data-testid="exterior-color-label"]',
                "span.exterior-color",
            ],
        )

        manufacturer_colour = self._select_text(
            soup,
            [
                '[data-testid="manufacturer-color-label"]',
                "span.manufacturer-color",
            ],
        )

        production_date = self._select_text(
            soup,
            [
                '[data-testid="production-date-label"]',
                "span.production-date",
            ],
        )

        comfort = self._select_all_texts(
            soup,
            [
                '[data-testid="comfort-features"] li',
                "ul.comfort-features li",
            ],
        )
        media = self._select_all_texts(
            soup,
            [
                '[data-testid="media-features"] li',
                "ul.media-features li",
            ],
        )
        safety = self._select_all_texts(
            soup,
            [
                '[data-testid="safety-features"] li',
                "ul.safety-features li",
            ],
        )
        extras = self._select_all_texts(
            soup,
            [
                '[data-testid="other-features"] li',
                "ul.extra-features li",
            ],
        )

        image_urls: List[str] = []
        for img in soup.select(
            "figure img, [data-testid='gallery'] img, .image-gallery img"
        ):
            src = img.get("src") or img.get("data-src")
            src = clean_text(src)
            if src and src not in image_urls:
                image_urls.append(src)

        record: Dict[str, Optional[str] | List[str]] = {
            "title": title,
            "url": clean_text(url),
            "mark": mark,
            "model": model,
            "modelVersion": model_version,
            "location": location,
            "dealerName": dealer_name,
            "dealerRatings": dealer_ratings,
            "price": price,
            "milage": milage,
            "gearbox": gearbox,
            "firstRegistration": first_registration,
            "fuelType": fuel_type,
            "power": power,
            "seller": seller,
            "contactName": contact_name,
            "contactPhone": contact_phone,
            "bodyType": body_type,
            "drivetrain": drivetrain,
            "seats": seats,
            "engineSize": engine_size,
            "gears": gears,
            "emissionClass": emission_class,
            "comfort": comfort,
            "media": media,
            "safety": safety,
            "extras": extras,
            "colour": colour,
            "manufacturerColour": manufacturer_colour,
            "productionDate": production_date,
            "images": image_urls,
        }

        return record