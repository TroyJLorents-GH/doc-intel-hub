"""
Query Expansion + Multi-Query RAG.
- Query Expansion: enriches a single query with related terms and context
- Multi-Query: generates multiple distinct phrasings to capture different angles
"""
from openai import AzureOpenAI

from app.config import settings


def _get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.OPENAI_ENDPOINT,
        api_key=settings.OPENAI_KEY,
        api_version="2024-10-21",
    )


def expand_query(query: str) -> str:
    """Expand a brief query into a richer, more comprehensive version."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a search query expansion assistant. Given a user's brief query, "
                    "expand it into a more detailed, comprehensive search query by:\n"
                    "- Adding related terms and synonyms\n"
                    "- Clarifying intent\n"
                    "- Including relevant context\n"
                    "Maintain the original intent. Return ONLY the expanded query, nothing else."
                ),
            },
            {"role": "user", "content": query},
        ],
        max_tokens=200,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def generate_multi_queries(query: str, num_queries: int = 4) -> list[str]:
    """Generate multiple distinct query variations to capture different angles."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a search query diversification assistant. Given a user query, "
                    "generate exactly {n} distinct alternative phrasings that capture different "
                    "perspectives or angles of the same information need.\n"
                    "Each query should approach the topic from a different angle.\n"
                    "Return one query per line, no numbering or bullets."
                ).format(n=num_queries),
            },
            {"role": "user", "content": query},
        ],
        max_tokens=400,
        temperature=0.7,
    )
    queries = [
        line.strip()
        for line in response.choices[0].message.content.strip().split("\n")
        if line.strip()
    ]
    # Always include the original query
    return [query] + queries[:num_queries]
