import itertools
import logging
import os
import threading
from typing import Dict, Iterable, List, Optional

log = logging.getLogger(__name__)

class ProxyManager:
    """
    Simple round-robin proxy manager.

    Proxies can be provided directly as a list of HTTP URLs or via environment
    variables HTTP_PROXIES / HTTPS_PROXIES (comma separated).
    """

    def __init__(
        self,
        proxies: Optional[Iterable[str]] = None,
        use_env: bool = True,
    ) -> None:
        env_proxies: List[str] = []
        if use_env:
            for env_key in ("HTTP_PROXIES", "HTTPS_PROXIES"):
                raw = os.getenv(env_key)
                if raw:
                    env_proxies.extend(
                        p.strip() for p in raw.split(",") if p.strip()
                    )

        all_proxies = list(proxies or []) + env_proxies
        self._proxies = [p for p in all_proxies if p]
        self._lock = threading.Lock()
        self._iterator = itertools.cycle(self._proxies) if self._proxies else None

        if self._proxies:
            log.info("ProxyManager configured with %d proxies.", len(self._proxies))
        else:
            log.info("ProxyManager running in direct mode (no proxies configured).")

    def has_proxies(self) -> bool:
        return bool(self._proxies)

    def get_next(self) -> Optional[Dict[str, str]]:
        """
        Return a proxies dict suitable for requests, or None when no proxy is configured.
        """
        if not self._iterator:
            return None
        with self._lock:
            proxy = next(self._iterator, None)
        if not proxy:
            return None
        return {
            "http": proxy,
            "https": proxy,
        }