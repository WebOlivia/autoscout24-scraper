import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests

from utils.data_cleaner import normalize_listing
from utils.parser import ListingParser
from utils.proxy_manager import ProxyManager

log = logging.getLogger(__name__)

class ListingExtractor:
    """
    Orchestrates HTTP fetching and HTML parsing for Autoscout24 listings.
    """

    def __init__(
        self,
        max_records: int = 300,
        proxy_manager: Optional[ProxyManager] = None,
        timeout: float = 15.0,
        parallel_requests: int = 8,
        user_agent: Optional[str] = None,
    ) -> None:
        self.max_records = max_records
        self.proxy_manager = proxy_manager or ProxyManager()
        self.timeout = timeout
        self.parallel_requests = max(1, parallel_requests)
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )

        self.parser = ListingParser()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.log = logging.getLogger(self.__class__.__name__)

    def _is_detail_url(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return "/angebote/" in path or "/offers/" in path

    def _fetch_url(self, url: str) -> Optional[str]:
        proxies = self.proxy_manager.get_next()
        try:
            resp = self.session.get(
                url,
                timeout=self.timeout,
                proxies=proxies,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            self.log.warning("Failed to fetch %s: %s", url, exc)
            return None

    def _collect_listing_urls_from_search(
        self, start_url: str
    ) -> List[str]:
        listing_urls: List[str] = []
        visited_pages: Set[str] = set()
        next_url: Optional[str] = start_url

        while next_url and len(listing_urls) < self.max_records:
            if next_url in visited_pages:
                break
            visited_pages.add(next_url)

            html = self._fetch_url(next_url)
            if not html:
                break

            page_urls, next_url = self.parser.parse_search_page(html, next_url)
            for u in page_urls:
                if u not in listing_urls:
                    listing_urls.append(u)
            if not next_url:
                break

        return listing_urls

    def _prepare_listing_urls(self, start_urls: Iterable[str]) -> List[str]:
        listing_urls: List[str] = []
        for start_url in start_urls:
            start_url = start_url.strip()
            if not start_url:
                continue

            if self._is_detail_url(start_url):
                if start_url not in listing_urls:
                    listing_urls.append(start_url)
                continue

            self.log.info("Expanding search URL: %s", start_url)
            urls = self._collect_listing_urls_from_search(start_url)
            for u in urls:
                if u not in listing_urls:
                    listing_urls.append(u)

            if len(listing_urls) >= self.max_records:
                break

        if len(listing_urls) > self.max_records:
            listing_urls = listing_urls[: self.max_records]

        self.log.info(
            "Prepared %d listing URLs (max=%d).",
            len(listing_urls),
            self.max_records,
        )
        return listing_urls

    def _scrape_single_listing(self, url: str) -> Optional[Dict]:
        html = self._fetch_url(url)
        if not html:
            return None
        raw_record = self.parser.parse_listing_page(html, url)
        return normalize_listing(raw_record)

    def scrape(self, start_urls: Iterable[str]) -> List[Dict]:
        """
        High-level function to scrape all listings from a set of start URLs.
        """
        urls = self._prepare_listing_urls(start_urls)
        if not urls:
            self.log.warning("No listing URLs to scrape.")
            return []

        results: List[Dict] = []
        with ThreadPoolExecutor(max_workers=self.parallel_requests) as executor:
            future_to_url: Dict = {
                executor.submit(self._scrape_single_listing, url): url
                for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001
                    self.log.error("Error scraping %s: %s", url, exc)
                    continue

                if record:
                    results.append(record)

        self.log.info("Successfully scraped %d listings.", len(results))
        return results