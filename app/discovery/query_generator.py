"""Deterministic search query generator for target individuals.

Converts known intelligence about a target person into high-signal search queries
without external network or framework dependencies.
"""

import re
from app.models.schemas import TargetPerson


class QueryGenerator:
    """Generates prioritized, deterministic search queries from a TargetPerson."""

    def generate(self, target: TargetPerson) -> list[str]:
        """Generate a deterministic, prioritized list of search queries for a target person.

        Args:
            target: TargetPerson instance with known attributes.

        Returns:
            list[str]: Deduplicated, normalized search query strings in priority order.
        """
        raw_queries: list[str] = []

        name = self._normalize_whitespace(target.name)
        location = self._normalize_whitespace(target.location) if target.location else None
        organization = self._normalize_whitespace(target.organization) if target.organization else None

        # 1. Primary Name & Context Queries
        raw_queries.extend(self._generate_name_queries(name, location, organization))

        # 2. Alias Queries
        if target.aliases:
            raw_queries.extend(self._generate_alias_queries(target.aliases, location, organization))

        # 3. Username Queries (Extension Hook)
        if target.username:
            raw_queries.extend(self._generate_username_queries(name, target.username))

        # 4. Phone Queries (Extension Hook)
        if target.phone:
            raw_queries.extend(self._generate_phone_queries(name, target.phone))

        # 5. Contextual Keyword Queries (Extension Hook)
        if target.keywords:
            raw_queries.extend(self._generate_keyword_queries(name, target.keywords, location))

        # Deduplicate while strictly preserving insertion order
        normalized_queries: list[str] = []
        for q in raw_queries:
            clean_q = self._normalize_whitespace(q)
            if clean_q and clean_q not in normalized_queries:
                normalized_queries.append(clean_q)

        return normalized_queries

    def _generate_name_queries(
        self,
        name: str,
        location: str | None,
        organization: str | None,
    ) -> list[str]:
        """Generate primary name queries in priority order."""
        queries: list[str] = []

        # Query 1 — Exact name
        queries.append(f'"{name}"')

        # Query 2 — Name + location
        if location:
            queries.append(f'"{name}" {location}')

        # Query 3 — Name + organization
        if organization:
            queries.append(f'"{name}" "{organization}"')

        # Query 4 — Name + location + organization
        if location and organization:
            queries.append(f'"{name}" {location} "{organization}"')

        return queries

    def _generate_alias_queries(
        self,
        aliases: list[str],
        location: str | None,
        organization: str | None,
    ) -> list[str]:
        """Generate alias queries with context."""
        queries: list[str] = []
        for raw_alias in aliases:
            alias = self._normalize_whitespace(raw_alias)
            if not alias:
                continue

            # Standalone alias
            queries.append(f'"{alias}"')

            # Contextual alias with location
            if location:
                queries.append(f'"{alias}" {location}')

            # Contextual alias with organization
            if organization:
                queries.append(f'"{alias}" "{organization}"')

            # Contextual alias with both location and organization
            if location and organization:
                queries.append(f'"{alias}" {location} "{organization}"')

        return queries

    def _generate_username_queries(self, name: str, username: str) -> list[str]:
        """Generate queries targeting online handles and usernames."""
        clean_user = self._normalize_whitespace(username).lstrip("@")
        if not clean_user:
            return []

        return [
            f'"{clean_user}"',
            f'"{name}" "{clean_user}"',
        ]

    def _generate_phone_queries(self, name: str, phone: str) -> list[str]:
        """Generate queries targeting phone numbers."""
        clean_phone = self._normalize_whitespace(phone)
        if not clean_phone:
            return []

        return [
            f'"{clean_phone}"',
            f'"{name}" "{clean_phone}"',
        ]

    def _generate_keyword_queries(
        self,
        name: str,
        keywords: list[str],
        location: str | None = None,
    ) -> list[str]:
        """Generate contextual keyword queries."""
        queries: list[str] = []
        for raw_kw in keywords:
            kw = self._normalize_whitespace(raw_kw)
            if kw:
                queries.append(f'"{name}" {kw}')
                if location:
                    queries.append(f'"{name}" {location} {kw}')
        return queries

    @staticmethod
    def _normalize_whitespace(text: str | None) -> str:
        """Collapse multiple whitespace characters into a single space and strip edges."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()
