"""
Report generation: LLM takes retrieved chunks + graph context and generates
structured reports with categorization, charts, and summaries.
"""
import json
from openai import AzureOpenAI

from app.config import settings
from app.models.schemas import QueryResult, ReportResponse, ReportSection


def _get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.OPENAI_ENDPOINT,
        api_key=settings.OPENAI_KEY,
        api_version="2024-10-21",
    )


REPORT_SYSTEM_PROMPT = """You are a data analysis and report generation assistant. Given a set of document chunks retrieved from a search, generate a structured report.

Your report MUST be returned as valid JSON with this structure:
{
  "title": "Report title",
  "summary": "2-3 sentence executive summary",
  "sections": [
    {
      "title": "Section title",
      "content": "Markdown-formatted analysis text",
      "chart_data": {
        "type": "bar|pie|line",
        "labels": ["Label1", "Label2"],
        "values": [10, 20],
        "label": "Dataset label"
      },
      "table_data": [
        {"column1": "value1", "column2": "value2"}
      ]
    }
  ],
  "total_documents_analyzed": 42
}

Guidelines:
- IMPORTANT: If the data includes "FULL DATASET STATISTICS" or "TOTAL MATCHING TICKETS", use those numbers as the authoritative counts — they represent ALL data, not just the sample chunks shown below them
- Be specific with numbers and percentages based on the full dataset counts
- Include chart_data when categorization or trends are relevant (set to null otherwise)
- Include table_data for detailed breakdowns (set to null otherwise)
- chart_data.type should be "pie" for categories, "bar" for comparisons, "line" for trends
- Content should use markdown formatting
- Analyze ALL provided chunks, not just a sample"""


def _build_report_prompt(query: str, results: list[QueryResult], report_type: str) -> str:
    """Build the prompt with all retrieved context."""
    context_parts = []
    for i, r in enumerate(results):
        prefix = f"[Context: {r.contextual_prefix}]\n" if r.contextual_prefix else ""
        source = f"[Source: {r.source_file}"
        if r.section_type:
            source += f" | {r.section_type}"
        source += "]"
        context_parts.append(f"--- Chunk {i + 1} {source} ---\n{prefix}{r.text}")

    context = "\n\n".join(context_parts)

    type_instructions = {
        "summary": "Provide a comprehensive summary of the data, highlighting key findings and patterns.",
        "categorization": "Categorize and group the data by topic/type. Count items per category. Show distribution as chart data.",
        "trend": "Identify trends, patterns, and changes over time in the data.",
        "comparison": "Compare and contrast different groups, categories, or segments in the data.",
    }

    instruction = type_instructions.get(report_type, type_instructions["summary"])

    return (
        f"QUERY: {query}\n\n"
        f"REPORT TYPE: {report_type}\n"
        f"INSTRUCTION: {instruction}\n\n"
        f"DATA ({len(results)} chunks):\n\n{context}"
    )


async def generate_report(
    query: str,
    results: list[QueryResult],
    report_type: str = "summary",
) -> ReportResponse:
    """Generate a structured report from retrieved chunks."""
    client = _get_openai_client()

    prompt = _build_report_prompt(query, results, report_type)

    response = client.chat.completions.create(
        model=settings.OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    report_json = json.loads(response.choices[0].message.content)

    sections = []
    for s in report_json.get("sections", []):
        sections.append(ReportSection(
            title=s["title"],
            content=s["content"],
            chart_data=s.get("chart_data"),
            table_data=s.get("table_data"),
        ))

    return ReportResponse(
        title=report_json.get("title", "Report"),
        summary=report_json.get("summary", ""),
        sections=sections,
        total_documents_analyzed=report_json.get("total_documents_analyzed", len(results)),
    )


async def chat_with_data(query: str, results: list[QueryResult]) -> str:
    """Conversational Q&A over retrieved data (not a formal report)."""
    client = _get_openai_client()

    context_parts = []
    for i, r in enumerate(results):
        prefix = f"[Context: {r.contextual_prefix}]\n" if r.contextual_prefix else ""
        context_parts.append(f"--- {r.source_file} ---\n{prefix}{r.text}")
    context = "\n\n".join(context_parts)

    response = client.chat.completions.create(
        model=settings.OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a data analysis assistant. Answer the user's question based on "
                    "the provided document chunks. Be specific, cite source files, and include "
                    "numbers/counts when relevant. If the data doesn't contain enough info to "
                    "answer fully, say so."
                ),
            },
            {
                "role": "user",
                "content": f"DATA:\n{context}\n\nQUESTION: {query}",
            },
        ],
        max_tokens=2000,
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()
