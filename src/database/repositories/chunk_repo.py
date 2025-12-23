"""
Repository for Chunk operations
"""
from database.connection import get_db
from database.models import Chunk, Document

class ChunkRepository:
    
    @staticmethod
    def create(chunk_data):
        """Create a new chunk"""
        with get_db() as db:
            chunk = Chunk(**chunk_data)
            db.add(chunk)
            db.flush()
            return chunk.id
    
    @staticmethod
    def create_many(chunks_data):
        """Bulk insert chunks (faster)"""
        with get_db() as db:
            chunks = [Chunk(**data) for data in chunks_data]
            db.bulk_save_objects(chunks, return_defaults=True)
            db.flush()
            return [c.id for c in chunks]
    
    @staticmethod
    def get_by_document(document_id):
        """Get all chunks for a document"""
        with get_db() as db:
            # Join with documents to get document_id
            chunks = db.query(Chunk).join(Document).filter(
                Document.document_id == document_id
            ).order_by(Chunk.chunk_index).all()
            
            return [c.to_dict() for c in chunks]
    
    @staticmethod
    def count_by_document(document_id):
        """Count chunks for a document"""
        with get_db() as db:
            return db.query(Chunk).join(Document).filter(
                Document.document_id == document_id
            ).count()
