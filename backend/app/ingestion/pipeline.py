"""
Full ingestion pipeline: Extract → Chunk → Enrich → Store.
Orchestrates the entire document processing flow.
"""
import uuid
import logging

from app.models.schemas import DocumentChunk, FileType, IngestResponse
from app.ingestion.extractor import detect_file_type, extract_structured, extract_unstructured
from app.ingestion.chunker import chunk_structured_data, chunk_unstructured_data
from app.ingestion.enrichment import generate_embeddings, extract_key_phrases_and_entities
from app.ingestion.storage import store_in_search, store_in_neo4j

logger = logging.getLogger(__name__)

STRUCTURED_TYPES = {FileType.CSV, FileType.XLSX, FileType.JSON}
UNSTRUCTURED_TYPES = {FileType.PDF, FileType.DOCX, FileType.IMAGE}

# Minimum text length to warrant embedding + AI Search storage
MIN_TEXT_LENGTH_FOR_EMBEDDING = 50


async def ingest_document(file_bytes: bytes, filename: str) -> IngestResponse:
    """Full pipeline: file → extraction → chunking → enrichment → storage."""
    document_id = str(uuid.uuid4())
    file_type = detect_file_type(filename)

    # Step 1: Extract
    if file_type in STRUCTURED_TYPES:
        records = await extract_structured(file_bytes, filename, file_type)
        # Step 2: Chunk (rows → parent/child chunks)
        chunks = chunk_structured_data(records, filename, file_type)
    else:
        extracted = await extract_unstructured(file_bytes, filename, file_type)
        # Step 2: Chunk (semantic + structure-aware)
        chunks = chunk_unstructured_data(extracted, filename, file_type)

    # Split chunks: meaningful text gets full enrichment, short/empty go to Neo4j only
    rich_chunks = [c for c in chunks if len(c.text.strip()) >= MIN_TEXT_LENGTH_FOR_EMBEDDING]
    thin_chunks = [c for c in chunks if len(c.text.strip()) < MIN_TEXT_LENGTH_FOR_EMBEDDING]

    logger.info(f"Processing {filename}: {len(rich_chunks)} rich chunks, {len(thin_chunks)} thin chunks")

    # Step 3: Enrich rich chunks — key phrases, entities, embeddings
    if rich_chunks:
        rich_chunks = await extract_key_phrases_and_entities(rich_chunks)
        rich_chunks = await generate_embeddings(rich_chunks)

    # Step 4a: Store rich chunks in BOTH AI Search and Neo4j
    if rich_chunks:
        await store_in_search(rich_chunks)
        await store_in_neo4j(rich_chunks, document_id, filename)

    # Step 4b: Store thin chunks in Neo4j ONLY (no embeddings, no AI Search)
    if thin_chunks:
        await store_in_neo4j(thin_chunks, document_id, filename)

    all_chunks = rich_chunks + thin_chunks
    total_entities = sum(len(c.metadata.entities) for c in all_chunks)

    return IngestResponse(
        document_id=document_id,
        file_name=filename,
        file_type=file_type,
        total_chunks=len(all_chunks),
        entities_extracted=total_entities,
        message=(
            f"Successfully ingested {filename}: {len(all_chunks)} total chunks "
            f"({len(rich_chunks)} searchable, {len(thin_chunks)} graph-only), "
            f"{total_entities} entities"
        ),
    )
