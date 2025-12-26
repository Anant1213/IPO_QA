"""
Repository for Knowledge Graph operations from PostgreSQL database
"""
from sqlalchemy import text
from database.connection import engine
from typing import List, Dict, Optional
import json


class KGRepository:
    """Repository for querying Knowledge Graph from PostgreSQL"""
    
    @staticmethod
    def get_document_id(document_id_str: str) -> Optional[int]:
        """Get numeric document ID from string document_id"""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id FROM documents WHERE document_id = :doc_id
            """), {"doc_id": document_id_str})
            row = result.fetchone()
            return row[0] if row else None
    
    @staticmethod
    def search_entities(doc_id: int, search_terms: List[str], limit: int = 10) -> List[Dict]:
        """
        Search entities by name matching any of the search terms
        Uses fuzzy matching with ILIKE
        """
        entities = []
        with engine.connect() as conn:
            for term in search_terms:
                if len(term) < 2:
                    continue
                result = conn.execute(text("""
                    SELECT id, canonical_name, entity_type, attributes
                    FROM kg_entities
                    WHERE document_id = :doc_id
                    AND (
                        canonical_name ILIKE :pattern
                        OR normalized_key ILIKE :norm_pattern
                    )
                    LIMIT :limit
                """), {
                    "doc_id": doc_id,
                    "pattern": f"%{term}%",
                    "norm_pattern": f"%{term.lower().replace(' ', '_')}%",
                    "limit": limit
                })
                for row in result:
                    entity = {
                        "id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "attributes": row[3] if row[3] else {}
                    }
                    # Avoid duplicates
                    if not any(e["id"] == entity["id"] for e in entities):
                        entities.append(entity)
        
        return entities[:limit]
    
    @staticmethod
    def find_entity_by_name(doc_id: int, name: str) -> Optional[Dict]:
        """Find entity by exact or fuzzy name match"""
        with engine.connect() as conn:
            # Try exact match first
            normalized = name.lower().replace(" ", "_")
            result = conn.execute(text("""
                SELECT id, canonical_name, entity_type, attributes
                FROM kg_entities
                WHERE document_id = :doc_id AND normalized_key = :norm
            """), {"doc_id": doc_id, "norm": normalized})
            row = result.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "attributes": row[3] if row[3] else {}
                }
            
            # Try fuzzy match
            result = conn.execute(text("""
                SELECT id, canonical_name, entity_type, attributes
                FROM kg_entities
                WHERE document_id = :doc_id
                AND canonical_name ILIKE :pattern
                LIMIT 1
            """), {"doc_id": doc_id, "pattern": f"%{name}%"})
            row = result.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "attributes": row[3] if row[3] else {}
                }
            
            return None
    
    @staticmethod
    def get_entity_claims(entity_id: int, direction: str = "both") -> List[Dict]:
        """
        Get all claims involving an entity
        direction: 'outgoing' (entity is subject), 'incoming' (entity is object), 'both'
        """
        claims = []
        with engine.connect() as conn:
            if direction in ["outgoing", "both"]:
                result = conn.execute(text("""
                    SELECT c.id, c.predicate, c.object_value,
                           e.canonical_name as object_name, e.entity_type as object_type
                    FROM claims c
                    LEFT JOIN kg_entities e ON c.object_entity_id = e.id
                    WHERE c.subject_entity_id = :eid
                """), {"eid": entity_id})
                for row in result:
                    claims.append({
                        "direction": "outgoing",
                        "predicate": row[1],
                        "target_value": row[2],
                        "target_name": row[3],
                        "target_type": row[4]
                    })
            
            if direction in ["incoming", "both"]:
                result = conn.execute(text("""
                    SELECT c.id, c.predicate, c.object_value,
                           e.canonical_name as subject_name, e.entity_type as subject_type
                    FROM claims c
                    LEFT JOIN kg_entities e ON c.subject_entity_id = e.id
                    WHERE c.object_entity_id = :eid
                """), {"eid": entity_id})
                for row in result:
                    claims.append({
                        "direction": "incoming",
                        "predicate": row[1],
                        "source_name": row[3],
                        "source_type": row[4]
                    })
        
        return claims
    
    @staticmethod
    def traverse_from_entity(doc_id: int, entity_id: int, predicate: str = None, 
                             direction: str = "outgoing") -> List[Dict]:
        """
        Traverse claims from an entity, optionally filtering by predicate
        Returns connected entities
        """
        entities = []
        with engine.connect() as conn:
            if direction == "outgoing":
                query = """
                    SELECT e.id, e.canonical_name, e.entity_type, c.predicate
                    FROM claims c
                    JOIN kg_entities e ON c.object_entity_id = e.id
                    WHERE c.subject_entity_id = :eid
                """
                if predicate:
                    query += " AND c.predicate = :pred"
                result = conn.execute(text(query), {"eid": entity_id, "pred": predicate})
            else:  # incoming
                query = """
                    SELECT e.id, e.canonical_name, e.entity_type, c.predicate
                    FROM claims c
                    JOIN kg_entities e ON c.subject_entity_id = e.id
                    WHERE c.object_entity_id = :eid
                """
                if predicate:
                    query += " AND c.predicate = :pred"
                result = conn.execute(text(query), {"eid": entity_id, "pred": predicate})
            
            for row in result:
                entities.append({
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "predicate": row[3]
                })
        
        return entities
    
    @staticmethod
    def multi_hop_query(doc_id: int, start_entity_name: str, predicates: List[str]) -> List[Dict]:
        """
        Execute a multi-hop traversal starting from an entity name
        
        Example: multi_hop_query(1, "Policybazaar", ["OWNS", "CEO_OF"])
        Finds: X --OWNS--> Policybazaar, then Y --CEO_OF--> X
        Returns the final entities (Y in this case)
        """
        # Find starting entity
        start = KGRepository.find_entity_by_name(doc_id, start_entity_name)
        if not start:
            return []
        
        current_entities = [start]
        path = [start]
        
        for predicate in predicates:
            next_entities = []
            for entity in current_entities:
                # Try incoming (someone does predicate TO this entity)
                connected = KGRepository.traverse_from_entity(
                    doc_id, entity["id"], predicate, direction="incoming"
                )
                next_entities.extend(connected)
            
            if not next_entities:
                break
            
            current_entities = next_entities
            path.extend(next_entities)
        
        return current_entities
    
    @staticmethod
    def get_kg_context_for_question(doc_id: int, search_terms: List[str], max_hops: int = 2) -> str:
        """
        Build KG context for a question by:
        1. Finding entities matching search terms
        2. Getting their relationships
        3. Formatting as text context
        """
        context_parts = []
        seen_facts = set()
        
        # Find matching entities
        entities = KGRepository.search_entities(doc_id, search_terms, limit=5)
        
        for entity in entities:
            entity_id = entity["id"]
            entity_name = entity["name"]
            entity_type = entity["type"]
            
            # Add entity info
            context_parts.append(f"• {entity_name} ({entity_type})")
            
            # Get claims
            claims = KGRepository.get_entity_claims(entity_id, direction="both")
            
            for claim in claims:
                if claim["direction"] == "outgoing":
                    target = claim.get("target_name") or claim.get("target_value", "?")
                    fact = f"  → {entity_name} --[{claim['predicate']}]--> {target}"
                else:
                    source = claim.get("source_name", "?")
                    fact = f"  ← {source} --[{claim['predicate']}]--> {entity_name}"
                
                if fact not in seen_facts:
                    context_parts.append(fact)
                    seen_facts.add(fact)
        
        if context_parts:
            return "FROM KNOWLEDGE GRAPH:\n" + "\n".join(context_parts)
        else:
            return ""
