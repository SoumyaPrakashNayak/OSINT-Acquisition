"""Mock entity extractor for deterministic and isolated unit testing."""

from app.entity_extraction.models import ExtractedEntity
from app.extraction.models import ExtractedDocument


class MockEntityExtractor:
    """Mock extractor providing pre-configured deterministic entity results without ML or network calls."""

    def __init__(
        self,
        default_entities: list[ExtractedEntity] | None = None,
        raise_exception: Exception | None = None,
    ):
        self.default_entities = default_entities or []
        self.raise_exception = raise_exception
        self._doc_mappings: dict[str, list[ExtractedEntity]] = {}

    def register_document_entities(self, text_or_hash: str, entities: list[ExtractedEntity]) -> None:
        """Register specific entities to return when a matching document text or content_hash is seen."""
        self._doc_mappings[text_or_hash] = entities

    def extract(self, document: ExtractedDocument) -> list[ExtractedEntity]:
        """Extract mock entities for the given ExtractedDocument."""
        if self.raise_exception:
            raise self.raise_exception

        # Check for registered matches by content_hash or text
        if document.content_hash in self._doc_mappings:
            return self._doc_mappings[document.content_hash]
        if document.text in self._doc_mappings:
            return self._doc_mappings[document.text]

        # Otherwise return default configured entities, ensuring provenance matches the document
        results: list[ExtractedEntity] = []
        for ent in self.default_entities:
            # Rebind provenance to the active document
            results.append(
                ExtractedEntity(
                    id=ent.id,
                    type=ent.type,
                    text=ent.text,
                    normalized_text=ent.normalized_text,
                    start_offset=ent.start_offset,
                    end_offset=ent.end_offset,
                    sentence=ent.sentence,
                    confidence=ent.confidence,
                    source_document_hash=document.content_hash,
                    source_url=document.final_url or document.requested_url,
                )
            )
        return results
