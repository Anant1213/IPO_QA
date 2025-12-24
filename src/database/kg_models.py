"""
SQLAlchemy ORM models for KG tables
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Float, Boolean, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from .models import Base


class Evidence(Base):
    """Provenance tracking for extracted facts"""
    __tablename__ = 'evidence'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    chunk_id = Column(Integer, ForeignKey('chunks.id', ondelete='SET NULL'))
    
    quote = Column(Text, nullable=False)
    page_number = Column(Integer)
    section_title = Column(String(255))
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'quote': self.quote,
            'page_number': self.page_number,
            'section_title': self.section_title
        }


class KGEntity(Base):
    """Canonical entities with normalization"""
    __tablename__ = 'kg_entities'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    entity_type = Column(String(50), nullable=False)
    canonical_name = Column(String(500), nullable=False)
    normalized_key = Column(String(500), nullable=False)
    
    attributes = Column(JSONB, default={})
    confidence = Column(Float, default=1.0)
    evidence_id = Column(Integer, ForeignKey('evidence.id', ondelete='SET NULL'))
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'canonical_name': self.canonical_name,
            'normalized_key': self.normalized_key,
            'attributes': self.attributes,
            'confidence': self.confidence
        }


class EntityAlias(Base):
    """Entity name variants"""
    __tablename__ = 'entity_aliases'
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False)
    
    alias = Column(String(500), nullable=False)
    alias_normalized = Column(String(500), nullable=False)
    source = Column(String(50), default='extraction')
    
    created_at = Column(TIMESTAMP, default=datetime.now)


class DefinedTerm(Base):
    """Glossary/Definitions from documents"""
    __tablename__ = 'defined_terms'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    term = Column(String(500), nullable=False)
    term_normalized = Column(String(500), nullable=False)
    definition = Column(Text, nullable=False)
    
    evidence_id = Column(Integer, ForeignKey('evidence.id', ondelete='SET NULL'))
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'term': self.term,
            'definition': self.definition
        }


class Claim(Base):
    """Facts with provenance (subject -> predicate -> object)"""
    __tablename__ = 'claims'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    subject_entity_id = Column(Integer, ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False)
    predicate = Column(String(100), nullable=False)
    
    object_value = Column(Text)
    object_entity_id = Column(Integer, ForeignKey('kg_entities.id', ondelete='SET NULL'))
    
    datatype = Column(String(50), nullable=False)
    period_label = Column(String(50))
    period_scope = Column(String(50))
    
    confidence = Column(Float, default=1.0)
    evidence_id = Column(Integer, ForeignKey('evidence.id', ondelete='SET NULL'))
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'subject_entity_id': self.subject_entity_id,
            'predicate': self.predicate,
            'object_value': self.object_value,
            'object_entity_id': self.object_entity_id,
            'datatype': self.datatype,
            'period_label': self.period_label,
            'confidence': self.confidence
        }


class Event(Base):
    """Timeline events"""
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    event_type = Column(String(100), nullable=False)
    event_date = Column(Date)
    event_date_text = Column(String(100))
    description = Column(Text)
    
    evidence_id = Column(Integer, ForeignKey('evidence.id', ondelete='SET NULL'))
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_type': self.event_type,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_date_text': self.event_date_text,
            'description': self.description
        }


class EventParticipant(Base):
    """Entities participating in events"""
    __tablename__ = 'event_participants'
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('events.id', ondelete='CASCADE'), nullable=False)
    entity_id = Column(Integer, ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False)
    
    role = Column(String(100), nullable=False)
    
    created_at = Column(TIMESTAMP, default=datetime.now)


class ValidationReport(Base):
    """Validation results for KG extraction"""
    __tablename__ = 'validation_reports'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    run_at = Column(TIMESTAMP, default=datetime.now)
    pipeline_version = Column(String(50))
    
    total_entities = Column(Integer, default=0)
    total_claims = Column(Integer, default=0)
    total_events = Column(Integer, default=0)
    total_definitions = Column(Integer, default=0)
    
    violations = Column(JSONB, default=[])
    warnings = Column(JSONB, default=[])
    
    is_valid = Column(Boolean, default=True)
    
    created_at = Column(TIMESTAMP, default=datetime.now)


class MergeCandidate(Base):
    """Entity resolution candidates"""
    __tablename__ = 'merge_candidates'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    entity_a_id = Column(Integer, ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False)
    entity_b_id = Column(Integer, ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False)
    
    confidence = Column(Float, nullable=False)
    reason = Column(String(255))
    
    status = Column(String(50), default='pending')
    reviewed_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, default=datetime.now)
