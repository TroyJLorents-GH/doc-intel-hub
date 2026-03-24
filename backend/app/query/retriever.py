"""
Hybrid retriever: Azure AI Search (BM25 + vector) + Neo4j graph traversal.
Supports Multi-Query RAG with deduplication and RRF fusion.
"""
import asyncio
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from neo4j import GraphDatabase
from openai import AzureOpenAI

from app.config import settings
from app.models.schemas import QueryResult
from app.query.expansion import expand_query, generate_multi_queries


def _get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=settings.SEARCH_ENDPOINT,
        index_name=settings.SEARCH_INDEX,
        credential=AzureKeyCredential(settings.SEARCH_KEY),
    )


def _get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.OPENAI_ENDPOINT,
        api_key=settings.OPENAI_KEY,
        api_version="2024-10-21",
    )


def _get_neo4j_driver():
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )


def _embed_query(query: str) -> list[float]:
    client = _get_openai_client()
    response = client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_DEPLOYMENT,
        input=[query],
        dimensions=512,
    )
    return response.data[0].embedding


def _search_hybrid(query: str, query_embedding: list[float], top_k: int = 10, file_filter: str | None = None) -> list[QueryResult]:
    """Run hybrid BM25 + vector search on Azure AI Search."""
    client = _get_search_client()

    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields="embedding",
    )

    filter_expr = None
    if file_filter:
        filter_expr = f"source_file eq '{file_filter}'"

    results = client.search(
        search_text=query,
        vector_queries=[vector_query],
        top=top_k,
        filter=filter_expr,
        select=["id", "text", "source_file", "section_type", "heading_path", "contextual_prefix", "key_phrases"],
    )

    query_results = []
    for result in results:
        query_results.append(QueryResult(
            chunk_id=result["id"],
            text=result["text"],
            score=result["@search.score"],
            source_file=result["source_file"],
            section_type=result.get("section_type"),
            heading_path=result.get("heading_path", "").split(" > ") if result.get("heading_path") else [],
            contextual_prefix=result.get("contextual_prefix", ""),
        ))

    return query_results


def _search_neo4j_entities(query: str, top_k: int = 10) -> list[QueryResult]:
    """Search Neo4j for entity-connected chunks."""
    driver = _get_neo4j_driver()
    results = []

    with driver.session() as session:
        # Find entities matching the query, then traverse to chunks
        records = session.run(
            """
            CALL db.index.fulltext.queryNodes('entity_text', $query)
            YIELD node, score
            WITH node AS entity, score
            MATCH (c:Chunk)-[:MENTIONS]->(entity)
            MATCH (d:Document)-[:CONTAINS]->(c)
            RETURN c.id AS chunk_id, c.text AS text, score,
                   d.filename AS source_file, c.section_type AS section_type,
                   c.contextual_prefix AS contextual_prefix
            ORDER BY score DESC
            LIMIT $top_k
            """,
            query=query, top_k=top_k,
        )
        for record in records:
            results.append(QueryResult(
                chunk_id=record["chunk_id"],
                text=record["text"],
                score=record["score"],
                source_file=record["source_file"],
                section_type=record.get("section_type"),
                contextual_prefix=record.get("contextual_prefix", ""),
            ))

    driver.close()
    return results


def _reciprocal_rank_fusion(result_lists: list[list[QueryResult]], k: int = 60) -> list[QueryResult]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    chunk_map: dict[str, QueryResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results):
            rrf_score = 1.0 / (k + rank + 1)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
            if result.chunk_id not in chunk_map:
                chunk_map[result.chunk_id] = result

    # Sort by fused score
    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    fused = []
    for cid in sorted_ids:
        result = chunk_map[cid]
        result.score = scores[cid]
        fused.append(result)

    return fused


async def retrieve(
    query: str,
    top_k: int = 10,
    use_multi_query: bool = True,
    use_query_expansion: bool = True,
    file_filter: str | None = None,
) -> tuple[list[QueryResult], list[str]]:
    """Full retrieval pipeline: expansion → multi-query → hybrid search → RRF fusion."""

    queries_used = [query]

    if use_query_expansion:
        expanded = expand_query(query)
        queries_used.append(expanded)

    if use_multi_query:
        multi_queries = generate_multi_queries(query)
        queries_used.extend(multi_queries[1:])  # Skip original (already in list)

    # Deduplicate queries
    queries_used = list(dict.fromkeys(queries_used))

    # Run all searches concurrently
    all_result_lists = []

    for q in queries_used:
        embedding = _embed_query(q)
        hybrid_results = _search_hybrid(q, embedding, top_k=top_k, file_filter=file_filter)
        all_result_lists.append(hybrid_results)

    # Also search Neo4j graph
    try:
        graph_results = _search_neo4j_entities(query, top_k=top_k)
        if graph_results:
            all_result_lists.append(graph_results)
    except Exception:
        pass  # Neo4j may not have fulltext index yet

    # Fuse all results with RRF
    fused = _reciprocal_rank_fusion(all_result_lists)

    return fused[:top_k], queries_used
