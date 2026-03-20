"""
Document extraction layer.
- Structured files (CSV, XLSX, JSON): parsed with pandas/json
- Unstructured files (PDF, DOCX, images): Azure Doc Intelligence
"""
import io
import json
import pandas as pd
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from app.config import settings
from app.models.schemas import FileType


def _get_doc_intel_client() -> DocumentAnalysisClient:
    return DocumentAnalysisClient(
        endpoint=settings.DOC_INTEL_ENDPOINT,
        credential=AzureKeyCredential(settings.DOC_INTEL_KEY),
    )


def detect_file_type(filename: str) -> FileType:
    ext = filename.rsplit(".", 1)[-1].lower()
    mapping = {
        "pdf": FileType.PDF,
        "docx": FileType.DOCX,
        "csv": FileType.CSV,
        "xlsx": FileType.XLSX,
        "json": FileType.JSON,
        "jpg": FileType.IMAGE,
        "jpeg": FileType.IMAGE,
        "png": FileType.IMAGE,
        "tiff": FileType.IMAGE,
        "bmp": FileType.IMAGE,
    }
    return mapping.get(ext, FileType.PDF)


async def extract_structured(file_bytes: bytes, filename: str, file_type: FileType) -> list[dict]:
    """Extract rows/records from CSV, XLSX, or JSON files. Each row becomes a document."""
    if file_type == FileType.CSV:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="cp1252")
    elif file_type == FileType.XLSX:
        df = pd.read_excel(io.BytesIO(file_bytes))
    elif file_type == FileType.JSON:
        data = json.loads(file_bytes.decode("utf-8"))
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Try to find a list within the dict
            for value in data.values():
                if isinstance(value, list):
                    df = pd.DataFrame(value)
                    break
            else:
                df = pd.DataFrame([data])
        else:
            df = pd.DataFrame([{"content": str(data)}])
    else:
        raise ValueError(f"Unsupported structured type: {file_type}")

    # Convert each row to a text representation + preserve raw columns as metadata
    # Skip columns that are mostly empty or contain non-useful data
    skip_patterns = {"nan", "none", ""}
    records = []
    columns = list(df.columns)
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        # Build readable text from row, skipping empty/junk columns
        text_parts = []
        for col, val in row_dict.items():
            if pd.notna(val) and str(val).strip().lower() not in skip_patterns:
                text_parts.append(f"{col}: {val}")
        records.append({
            "index": idx,
            "text": "\n".join(text_parts),
            "columns": columns,
            "raw": {k: (str(v) if pd.notna(v) else None) for k, v in row_dict.items()},
        })
    return records


async def extract_unstructured(file_bytes: bytes, filename: str, file_type: FileType) -> dict:
    """Extract text, tables, and key-value pairs from PDF/DOCX/images via Doc Intelligence."""
    client = _get_doc_intel_client()
    poller = client.begin_analyze_document("prebuilt-document", document=io.BytesIO(file_bytes))
    result = poller.result()

    extracted = {
        "content": result.content,
        "pages": [],
        "tables": [],
        "key_value_pairs": [],
    }

    # Pages
    for page in result.pages:
        page_data = {
            "page_number": page.page_number,
            "lines": [line.content for line in (page.lines or [])],
        }
        extracted["pages"].append(page_data)

    # Tables
    for table in (result.tables or []):
        table_data = {
            "row_count": table.row_count,
            "column_count": table.column_count,
            "cells": [],
        }
        for cell in table.cells:
            table_data["cells"].append({
                "row": cell.row_index,
                "col": cell.column_index,
                "text": cell.content,
                "is_header": cell.kind == "columnHeader",
            })
        extracted["tables"].append(table_data)

    # Key-value pairs
    for kv in (result.key_value_pairs or []):
        if kv.key and kv.value:
            extracted["key_value_pairs"].append({
                "key": kv.key.content,
                "value": kv.value.content,
            })

    return extracted
