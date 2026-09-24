"""Entity extraction service coordinating extraction, occurrence tracking, and provenance."""

import time
from app.entity_extraction.errors import (
    EMPTY_DOCUMENT,
    ENTITY_EXTRACTION_FAILED,
    INVALID_DOCUMENT,
    EntityExtractionException,
)
from app.entity_extraction.extractor import DeterministicEntityExtractor, EntityExtractor
from app.entity_extraction.models import (
    EntityExtractionError,
    EntityExtractionMetrics,
    EntityExtractionResult,
    EntityOccurrence,
    ExtractedEntity,
    UniqueEntity,
)
from app.entity_extraction.taxonomy import EntityType
from app.extraction.models import ExtractedDocument
from app.logging_config import logger


class EntityExtractionService:
    """Service coordinating entity extraction from ExtractedDocuments.

    Enforces strict architectural boundaries:
    - Zero target-resolution or identity matching.
    - Zero network access or runtime downloads.
    - Preserves document content_hash provenance and offsets.
    """

    def __init__(self, extractor: EntityExtractor | None = None):
        self.extractor = extractor or DeterministicEntityExtractor()

    def extract(self, document: ExtractedDocument) -> EntityExtractionResult:
        """Extract identifiable entities and track occurrences from an ExtractedDocument.

        Args:
            document: ExtractedDocument produced during Phase 4.

        Returns:
            EntityExtractionResult: Structured result with entities, unique occurrences, counts, and metrics.
        """
        start = time.perf_counter()

        # 1. Validate document input
        if not document or not isinstance(document, ExtractedDocument):
            logger.warning("Entity extraction requested on invalid or null ExtractedDocument")
            return EntityExtractionResult(
                success=False,
                document_hash=None,
                source_url=None,
                entities=[],
                unique_entities=[],
                entity_count=0,
                mention_count=0,
                unique_entity_count=0,
                counts_by_type={},
                warnings=["Invalid ExtractedDocument provided."],
                error=EntityExtractionError(
                    code=INVALID_DOCUMENT,
                    message="Invalid ExtractedDocument provided for entity extraction.",
                    retryable=False,
                ),
            )

        doc_hash = document.content_hash
        source_url = document.final_url or document.requested_url
        raw_text = document.text or ""

        # 2. Check for empty or whitespace-only document
        if not raw_text.strip():
            logger.info(f"entity_extraction_skipped: empty text for doc_hash='{doc_hash[:10]}...'")
            return EntityExtractionResult(
                success=False,
                document_hash=doc_hash,
                source_url=source_url,
                entities=[],
                unique_entities=[],
                entity_count=0,
                mention_count=0,
                unique_entity_count=0,
                counts_by_type={},
                warnings=["The document contains no text for entity extraction."],
                error=EntityExtractionError(
                    code=EMPTY_DOCUMENT,
                    message="The provided document contains no extractable text.",
                    retryable=False,
                ),
            )

        logger.info(f"entity_extraction_started: target='{source_url}' hash='{doc_hash[:10]}...'")

        try:
            # 3. Perform extraction
            entities = self.extractor.extract(document)

            # 4. Group into UniqueEntity records and track occurrences
            unique_map: dict[tuple[EntityType, str], list[EntityOccurrence]] = {}
            counts_by_type: dict[str, int] = {}

            for ent in entities:
                # Track type count (total mentions)
                type_key = ent.type.value if hasattr(ent.type, "value") else str(ent.type)
                counts_by_type[type_key] = counts_by_type.get(type_key, 0) + 1

                # Group by (type, normalized_text)
                group_key = (ent.type, ent.normalized_text)
                occ = EntityOccurrence(
                    text=ent.text,
                    start_offset=ent.start_offset,
                    end_offset=ent.end_offset,
                    sentence=ent.sentence,
                    confidence=ent.confidence,
                )
                if group_key not in unique_map:
                    unique_map[group_key] = []
                unique_map[group_key].append(occ)

            unique_entities = [
                UniqueEntity(
                    type=k[0],
                    normalized_text=k[1],
                    count=len(occs),
                    occurrences=occs,
                )
                for k, occs in unique_map.items()
            ]

            mention_count = len(entities)
            unique_count = len(unique_entities)
            duration_ms = (time.perf_counter() - start) * 1000

            metrics = EntityExtractionMetrics(
                character_count=len(raw_text),
                word_count=len(raw_text.split()),
                mention_count=mention_count,
                unique_entity_count=unique_count,
                duration_ms=round(duration_ms, 2),
            )

            logger.info(
                f"entity_extraction_completed: mentions={mention_count} unique={unique_count} "
                f"duration={duration_ms:.1f}ms"
            )

            return EntityExtractionResult(
                success=True,
                document_hash=doc_hash,
                source_url=source_url,
                entities=entities,
                unique_entities=unique_entities,
                entity_count=mention_count,
                mention_count=mention_count,
                unique_entity_count=unique_count,
                counts_by_type=counts_by_type,
                warnings=[],
                error=None,
                metrics=metrics,
            )

        except EntityExtractionException as err:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                f"entity_extraction_failed: code={err.code} msg='{err.message}' duration={duration_ms:.1f}ms"
            )
            return EntityExtractionResult(
                success=False,
                document_hash=doc_hash,
                source_url=source_url,
                entities=[],
                unique_entities=[],
                entity_count=0,
                mention_count=0,
                unique_entity_count=0,
                counts_by_type={},
                warnings=[],
                error=EntityExtractionError(
                    code=err.code,
                    message=err.message,
                    retryable=err.retryable,
                    details=err.details,
                ),
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"entity_extraction_failed: unexpected error={exc} duration={duration_ms:.1f}ms",
                exc_info=True,
            )
            return EntityExtractionResult(
                success=False,
                document_hash=doc_hash,
                source_url=source_url,
                entities=[],
                unique_entities=[],
                entity_count=0,
                mention_count=0,
                unique_entity_count=0,
                counts_by_type={},
                warnings=[],
                error=EntityExtractionError(
                    code=ENTITY_EXTRACTION_FAILED,
                    message=f"Entity extraction failed due to an internal error: {exc}",
                    retryable=False,
                ),
            )
