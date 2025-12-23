"""
SQLAlchemy ORM models for database tables
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(String(255), unique=True, nullable=False)
    filename = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False)
    file_path = Column(Text, nullable=False)
    
    total_pages = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    
    upload_date = Column(TIMESTAMP, default=datetime.now)
    processed_at = Column(TIMESTAMP)
    
    
    doc_metadata = Column(JSONB, name='doc_metadata', default={})
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'document_id': self.document_id,
            'filename': self.filename,
            'display_name': self.display_name,
            'file_hash': self.file_hash,
            'file_path': self.file_path,
            'total_pages': self.total_pages,
            'total_chunks': self.total_chunks,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'metadata': self.doc_metadata
        }

class Chapter(Base):
    __tablename__ = 'chapters'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    start_page = Column(Integer)
    end_page = Column(Integer)
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    def to_dict(self):
        return {
            'chapter_number': self.chapter_number,
            'title': self.title,
            'start_page': self.start_page,
            'end_page': self.end_page
        }

class Chunk(Base):
    __tablename__ = 'chunks'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    chapter_id = Column(Integer, ForeignKey('chapters.id', ondelete='SET NULL'))
    
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    
    page_number = Column(Integer)
    word_count = Column(Integer)
    
    
    chunk_metadata = Column(JSONB, name='chunk_metadata', default={})
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'chunk_index': self.chunk_index,
            'text': self.text,
            'page_number': self.page_number,
            'metadata': self.chunk_metadata
        }

class Embedding(Base):
    __tablename__ = 'embeddings'
    
    id = Column(Integer, primary_key=True)
    chunk_id = Column(Integer, ForeignKey('chunks.id', ondelete='CASCADE'), nullable=False)
    
    # Store as JSONB array (384 floats)
    embedding = Column(JSONB, nullable=False)
    
    model_name = Column(String(100), default='all-MiniLM-L6-v2')
    created_at = Column(TIMESTAMP, default=datetime.now)
