"""
Context-Aware Chunking + Contextual Retrieval + Hierarchical RAG.

For unstructured docs: uses semantic boundaries, headings, and structure.
For structured data (CSV rows): each row is a natural chunk, grouped into parent chunks.
"""
import uuid
import tiktoken
from openai import AzureOpenAI

from app.config import settings
from app.models.schemas import ChunkMetadata, DocumentChunk, FileType

# Target ~500 tokens per chunk, max 800
TARGET_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 800
OVERLAP_TOKENS = 50

_tokenizer = tiktoken.encoding_for_model("gpt-4o")


def _count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


def _get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.OPENAI_ENDPOINT,
        api_key=settings.OPENAI_KEY,
        api_version="2024-10-21",
    )


def _generate_contextual_prefix(chunk_text: str, full_document_text: str) -> str:
    """Anthropic's Contextual Retrieval: generate 1-2 sentences explaining
    what this chunk discusses in the context of the whole document."""
    client = _get_openai_client()
    # Truncate document context to avoid token limits
    doc_context = full_document_text[:4000]

    response = client.chat.completions.create(
        model=settings.OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a document analysis assistant. Given a chunk of a document and the "
                    "broader document context, write 1-2 concise sentences explaining what this "
                    "chunk discusses and how it relates to the overall document. Be specific and "
                    "include key terms that would help with search retrieval."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"DOCUMENT CONTEXT:\n{doc_context}\n\n"
                    f"CHUNK:\n{chunk_text}\n\n"
                    "Write 1-2 sentences of context for this chunk:"
                ),
            },
        ],
        max_tokens=150,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


def chunk_structured_data(
    records: list[dict], filename: str, file_type: FileType, batch_size: int = 20
) -> list[DocumentChunk]:
    """Chunk structured data (CSV/XLSX/JSON rows).
    Each row = child chunk. Groups of rows = parent chunks."""
    chunks = []
    full_text = "\n\n".join(r["text"] for r in records)

    # Create parent chunks (batches of rows)
    for batch_start in range(0, len(records), batch_size):
        batch = records[batch_start : batch_start + batch_size]
        parent_id = str(uuid.uuid4())
        parent_text = "\n\n".join(r["text"] for r in batch)

        parent_chunk = DocumentChunk(
            id=parent_id,
            text=parent_text,
            metadata=ChunkMetadata(
                source_file=filename,
                file_type=file_type,
                chunk_index=batch_start // batch_size,
                section_type="parent",
                heading_path=[f"Rows {batch_start + 1}-{batch_start + len(batch)}"],
            ),
        )
        chunks.append(parent_chunk)

        # Create child chunks (individual rows)
        # Skip contextual retrieval for structured data — column headers already provide context
        for record in batch:
            child_id = str(uuid.uuid4())
            columns = record.get("columns", [])
            contextual_prefix = f"Row from {filename} with columns: {', '.join(columns)}" if columns else ""

            child_chunk = DocumentChunk(
                id=child_id,
                text=record["text"],
                metadata=ChunkMetadata(
                    source_file=filename,
                    file_type=file_type,
                    chunk_index=record["index"],
                    parent_chunk_id=parent_id,
                    section_type="row",
                    heading_path=list(record.get("columns", [])),
                    contextual_prefix=contextual_prefix,
                ),
            )
            chunks.append(child_chunk)

    return chunks


def chunk_unstructured_data(
    extracted: dict, filename: str, file_type: FileType
) -> list[DocumentChunk]:
    """Chunk unstructured docs (PDF/DOCX/images) using token-aware splitting
    with heading detection and semantic boundaries."""
    full_text = extracted["content"]
    chunks = []

    # Split by double newlines first (natural paragraph boundaries)
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]

    current_chunk_parts: list[str] = []
    current_tokens = 0
    chunk_index = 0
    current_heading = []

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        # Detect headings (short lines, often uppercase or title case)
        is_heading = (
            para_tokens < 20
            and not para.endswith(".")
            and (para.isupper() or para.istitle() or para.endswith(":"))
        )

        if is_heading:
            # Flush current chunk before new section
            if current_chunk_parts:
                chunk_text = "\n\n".join(current_chunk_parts)
                parent_id = str(uuid.uuid4())
                contextual_prefix = _generate_contextual_prefix(chunk_text, full_text[:4000])

                chunks.append(DocumentChunk(
                    id=parent_id,
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        source_file=filename,
                        file_type=file_type,
                        chunk_index=chunk_index,
                        section_type="detail",
                        heading_path=list(current_heading),
                        contextual_prefix=contextual_prefix,
                    ),
                ))
                chunk_index += 1
                current_chunk_parts = []
                current_tokens = 0

            current_heading = [para]
            continue

        # Check if adding this paragraph exceeds max
        if current_tokens + para_tokens > MAX_CHUNK_TOKENS and current_chunk_parts:
            chunk_text = "\n\n".join(current_chunk_parts)
            chunk_id = str(uuid.uuid4())
            contextual_prefix = _generate_contextual_prefix(chunk_text, full_text[:4000])

            chunks.append(DocumentChunk(
                id=chunk_id,
                text=chunk_text,
                metadata=ChunkMetadata(
                    source_file=filename,
                    file_type=file_type,
                    chunk_index=chunk_index,
                    section_type="detail",
                    heading_path=list(current_heading),
                    contextual_prefix=contextual_prefix,
                ),
            ))
            chunk_index += 1
            # Overlap: keep last part
            current_chunk_parts = [current_chunk_parts[-1]] if current_chunk_parts else []
            current_tokens = _count_tokens(current_chunk_parts[0]) if current_chunk_parts else 0

        current_chunk_parts.append(para)
        current_tokens += para_tokens

    # Final chunk
    if current_chunk_parts:
        chunk_text = "\n\n".join(current_chunk_parts)
        chunk_id = str(uuid.uuid4())
        contextual_prefix = _generate_contextual_prefix(chunk_text, full_text[:4000])

        chunks.append(DocumentChunk(
            id=chunk_id,
            text=chunk_text,
            metadata=ChunkMetadata(
                source_file=filename,
                file_type=file_type,
                chunk_index=chunk_index,
                section_type="detail",
                heading_path=list(current_heading),
                contextual_prefix=contextual_prefix,
            ),
        ))

    # Also chunk tables separately
    for i, table in enumerate(extracted.get("tables", [])):
        table_text = _table_to_text(table)
        table_id = str(uuid.uuid4())
        contextual_prefix = _generate_contextual_prefix(table_text, full_text[:4000])

        chunks.append(DocumentChunk(
            id=table_id,
            text=table_text,
            metadata=ChunkMetadata(
                source_file=filename,
                file_type=file_type,
                chunk_index=chunk_index + i + 1,
                section_type="table",
                heading_path=["Tables"],
                contextual_prefix=contextual_prefix,
            ),
        ))

    return chunks


def _table_to_text(table: dict) -> str:
    """Convert a Doc Intelligence table to readable text."""
    rows: dict[int, dict[int, str]] = {}
    headers: dict[int, str] = {}

    for cell in table["cells"]:
        r, c, text = cell["row"], cell["col"], cell["text"]
        if cell.get("is_header"):
            headers[c] = text
        else:
            rows.setdefault(r, {})[c] = text

    lines = []
    if headers:
        lines.append(" | ".join(headers[c] for c in sorted(headers)))
        lines.append("-" * 40)

    for r in sorted(rows):
        row_data = rows[r]
        if headers:
            parts = []
            for c in sorted(headers):
                val = row_data.get(c, "")
                parts.append(f"{headers[c]}: {val}")
            lines.append(", ".join(parts))
        else:
            lines.append(" | ".join(row_data[c] for c in sorted(row_data)))

    return "\n".join(lines)
