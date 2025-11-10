from collections import defaultdict
from typing import Any, Dict, Iterable

class DealerExtractor:
    """
    Helper for aggregating scraped listings by dealer.
    """

    @staticmethod
    def build_summary(listings: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Build a simple aggregation keyed by dealerName.
        """
        summary: Dict[str, Dict[str, Any]] = {}
        counter = defaultdict(int)

        for rec in listings:
            dealer_name = (rec.get("dealerName") or "").strip()
            if not dealer_name:
                dealer_name = "Unknown dealer"

            counter[dealer_name] += 1
            dealer_entry = summary.setdefault(
                dealer_name,
                {
                    "dealerName": dealer_name,
                    "location": rec.get("location"),
                    "dealerRatings": rec.get("dealerRatings"),
                    "listingCount": 0,
                },
            )
            dealer_entry["listingCount"] = counter[dealer_name]

        return summary