"""
Embedding utilities for generating and searching vector embeddings.
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Tuple
from utils.config import EMBEDDING_MODEL_NAME, DEFAULT_TOP_K


# Global model cache
_model = None


def get_embedding_model() -> SentenceTransformer:
    """
    Get or load the embedding model (cached).
    
    Returns:
        SentenceTransformer model
    """
    global _model
    
    if _model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        # Force CPU to avoid mutex lock issues on Apple Silicon
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME, device='cpu')
        print("Model loaded successfully (CPU mode)")
    
    return _model


def encode_chunks(chunks: List[Dict]) -> Tuple[np.ndarray, Dict[str, int]]:
    """
    Encode chunks into embeddings.
    
    Args:
        chunks: List of chunk dicts
        
    Returns:
        Tuple of (embeddings array, index_to_chunk_id mapping)
    """
    print("\\n=== Generating Embeddings ===")
    
    model = get_embedding_model()
    
    # Extract texts
    texts = [chunk["text"] for chunk in chunks]
    
    print(f"Encoding {len(texts)} chunks...")
    
    # Generate embeddings
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    # Create index mapping
    index_to_chunk_id = {str(i): chunks[i]["chunk_id"] for i in range(len(chunks))}
    
    print(f"Embeddings shape: {embeddings.shape}")
    
    return embeddings, index_to_chunk_id


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between vectors.
    
    Args:
        a: Query vector (1D or 2D)
        b: Document vectors (2D)
        
    Returns:
        Similarity scores
    """
    # Normalize vectors
    a_norm = a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-8)
    b_norm = b / (np.linalg.norm(b, axis=-1, keepdims=True) + 1e-8)
    
    # Compute dot product
    if a_norm.ndim == 1:
        return np.dot(b_norm, a_norm)
    else:
        return np.dot(b_norm, a_norm.T).squeeze()


def search_similar_chunks(
    question: str,
    chunks: List[Dict],
    embeddings: np.ndarray,
    top_k: int = DEFAULT_TOP_K
) -> List[Tuple[Dict, float]]:
    """
    Search for similar chunks using cosine similarity.
    
    Args:
        question: User's question
        chunks: List of chunk dicts (filtered by chapter)
        embeddings: Embeddings array (corresponding to chunks)
        top_k: Number of top results to return
        
    Returns:
        List of (chunk_dict, similarity_score) tuples
    """
    print(f"\\n=== Searching for Top {top_k} Similar Chunks ===")
    
    # Encode question
    model = get_embedding_model()
    question_embedding = model.encode([question], convert_to_numpy=True)[0]
    
    # Compute similarities
    similarities = cosine_similarity(question_embedding, embeddings)
    
    # Get top K indices
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    # Build results
    results = []
    for idx in top_indices:
        chunk = chunks[idx]
        score = float(similarities[idx])
        results.append((chunk, score))
    
    print(f"Found {len(results)} similar chunks")
    
    return results
