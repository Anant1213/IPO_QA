"""
Repository classes for KG tables
"""
import re
from typing import List, Dict, Optional, Any
from database.connection import get_db
from database.kg_models import (
    Evidence, KGEntity, EntityAlias, DefinedTerm, 
    Claim, Event, EventParticipant, ValidationReport, MergeCandidate
)


def normalize_key(text: str) -> str:
    """Normalize text for matching: lowercase, trim, collapse spaces, unify dashes"""
    if not text:
        return ""
    # Trim
    result = text.strip()
    # Unify dashes
    result = re.sub(r'[–—]', '-', result)
    # Lowercase
    result = result.lower()
    # Collapse multiple spaces and replace with underscore
    result = re.sub(r'\s+', '_', result)
    return result


class EvidenceRepository:
    """Repository for evidence/provenance tracking"""
    
    @staticmethod
    def create(data: Dict) -> Dict:
        """Create evidence record"""
        with get_db() as db:
            evidence = Evidence(
                document_id=data['document_id'],
                chunk_id=data.get('chunk_id'),
                quote=data['quote'][:500],  # Limit quote length
                page_number=data.get('page_number'),
                section_title=data.get('section_title')
            )
            db.add(evidence)
            db.commit()
            db.refresh(evidence)
            return evidence.to_dict()
    
    @staticmethod
    def create_many(evidence_list: List[Dict]) -> List[int]:
        """Bulk create evidence records"""
        with get_db() as db:
            ids = []
            for data in evidence_list:
                evidence = Evidence(
                    document_id=data['document_id'],
                    chunk_id=data.get('chunk_id'),
                    quote=data['quote'][:500],
                    page_number=data.get('page_number'),
                    section_title=data.get('section_title')
                )
                db.add(evidence)
                db.flush()
                ids.append(evidence.id)
            db.commit()
            return ids


class KGEntityRepository:
    """Repository for KG entities"""
    
    @staticmethod
    def create(data: Dict) -> Dict:
        """Create entity"""
        with get_db() as db:
            entity = KGEntity(
                document_id=data['document_id'],
                entity_type=data['entity_type'],
                canonical_name=data['canonical_name'],
                normalized_key=normalize_key(data['canonical_name']),
                attributes=data.get('attributes', {}),
                confidence=data.get('confidence', 1.0),
                evidence_id=data.get('evidence_id')
            )
            db.add(entity)
            db.commit()
            db.refresh(entity)
            return entity.to_dict()
    
    @staticmethod
    def get_by_normalized_key(document_id: int, key: str) -> Optional[Dict]:
        """Find entity by normalized key"""
        with get_db() as db:
            entity = db.query(KGEntity).filter(
                KGEntity.document_id == document_id,
                KGEntity.normalized_key == normalize_key(key)
            ).first()
            return entity.to_dict() if entity else None
    
    @staticmethod
    def get_all_for_document(document_id: int, entity_type: str = None) -> List[Dict]:
        """Get all entities for a document"""
        with get_db() as db:
            query = db.query(KGEntity).filter(KGEntity.document_id == document_id)
            if entity_type:
                query = query.filter(KGEntity.entity_type == entity_type)
            return [e.to_dict() for e in query.all()]
    
    @staticmethod
    def search(document_id: int, search_term: str, limit: int = 10) -> List[Dict]:
        """Search entities by name (fuzzy)"""
        with get_db() as db:
            # Simple ILIKE search - can enhance with pg_trgm later
            entities = db.query(KGEntity).filter(
                KGEntity.document_id == document_id,
                KGEntity.canonical_name.ilike(f'%{search_term}%')
            ).limit(limit).all()
            return [e.to_dict() for e in entities]
    
    @staticmethod
    def add_alias(entity_id: int, alias: str, source: str = 'extraction'):
        """Add alias to entity"""
        with get_db() as db:
            entity_alias = EntityAlias(
                entity_id=entity_id,
                alias=alias,
                alias_normalized=normalize_key(alias),
                source=source
            )
            db.add(entity_alias)
            db.commit()


class DefinedTermRepository:
    """Repository for defined terms/glossary"""
    
    @staticmethod
    def create(data: Dict) -> Dict:
        """Create defined term"""
        with get_db() as db:
            term = DefinedTerm(
                document_id=data['document_id'],
                term=data['term'],
                term_normalized=normalize_key(data['term']),
                definition=data['definition'],
                evidence_id=data.get('evidence_id')
            )
            db.add(term)
            db.commit()
            db.refresh(term)
            return term.to_dict()
    
    @staticmethod
    def get_by_term(document_id: int, term: str) -> Optional[Dict]:
        """Find definition by term"""
        with get_db() as db:
            defined_term = db.query(DefinedTerm).filter(
                DefinedTerm.document_id == document_id,
                DefinedTerm.term_normalized == normalize_key(term)
            ).first()
            return defined_term.to_dict() if defined_term else None
    
    @staticmethod
    def get_all_for_document(document_id: int) -> List[Dict]:
        """Get all definitions for a document"""
        with get_db() as db:
            terms = db.query(DefinedTerm).filter(
                DefinedTerm.document_id == document_id
            ).all()
            return [t.to_dict() for t in terms]


class ClaimRepository:
    """Repository for claims/facts"""
    
    @staticmethod
    def create(data: Dict) -> Dict:
        """Create claim"""
        with get_db() as db:
            claim = Claim(
                document_id=data['document_id'],
                subject_entity_id=data['subject_entity_id'],
                predicate=data['predicate'],
                object_value=data.get('object_value'),
                object_entity_id=data.get('object_entity_id'),
                datatype=data['datatype'],
                period_label=data.get('period_label'),
                period_scope=data.get('period_scope'),
                confidence=data.get('confidence', 1.0),
                evidence_id=data.get('evidence_id')
            )
            db.add(claim)
            db.commit()
            db.refresh(claim)
            return claim.to_dict()
    
    @staticmethod
    def get_claims_for_entity(entity_id: int, predicate: str = None) -> List[Dict]:
        """Get claims where entity is subject"""
        with get_db() as db:
            query = db.query(Claim).filter(Claim.subject_entity_id == entity_id)
            if predicate:
                query = query.filter(Claim.predicate == predicate)
            return [c.to_dict() for c in query.all()]
    
    @staticmethod
    def get_relationships(entity_id: int) -> List[Dict]:
        """Get relationship claims (where object is entity)"""
        with get_db() as db:
            claims = db.query(Claim).filter(
                Claim.subject_entity_id == entity_id,
                Claim.datatype == 'entity'
            ).all()
            return [c.to_dict() for c in claims]


class EventRepository:
    """Repository for events"""
    
    @staticmethod
    def create(data: Dict) -> Dict:
        """Create event"""
        with get_db() as db:
            event = Event(
                document_id=data['document_id'],
                event_type=data['event_type'],
                event_date=data.get('event_date'),
                event_date_text=data.get('event_date_text'),
                description=data.get('description'),
                evidence_id=data.get('evidence_id')
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return event.to_dict()
    
    @staticmethod
    def add_participant(event_id: int, entity_id: int, role: str):
        """Add participant to event"""
        with get_db() as db:
            participant = EventParticipant(
                event_id=event_id,
                entity_id=entity_id,
                role=role
            )
            db.add(participant)
            db.commit()
    
    @staticmethod
    def get_events_for_document(document_id: int, event_type: str = None) -> List[Dict]:
        """Get events for document"""
        with get_db() as db:
            query = db.query(Event).filter(Event.document_id == document_id)
            if event_type:
                query = query.filter(Event.event_type == event_type)
            return [e.to_dict() for e in query.order_by(Event.event_date).all()]


class ValidationReportRepository:
    """Repository for validation reports"""
    
    @staticmethod
    def create(data: Dict) -> Dict:
        """Create validation report"""
        with get_db() as db:
            report = ValidationReport(
                document_id=data['document_id'],
                pipeline_version=data.get('pipeline_version'),
                total_entities=data.get('total_entities', 0),
                total_claims=data.get('total_claims', 0),
                total_events=data.get('total_events', 0),
                total_definitions=data.get('total_definitions', 0),
                violations=data.get('violations', []),
                warnings=data.get('warnings', []),
                is_valid=data.get('is_valid', True)
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            return {
                'id': report.id,
                'is_valid': report.is_valid,
                'total_entities': report.total_entities,
                'violations': report.violations
            }
