from pydantic import BaseModel
from enum import Enum


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    IMAGE = "image"  # JPEG, PNG, etc.


class ChunkMetadata(BaseModel):
    source_file: str
    file_type: FileType
    chunk_index: int
    parent_chunk_id: str | None = None
    section_type: str | None = None  # "table", "summary", "detail", "row"
    heading_path: list[str] = []
    contextual_prefix: str = ""
    key_phrases: list[str] = []
    entities: list[dict] = []
    timestamp: str | None = None


class DocumentChunk(BaseModel):
    id: str
    text: str
    embedding: list[float] = []
    metadata: ChunkMetadata


class IngestResponse(BaseModel):
    document_id: str
    file_name: str
    file_type: FileType
    total_chunks: int
    entities_extracted: int
    message: str


class QueryRequest(BaseModel):
    query: str
    use_multi_query: bool = True
    use_query_expansion: bool = True
    top_k: int = 10
    file_filter: str | None = None


class QueryResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    source_file: str
    section_type: str | None = None
    heading_path: list[str] = []
    contextual_prefix: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: list[QueryResult]
    queries_used: list[str]


class ReportRequest(BaseModel):
    query: str
    report_type: str = "summary"  # "summary", "categorization", "trend", "comparison"
    file_filter: str | None = None


class ReportSection(BaseModel):
    title: str
    content: str
    chart_data: dict | None = None
    table_data: list[dict] | None = None


class ReportResponse(BaseModel):
    title: str
    summary: str
    sections: list[ReportSection]
    total_documents_analyzed: int
