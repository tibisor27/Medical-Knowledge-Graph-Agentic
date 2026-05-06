from typing import Optional, List
from langchain_openai import AzureOpenAIEmbeddings
from src.config import validate_config, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, OPENAI_API_VERSION, AZURE_EMBEDDINGS_DEPLOYMENT_NAME

import logging
logger = logging.getLogger(__name__)

def get_embeddings_client() -> AzureOpenAIEmbeddings:
    """Get the Azure OpenAI embeddings client."""
    validate_config()
    return AzureOpenAIEmbeddings(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment=AZURE_EMBEDDINGS_DEPLOYMENT_NAME
    )

def get_embeddings(text: str) -> Optional[List[float]]:

    if not text or not text.strip():
        logger.warning("Empty text provided for embedding")
        return None
    
    try:
        embedding_client = get_embeddings_client()

        embedding = embedding_client.embed_query(text)
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding for '{text}': {e}")
        return None
