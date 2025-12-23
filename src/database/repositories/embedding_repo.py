"""
Repository for Embedding operations (using JSONB instead of pgvector)
"""
from database.connection import get_db  
from database.models import Embedding
import numpy as np
import json

class EmbeddingRepository:
    
    @staticmethod
    def create(embedding_data):
        """Create a new embedding"""
        with get_db() as db:
            emb = Embedding(**embedding_data)
            db.add(emb)
            db.flush()
            return emb.id
    
    @staticmethod
    def create_many(embeddings_data):
        """Bulk insert embeddings"""
        with get_db() as db:
            embeddings = [Embedding(**data) for data in embeddings_data]
            db.bulk_save_objects(embeddings)
            db.flush()
            return len(embeddings)
    
    @staticmethod
    def search_similar(query_embedding, document_id, top_k=5):
        """
        Find similar chunks using cosine similarity
        
        Args:
            query_embedding: numpy array or list of floats (384 dims)
            document_id: document_id to search within
            top_k: number of results to return
        
        Returns:
            List of dicts with chunk info and similarity scores
        """
        with get_db() as db:
            # Convert numpy array to list
            if isinstance(query_embedding, np.ndarray):
                query_embedding = query_embedding.tolist()
            
            # Convert to JSONB string
            query_json = json.dumps(query_embedding)
            
            # Use raw connection to avoid SQLAlchemy parsing issues
            raw_conn = db.connection().connection  # Get the underlying psycopg2 connection
            cursor = raw_conn.cursor()
            
            query = """
                SELECT 
                    c.id as chunk_id,
                    c.text,
                    c.page_number,
                    c.chunk_metadata as metadata,
                    cosine_similarity(e.embedding, %s::jsonb) as similarity
                FROM embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE d.document_id = %s
                ORDER BY cosine_similarity(e.embedding, %s::jsonb) DESC
                LIMIT %s
            """
            
            cursor.execute(query, (query_json, document_id, query_json, top_k))
            results = cursor.fetchall()
            cursor.close()
            
            return [{
                'chunk_id': r[0],
                'text': r[1],
                'page_number': r[2],
                'metadata': r[3],
                'similarity': float(r[4]) if r[4] else 0.0
            } for r in results]
