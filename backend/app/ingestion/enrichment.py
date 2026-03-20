"""
Enrichment layer: embeddings, key phrases, entities via Azure services.
"""
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

from app.config import settings
from app.models.schemas import DocumentChunk


def _get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.OPENAI_ENDPOINT,
        api_key=settings.OPENAI_KEY,
        api_version="2024-10-21",
    )


def _get_text_analytics_client() -> TextAnalyticsClient:
    return TextAnalyticsClient(
        endpoint=settings.TEXT_ANALYTICS_ENDPOINT,
        credential=AzureKeyCredential(settings.TEXT_ANALYTICS_KEY),
    )


async def generate_embeddings(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    """Generate 1536-dim embeddings for each chunk using Azure OpenAI.
    Embeds contextual_prefix + chunk text together for Contextual Retrieval."""
    client = _get_openai_client()

    # Skip parent chunks (too large) — only embed child/detail chunks
    embeddable = [c for c in chunks if c.metadata.section_type != "parent"]

    # Batch embed (Azure OpenAI supports up to 16 inputs per call)
    # text-embedding-3-small max is 8192 tokens (~30k chars), truncate to be safe
    max_chars = 25000
    batch_size = 16
    for i in range(0, len(embeddable), batch_size):
        batch = embeddable[i : i + batch_size]
        texts = []
        for chunk in batch:
            embed_text = chunk.text
            if chunk.metadata.contextual_prefix:
                embed_text = f"{chunk.metadata.contextual_prefix}\n\n{chunk.text}"
            texts.append(embed_text[:max_chars])

        response = client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_DEPLOYMENT,
            input=texts,
            dimensions=512,
        )

        for j, embedding_data in enumerate(response.data):
            batch[j].embedding = embedding_data.embedding

    return chunks


async def extract_key_phrases_and_entities(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    """Extract key phrases and named entities from chunks via Text Analytics."""
    client = _get_text_analytics_client()

    # Text Analytics free/standard tier: max 5 docs per batch
    batch_size = 5
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.text[:5000] for c in batch]

        # Key phrases
        kp_results = client.extract_key_phrases(texts)
        for j, result in enumerate(kp_results):
            if not result.is_error:
                batch[j].metadata.key_phrases = result.key_phrases

        # Named entities (people, orgs, locations, dates, etc.)
        entity_results = client.recognize_entities(texts)
        for j, result in enumerate(entity_results):
            if not result.is_error:
                batch[j].metadata.entities = [
                    {
                        "text": e.text,
                        "category": e.category,
                        "subcategory": e.subcategory,
                        "confidence": e.confidence_score,
                    }
                    for e in result.entities
                ]

    return chunks
