"""Extraction service coordinating deterministic document extraction."""

import time
from app.acquisition.models import WebDocument
from app.extraction.errors import EXTRACTION_FAILED, INVALID_DOCUMENT, ExtractionException
from app.extraction.extractor import ContentExtractor, DeterministicHtmlExtractor
from app.extraction.models import ExtractionError, ExtractionResult
from app.logging_config import logger


class ExtractionService:
    """Service coordinating deterministic extraction of acquired WebDocuments without network access."""

    def __init__(self, extractor: ContentExtractor | None = None):
        self.extractor = extractor or DeterministicHtmlExtractor()

    def extract(self, web_document: WebDocument) -> ExtractionResult:
        """Extract structured content from an authoritative WebDocument.

        Args:
            web_document: WebDocument acquired during Phase 3.

        Returns:
            ExtractionResult: Structured extraction result (success with ExtractedDocument, or controlled failure).
        """
        start = time.perf_counter()
        if not web_document or not isinstance(web_document, WebDocument):
            logger.warning("Extraction requested on invalid or null WebDocument")
            return ExtractionResult(
                success=False,
                document=None,
                error=ExtractionError(
                    code=INVALID_DOCUMENT,
                    message="Invalid WebDocument provided for extraction.",
                    retryable=False,
                ),
            )

        url = web_document.final_url or web_document.requested_url
        logger.info(f"extraction_started: target='{url}' hash='{web_document.content_hash[:10]}...'")

        try:
            doc = self.extractor.extract(web_document)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                f"extraction_completed: target='{url}' words={doc.word_count} "
                f"quality={doc.content_quality} duration={duration_ms:.1f}ms"
            )
            return ExtractionResult(
                success=True,
                document=doc,
                error=None,
            )
        except ExtractionException as err:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                f"extraction_failed: target='{url}' code={err.code} msg='{err.message}' duration={duration_ms:.1f}ms"
            )
            return ExtractionResult(
                success=False,
                document=None,
                error=ExtractionError(
                    code=err.code,
                    message=err.message,
                    retryable=err.retryable,
                    details=err.details,
                ),
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"extraction_failed: target='{url}' unexpected error={exc} duration={duration_ms:.1f}ms",
                exc_info=True,
            )
            return ExtractionResult(
                success=False,
                document=None,
                error=ExtractionError(
                    code=EXTRACTION_FAILED,
                    message=f"Extraction failed due to an internal error: {exc}",
                    retryable=False,
                ),
            )
