"""Real search provider adapter supporting external HTTP-based search APIs.

Supports standard OSINT search backends: SearXNG, SerpAPI, Tavily, and generic search APIs.
Configured via environment variables; credentials are never hard-coded.
"""

from datetime import datetime
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from bs4 import BeautifulSoup
import httpx

from app.discovery.provider import SearchProvider
from app.discovery.url_utils import extract_domain, is_valid_url
from app.logging_config import logger
from app.models.errors import SearchProviderException, SearchTimeoutException
from app.models.schemas import SearchResult


class HttpSearchProvider(SearchProvider):
    """External HTTP search provider adapter supporting DuckDuckGo, SearXNG, SerpAPI, Tavily, and generic JSON APIs."""

    def __init__(
        self,
        provider_type: str = "duckduckgo",
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: float = 10.0,
    ):
        """Initialize HttpSearchProvider.

        Args:
            provider_type: The provider type ("duckduckgo", "searxng", "serpapi", "tavily", or "generic").
            api_key: Secret API key if required by provider (never logged).
            api_url: Custom base endpoint URL.
            timeout: Network request timeout in seconds.
        """
        self.provider_type = provider_type.lower()
        self.api_key = api_key
        # Only override default URL if api_url is explicitly provided for custom/searxng or matches provider
        if api_url and self.provider_type in ("searxng", "generic", "custom"):
            self.api_url = api_url
        elif api_url and self.provider_type not in ("wikipedia", "wiki", "duckduckgo", "ddg", "tavily", "serpapi"):
            self.api_url = api_url
        else:
            self.api_url = self._default_url(self.provider_type)
        self.timeout = timeout

    @staticmethod
    def _default_url(provider_type: str) -> str:
        defaults = {
            "wikipedia": "https://en.wikipedia.org/w/api.php",
            "wiki": "https://en.wikipedia.org/w/api.php",
            "duckduckgo": "https://html.duckduckgo.com/html/",
            "ddg": "https://html.duckduckgo.com/html/",
            "searxng": "http://localhost:8080/search",
            "serpapi": "https://serpapi.com/search",
            "tavily": "https://api.tavily.com/search",
            "generic": "http://localhost:8080/search",
        }
        return defaults.get(provider_type, "https://html.duckduckgo.com/html/")

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Execute query against configured external search service.

        Args:
            query: The search query string.
            limit: Maximum candidate results to retrieve.

        Returns:
            list[SearchResult]: Normalized candidate search results.
        """
        logger.info(f"Executing external search [{self.provider_type}] for query: '{query}'")

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                if self.provider_type in ("wikipedia", "wiki"):
                    return await self._search_wikipedia(client, query, limit)
                elif self.provider_type in ("duckduckgo", "ddg"):
                    return await self._search_duckduckgo(client, query, limit)
                elif self.provider_type == "tavily":
                    return await self._search_tavily(client, query, limit)
                elif self.provider_type == "serpapi":
                    return await self._search_serpapi(client, query, limit)
                else:
                    # Default: SearXNG / generic REST API
                    return await self._search_searxng(client, query, limit)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutException(
                f"External search request timed out after {self.timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SearchProviderException(
                f"External search API returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise SearchProviderException(
                f"Failed to connect to external search API: {type(exc).__name__}"
            ) from exc

    async def _search_wikipedia(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[SearchResult]:
        """Query official Wikipedia open search API without requiring API keys."""
        params: dict[str, Any] = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": limit,
        }
        headers = {"User-Agent": "SIRIS-OSINT-Component/0.1 (investigation-test@example.org)"}
        url = self.api_url or "https://en.wikipedia.org/w/api.php"
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        results: list[SearchResult] = []
        raw_items = data.get("query", {}).get("search", [])
        for item in raw_items[:limit]:
            title = item.get("title", "")
            slug = title.replace(" ", "_")
            article_url = f"https://en.wikipedia.org/wiki/{slug}"
            raw_snippet = item.get("snippet", "")
            clean_snippet = re.sub(r"<[^>]+>", "", raw_snippet) if raw_snippet else None
            results.append(
                SearchResult(
                    title=title,
                    url=article_url,
                    source="en.wikipedia.org",
                    snippet=clean_snippet,
                )
            )
        return results

    async def _search_duckduckgo(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[SearchResult]:
        """Query DuckDuckGo HTML endpoint without requiring API keys."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        url = self.api_url or "https://html.duckduckgo.com/html/"
        response = await client.post(url, data={"q": query}, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []

        for el in soup.select(".result__body"):
            if len(results) >= limit:
                break
            a = el.select_one(".result__a")
            if not a:
                continue
            title = a.get_text(strip=True)
            raw_url = a.get("href", "")
            if "uddg=" in raw_url:
                parsed = urlparse(raw_url)
                target_url = parse_qs(parsed.query).get("uddg", [raw_url])[0]
            else:
                target_url = raw_url

            if target_url and title and is_valid_url(target_url):
                snippet_tag = el.select_one(".result__snippet")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else None
                source = extract_domain(target_url)
                results.append(
                    SearchResult(
                        title=title,
                        url=target_url,
                        source=source,
                        snippet=snippet,
                    )
                )
        return results

    async def _search_searxng(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[SearchResult]:
        """Query a SearXNG instance."""
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "categories": "news,general",
        }
        headers = {"User-Agent": "SIRIS-OSINT-Component/0.1"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = self.api_url.rstrip("/")
        if not url.endswith("/search"):
            url = f"{url}/search"

        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        results: list[SearchResult] = []
        raw_items = data.get("results", [])
        for item in raw_items[:limit]:
            url = item.get("url")
            title = item.get("title")
            if url and title and is_valid_url(url):
                source = item.get("engine") or extract_domain(url)
                snippet = item.get("content")
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        source=source,
                        snippet=snippet,
                    )
                )
        return results

    async def _search_serpapi(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[SearchResult]:
        """Query SerpAPI (Google/Bing/News)."""
        if not self.api_key:
            raise SearchProviderException("SerpAPI requires SEARCH_API_KEY to be configured")

        params: dict[str, Any] = {
            "q": query,
            "api_key": self.api_key,
            "num": limit,
        }
        response = await client.get(self.api_url, params=params)
        response.raise_for_status()
        data = response.json()

        results: list[SearchResult] = []
        organic = data.get("organic_results", [])
        news = data.get("news_results", [])
        combined = news + organic

        for item in combined[:limit]:
            url = item.get("link")
            title = item.get("title")
            if url and title and is_valid_url(url):
                source = item.get("source") or extract_domain(url)
                snippet = item.get("snippet")
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        source=source,
                        snippet=snippet,
                    )
                )
        return results

    async def _search_tavily(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[SearchResult]:
        """Query Tavily search API."""
        if not self.api_key:
            raise SearchProviderException("Tavily requires SEARCH_API_KEY to be configured")

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": limit,
            "include_domains": [],
            "search_depth": "basic",
        }
        response = await client.post(self.api_url, json=payload)
        response.raise_for_status()
        data = response.json()

        results: list[SearchResult] = []
        raw_items = data.get("results", [])
        for item in raw_items[:limit]:
            url = item.get("url")
            title = item.get("title")
            if url and title and is_valid_url(url):
                source = extract_domain(url)
                snippet = item.get("content")
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        source=source,
                        snippet=snippet,
                    )
                )
        return results
