"""Entity taxonomy definitions for Phase 5 Named Entity Recognition (NER)."""

from enum import Enum


class EntityType(str, Enum):
    """Controlled, explicit entity taxonomy for the OSINT Intelligence Component.

    Only identifiable, explicitly mentioned entities are recognized.
    No target-resolution or intelligence conclusions are drawn at this layer.
    """

    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    DATE = "DATE"
    TIME = "TIME"
    MONEY = "MONEY"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    URL = "URL"

    # Additional supported types
    VEHICLE = "VEHICLE"
    FACILITY = "FACILITY"


# Descriptions of each entity type for documentation and provenance tracking
ENTITY_TYPE_DESCRIPTIONS: dict[EntityType, str] = {
    EntityType.PERSON: "Identifiable human beings explicitly mentioned by name or title.",
    EntityType.ORGANIZATION: "Companies, corporations, institutions, government bodies, police/intelligence agencies, or universities.",
    EntityType.LOCATION: "Named geographical entities, cities, states, provinces, regions, and countries.",
    EntityType.DATE: "Explicit calendar dates, ISO dates, named months, and days of the week.",
    EntityType.TIME: "Explicit times of day with standard 12-hour or 24-hour markers.",
    EntityType.MONEY: "Explicit monetary values and currency representations.",
    EntityType.PHONE: "Telephone or mobile phone numbers matching standard country formats.",
    EntityType.EMAIL: "Electronic mail addresses embedded within text content.",
    EntityType.URL: "Web URLs and hyperlinks directly referenced in body text.",
    EntityType.VEHICLE: "Identifiable vehicles, registration numbers, or vessel identifiers.",
    EntityType.FACILITY: "Buildings, airports, ports, monuments, or physical infrastructure.",
}


def is_valid_entity_type(type_name: str) -> bool:
    """Check whether a given string is a recognized EntityType in the taxonomy."""
    try:
        EntityType(type_name)
        return True
    except ValueError:
        return False
