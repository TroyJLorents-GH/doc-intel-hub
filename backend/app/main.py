"""
Doc Intel Hub — FastAPI backend.
Multi-format document ingestion, agentic RAG, and report generation.
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schemas import (
    IngestResponse,
    QueryRequest,
    QueryResponse,
    QueryResult,
    ReportRequest,
    ReportResponse,
)
from app.ingestion.pipeline import ingest_document
from app.query.retriever import retrieve
from app.reports.generator import generate_report, chat_with_data

app = FastAPI(
    title="Doc Intel Hub",
    description="Multi-format document intelligence with Agentic RAG",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "doc-intel-hub"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    """Upload and process a document (PDF, DOCX, CSV, XLSX, JSON, image)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = {"pdf", "docx", "csv", "xlsx", "json", "jpg", "jpeg", "png", "tiff", "bmp"}
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    result = await ingest_document(file_bytes, file.filename)
    return result


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Ask a question about ingested documents using Agentic RAG."""
    results, queries_used = await retrieve(
        query=request.query,
        top_k=request.top_k,
        use_multi_query=request.use_multi_query,
        use_query_expansion=request.use_query_expansion,
        file_filter=request.file_filter,
    )

    if not results:
        return QueryResponse(
            answer="No relevant documents found. Please upload documents first.",
            sources=[],
            queries_used=queries_used,
        )

    answer = await chat_with_data(request.query, results)

    return QueryResponse(
        answer=answer,
        sources=results,
        queries_used=queries_used,
    )


@app.post("/reports", response_model=ReportResponse)
async def reports(request: ReportRequest):
    """Generate a structured report from ingested documents.
    For categorization, scans ALL data via Neo4j instead of top-k search."""
    from neo4j import GraphDatabase

    # For categorization/summary reports, pull ALL relevant data from Neo4j
    # so the LLM sees the full dataset, not just top 20
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    # Extract key terms from the query to filter relevant rows
    query_lower = request.query.lower()
    neo4j_results = []

    with driver.session() as session:
        # Get total row count
        total_rows = session.run(
            "MATCH (d:Document)-[:CONTAINS]->(c:Chunk) WHERE c.section_type = 'row' RETURN count(c) AS total"
        ).single()["total"]

        # If query mentions a specific topic, filter for it
        filter_terms = []
        for term in ["linux", "windows", "access", "network", "vm", "virtual machine",
                      "install", "password", "email", "printer", "vpn", "software", "hardware",
                      "ssh", "vnc", "building", "location", "priority", "login", "request"]:
            if term in query_lower:
                filter_terms.append(term)

        if filter_terms:
            # Get count first, then decide strategy
            where_clause = " OR ".join([f"toLower(c.text) CONTAINS '{t}'" for t in filter_terms])
            count_result = session.run(
                f"""
                MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                WHERE c.section_type = 'row' AND ({where_clause})
                RETURN count(c) AS matched
                """
            ).single()["matched"]

            if count_result <= 200:
                # Small enough to send all rows to LLM
                records = session.run(
                    f"""
                    MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                    WHERE c.section_type = 'row' AND ({where_clause})
                    RETURN c.text AS text, c.id AS id, d.filename AS source_file
                    """
                )
                for r in records:
                    neo4j_results.append(QueryResult(
                        chunk_id=r["id"],
                        text=r["text"][:300],
                        score=1.0,
                        source_file=r["source_file"],
                    ))
            else:
                # Too many rows — send count + sample
                neo4j_results.append(QueryResult(
                    chunk_id="filter-stats",
                    text=f"TOTAL MATCHING TICKETS for '{', '.join(filter_terms)}': {count_result} out of {total_rows} total tickets.",
                    score=1.0,
                    source_file="Full Dataset Analysis",
                ))
                records = session.run(
                    f"""
                    MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                    WHERE c.section_type = 'row' AND ({where_clause})
                    RETURN c.text AS text, c.id AS id, d.filename AS source_file
                    LIMIT 150
                    """
                )
                for r in records:
                    neo4j_results.append(QueryResult(
                        chunk_id=r["id"],
                        text=r["text"][:300],
                        score=1.0,
                        source_file=r["source_file"],
                    ))
        else:
            # Broad query — get keyword counts across ALL data + a sample of rows
            stats = session.run(
                """
                MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                WHERE c.section_type = 'row'
                WITH c, toLower(c.text) AS t
                RETURN
                  count(c) AS total,
                  sum(CASE WHEN t CONTAINS 'linux' THEN 1 ELSE 0 END) AS linux,
                  sum(CASE WHEN t CONTAINS 'windows' THEN 1 ELSE 0 END) AS windows,
                  sum(CASE WHEN t CONTAINS 'access' THEN 1 ELSE 0 END) AS access_request,
                  sum(CASE WHEN t CONTAINS 'virtual machine' OR t CONTAINS ' vm ' THEN 1 ELSE 0 END) AS vm_issues,
                  sum(CASE WHEN t CONTAINS 'network' THEN 1 ELSE 0 END) AS network,
                  sum(CASE WHEN t CONTAINS 'password' OR t CONTAINS 'reset' THEN 1 ELSE 0 END) AS password_reset,
                  sum(CASE WHEN t CONTAINS 'install' THEN 1 ELSE 0 END) AS installation,
                  sum(CASE WHEN t CONTAINS 'email' OR t CONTAINS 'outlook' THEN 1 ELSE 0 END) AS email,
                  sum(CASE WHEN t CONTAINS 'printer' OR t CONTAINS 'print' THEN 1 ELSE 0 END) AS printing,
                  sum(CASE WHEN t CONTAINS 'vpn' THEN 1 ELSE 0 END) AS vpn,
                  sum(CASE WHEN t CONTAINS 'software' THEN 1 ELSE 0 END) AS software,
                  sum(CASE WHEN t CONTAINS 'hardware' THEN 1 ELSE 0 END) AS hardware,
                  sum(CASE WHEN t CONTAINS 'ssh' THEN 1 ELSE 0 END) AS ssh,
                  sum(CASE WHEN t CONTAINS 'vnc' THEN 1 ELSE 0 END) AS vnc,
                  sum(CASE WHEN t CONTAINS 'login' THEN 1 ELSE 0 END) AS login,
                  sum(CASE WHEN t CONTAINS 'incident' THEN 1 ELSE 0 END) AS incidents,
                  sum(CASE WHEN t CONTAINS 'task' THEN 1 ELSE 0 END) AS tasks,
                  sum(CASE WHEN t CONTAINS 'request' THEN 1 ELSE 0 END) AS requests,
                  sum(CASE WHEN t CONTAINS 'building' OR t CONTAINS 'bldg' OR t CONTAINS 'room' THEN 1 ELSE 0 END) AS has_location,
                  sum(CASE WHEN t CONTAINS 'p1' OR t CONTAINS 'p2' OR t CONTAINS 'p3' OR t CONTAINS 'p4' THEN 1 ELSE 0 END) AS has_priority
                """
            ).single()

            stats_text = f"""FULL DATASET STATISTICS (across all {total_rows} tickets):
Categories by keyword count:
- Linux: {stats['linux']}
- Windows: {stats['windows']}
- Access requests: {stats['access_request']}
- VM issues: {stats['vm_issues']}
- Network: {stats['network']}
- Password/Reset: {stats['password_reset']}
- Installation: {stats['installation']}
- Email/Outlook: {stats['email']}
- Printing: {stats['printing']}
- VPN: {stats['vpn']}
- Software: {stats['software']}
- Hardware: {stats['hardware']}
- SSH: {stats['ssh']}
- VNC: {stats['vnc']}
- Login: {stats['login']}
- Incidents: {stats['incidents']}
- Tasks: {stats['tasks']}
- Requests: {stats['requests']}
- Tickets with location/building info: {stats['has_location']}
- Tickets with priority level: {stats['has_priority']}
"""
            neo4j_results.append(QueryResult(
                chunk_id="dataset-stats",
                text=stats_text,
                score=1.0,
                source_file="Full Dataset Analysis",
            ))

            # Also get a diverse sample of 100 rows with meaningful content
            sample_records = session.run(
                """
                MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                WHERE c.section_type = 'row' AND size(c.text) > 50
                RETURN c.text AS text, c.id AS id, d.filename AS source_file
                LIMIT 100
                """
            )
            for r in sample_records:
                neo4j_results.append(QueryResult(
                    chunk_id=r["id"],
                    text=r["text"][:500],
                    score=1.0,
                    source_file=r["source_file"],
                ))

    driver.close()

    if not neo4j_results:
        raise HTTPException(status_code=404, detail="No relevant documents found")

    report = await generate_report(
        request.query,
        neo4j_results,
        request.report_type,
    )
    return report


@app.get("/analyze")
async def analyze_dataset():
    """Full dataset analysis: scan ALL rows in Neo4j and categorize by topic."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    with driver.session() as session:
        # Total counts
        total = session.run(
            "MATCH (d:Document)-[:CONTAINS]->(c:Chunk) WHERE c.section_type = 'row' RETURN count(c) AS total"
        ).single()["total"]

        # Category counts — scan ALL rows by keyword
        categories_result = session.run(
            """
            MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
            WHERE c.section_type = 'row'
            WITH c, toLower(c.text) AS t
            RETURN
              sum(CASE WHEN t CONTAINS 'linux' THEN 1 ELSE 0 END) AS linux,
              sum(CASE WHEN t CONTAINS 'windows' THEN 1 ELSE 0 END) AS windows,
              sum(CASE WHEN t CONTAINS 'access' THEN 1 ELSE 0 END) AS access_request,
              sum(CASE WHEN t CONTAINS 'virtual machine' OR t CONTAINS ' vm ' THEN 1 ELSE 0 END) AS vm_issues,
              sum(CASE WHEN t CONTAINS 'network' THEN 1 ELSE 0 END) AS network,
              sum(CASE WHEN t CONTAINS 'password' OR t CONTAINS 'reset' THEN 1 ELSE 0 END) AS password_reset,
              sum(CASE WHEN t CONTAINS 'install' THEN 1 ELSE 0 END) AS installation,
              sum(CASE WHEN t CONTAINS 'email' OR t CONTAINS 'outlook' THEN 1 ELSE 0 END) AS email,
              sum(CASE WHEN t CONTAINS 'printer' OR t CONTAINS 'print' THEN 1 ELSE 0 END) AS printing,
              sum(CASE WHEN t CONTAINS 'vpn' THEN 1 ELSE 0 END) AS vpn,
              sum(CASE WHEN t CONTAINS 'software' THEN 1 ELSE 0 END) AS software,
              sum(CASE WHEN t CONTAINS 'hardware' THEN 1 ELSE 0 END) AS hardware,
              sum(CASE WHEN t CONTAINS 'incident' THEN 1 ELSE 0 END) AS incidents,
              sum(CASE WHEN t CONTAINS 'catalog task' OR t CONTAINS 'task' THEN 1 ELSE 0 END) AS catalog_tasks,
              sum(CASE WHEN t CONTAINS 'request' THEN 1 ELSE 0 END) AS requests
            """
        ).single()

        categories = {k: v for k, v in dict(categories_result).items() if v > 0}

        # Top entities across all tickets
        entities_result = session.run(
            """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE c.section_type = 'row'
            RETURN e.category AS category, e.text AS entity, count(c) AS mentions
            ORDER BY mentions DESC
            LIMIT 30
            """
        )
        top_entities = [
            {"category": r["category"], "entity": r["entity"], "mentions": r["mentions"]}
            for r in entities_result
        ]

        # Sample Linux tickets
        linux_result = session.run(
            """
            MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
            WHERE c.section_type = 'row' AND toLower(c.text) CONTAINS 'linux'
            RETURN c.text AS text, c.chunk_index AS row
            ORDER BY c.chunk_index
            LIMIT 20
            """
        )
        linux_tickets = [{"row": r["row"], "text": r["text"][:300]} for r in linux_result]

    driver.close()

    return {
        "total_rows": total,
        "categories": categories,
        "top_entities": top_entities,
        "linux_tickets": linux_tickets,
    }


@app.get("/documents")
async def list_documents():
    """List all ingested documents from Neo4j."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    with driver.session() as session:
        records = session.run(
            """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
            RETURN d.id AS id, d.filename AS filename, d.ingested_at AS ingested_at,
                   count(c) AS chunk_count
            ORDER BY d.ingested_at DESC
            """
        )
        docs = [
            {
                "id": r["id"],
                "filename": r["filename"],
                "ingested_at": r["ingested_at"],
                "chunk_count": r["chunk_count"],
            }
            for r in records
        ]
    driver.close()
    return {"documents": docs}


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its chunks from Neo4j and AI Search."""
    from neo4j import GraphDatabase
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    # Get chunk IDs from Neo4j first
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    with driver.session() as session:
        records = session.run(
            "MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(c:Chunk) RETURN c.id AS chunk_id",
            doc_id=document_id,
        )
        chunk_ids = [r["chunk_id"] for r in records]

        # Delete from Neo4j (chunks, relationships, document)
        session.run(
            """
            MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(c:Chunk)
            OPTIONAL MATCH (c)-[r]-()
            DELETE r, c
            WITH d
            DELETE d
            """,
            doc_id=document_id,
        )
    driver.close()

    # Delete from AI Search
    if chunk_ids:
        search_client = SearchClient(
            endpoint=settings.SEARCH_ENDPOINT,
            index_name=settings.SEARCH_INDEX,
            credential=AzureKeyCredential(settings.SEARCH_KEY),
        )
        search_client.delete_documents(documents=[{"id": cid} for cid in chunk_ids])

    return {"message": f"Deleted document {document_id} and {len(chunk_ids)} chunks"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
