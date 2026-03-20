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
    """Generate a structured report from ingested documents."""
    results, _ = await retrieve(
        query=request.query,
        top_k=20,  # More context for reports
        use_multi_query=True,
        use_query_expansion=True,
        file_filter=request.file_filter,
    )

    if not results:
        raise HTTPException(status_code=404, detail="No relevant documents found")

    report = await generate_report(request.query, results, request.report_type)
    return report


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
