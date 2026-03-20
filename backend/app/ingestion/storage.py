"""
Storage layer: Azure AI Search (hybrid index) + Neo4j (graph + temporal).
"""
import json
from datetime import datetime, timezone

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from neo4j import GraphDatabase

from app.config import settings
from app.models.schemas import DocumentChunk


# ─── Azure AI Search ─────────────────────────────────────────────────────────

def _get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=settings.SEARCH_ENDPOINT,
        index_name=settings.SEARCH_INDEX,
        credential=AzureKeyCredential(settings.SEARCH_KEY),
    )


def _get_index_client() -> SearchIndexClient:
    return SearchIndexClient(
        endpoint=settings.SEARCH_ENDPOINT,
        credential=AzureKeyCredential(settings.SEARCH_KEY),
    )


def ensure_search_index():
    """Create the AI Search index if it doesn't exist."""
    client = _get_index_client()
    index_name = settings.SEARCH_INDEX

    try:
        client.get_index(index_name)
        return  # Already exists
    except Exception:
        pass

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="text", type=SearchFieldDataType.String),
        SearchableField(name="contextual_prefix", type=SearchFieldDataType.String),
        SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="file_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="section_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="parent_chunk_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, sortable=True),
        SearchableField(name="heading_path", type=SearchFieldDataType.String),
        SearchableField(name="key_phrases", type=SearchFieldDataType.String),
        SimpleField(name="entities_json", type=SearchFieldDataType.String),
        SimpleField(name="ingested_at", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=512,
            vector_search_profile_name="default-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw", parameters={"metric": "cosine"})],
        profiles=[VectorSearchProfile(name="default-vector-profile", algorithm_configuration_name="default-hnsw")],
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    client.create_index(index)


async def store_in_search(chunks: list[DocumentChunk]):
    """Upload chunks to Azure AI Search."""
    ensure_search_index()
    client = _get_search_client()
    now = datetime.now(timezone.utc).isoformat()

    documents = []
    for chunk in chunks:
        doc = {
            "id": chunk.id,
            "text": chunk.text,
            "contextual_prefix": chunk.metadata.contextual_prefix,
            "source_file": chunk.metadata.source_file,
            "file_type": chunk.metadata.file_type.value,
            "section_type": chunk.metadata.section_type or "",
            "parent_chunk_id": chunk.metadata.parent_chunk_id or "",
            "chunk_index": chunk.metadata.chunk_index,
            "heading_path": " > ".join(chunk.metadata.heading_path),
            "key_phrases": ", ".join(chunk.metadata.key_phrases),
            "entities_json": json.dumps(chunk.metadata.entities),
            "ingested_at": now,
            "embedding": chunk.embedding,
        }
        documents.append(doc)

    # Upload in batches of 100
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        client.upload_documents(documents=batch)


# ─── Neo4j ────────────────────────────────────────────────────────────────────

def _get_neo4j_driver():
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )


async def store_in_neo4j(chunks: list[DocumentChunk], document_id: str, filename: str):
    """Store document graph in Neo4j: Document → Chunks → Entities with temporal edges."""
    driver = _get_neo4j_driver()
    now = datetime.now(timezone.utc).isoformat()

    with driver.session() as session:
        # Create Document node
        session.run(
            """
            MERGE (d:Document {id: $doc_id})
            SET d.filename = $filename, d.ingested_at = $now
            """,
            doc_id=document_id, filename=filename, now=now,
        )

        for chunk in chunks:
            # Create Chunk node
            session.run(
                """
                MERGE (c:Chunk {id: $chunk_id})
                SET c.text = $text,
                    c.section_type = $section_type,
                    c.chunk_index = $chunk_index,
                    c.contextual_prefix = $prefix,
                    c.ingested_at = $now
                WITH c
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:CONTAINS]->(c)
                """,
                chunk_id=chunk.id,
                text=chunk.text[:1000],  # Store truncated text in graph (full text in Search)
                section_type=chunk.metadata.section_type or "",
                chunk_index=chunk.metadata.chunk_index,
                prefix=chunk.metadata.contextual_prefix,
                now=now,
                doc_id=document_id,
            )

            # Parent-child relationships
            if chunk.metadata.parent_chunk_id:
                session.run(
                    """
                    MATCH (parent:Chunk {id: $parent_id})
                    MATCH (child:Chunk {id: $child_id})
                    MERGE (parent)-[:HAS_CHILD]->(child)
                    """,
                    parent_id=chunk.metadata.parent_chunk_id,
                    child_id=chunk.id,
                )

            # Entity nodes + relationships
            for entity in chunk.metadata.entities:
                session.run(
                    """
                    MERGE (e:Entity {text: $text, category: $category})
                    WITH e
                    MATCH (c:Chunk {id: $chunk_id})
                    MERGE (c)-[:MENTIONS {confidence: $confidence}]->(e)
                    """,
                    text=entity["text"],
                    category=entity["category"],
                    chunk_id=chunk.id,
                    confidence=entity.get("confidence", 0.0),
                )

    driver.close()
