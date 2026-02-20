from typing import Optional, List
from src.utils.get_llm import get_embeddings_client

import logging
logger = logging.getLogger(__name__)

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
