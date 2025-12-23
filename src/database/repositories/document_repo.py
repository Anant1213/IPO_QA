"""
Repository for Document operations
"""
from database.connection import get_db
from database.models import Document

class DocumentRepository:
    
    @staticmethod
    def create(document_data):
        """Create a new document"""
        with get_db() as db:
            doc = Document(**document_data)
            db.add(doc)
            db.flush()  # Get ID without committing
            result = doc.to_dict()
            result['id'] = doc.id
            return result
    
    @staticmethod
    def get_all():
        """Get all documents"""
        with get_db() as db:
            docs = db.query(Document).order_by(Document.created_at.desc()).all()
            return [doc.to_dict() for doc in docs]
    
    @staticmethod
    def get_by_id(document_id):
        """Get document by document_id"""
        with get_db() as db:
            doc = db.query(Document).filter_by(document_id=document_id).first()
            if doc:
                result = doc.to_dict()
                result['id'] = doc.id
                return result
            return None
    
    @staticmethod
    def get_by_hash(file_hash):
        """Check if document with hash exists"""
        with get_db() as db:
            doc = db.query(Document).filter_by(file_hash=file_hash).first()
            return doc.to_dict() if doc else None
    
    @staticmethod
    def update(document_id, updates):
        """Update document"""
        with get_db() as db:
            doc = db.query(Document).filter_by(document_id=document_id).first()
            if doc:
                for key, value in updates.items():
                    setattr(doc, key, value)
                db.flush()
                return doc.to_dict()
            return None
    
    @staticmethod
    def delete(document_id):
        """Delete document (cascade to chunks/embeddings)"""
        with get_db() as db:
            doc = db.query(Document).filter_by(document_id=document_id).first()
            if doc:
                db.delete(doc)
                return True
            return False
