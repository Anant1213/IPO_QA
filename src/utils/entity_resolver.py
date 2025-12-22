"""
Entity Resolution - Merge duplicate entities and maintain canonical names
"""

from typing import List, Dict, Set, Tuple
from fuzzywuzzy import fuzz
import re


class EntityResolver:
    """Resolve and merge duplicate entities across extractions"""
    
    def __init__(self, similarity_threshold: int = 85):
        self.similarity_threshold = similarity_threshold
        self.canonical_map = {}  # alias -> canonical_id
        self.entity_registry = {}  # canonical_id -> entity_data
        
    def normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison"""
        # Remove common prefixes/suffixes
        name = re.sub(r'\b(Mr\.|Mrs\.|Ms\.|Dr\.|Ltd\.|Limited|Private|Pvt\.)\b', '', name, flags=re.IGNORECASE)
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Lowercase for comparison
        return name.lower().strip()
    
    def find_similar_entity(self, entity: Dict) -> Tuple[bool, str]:
        """
        Check if entity already exists with similar name
        
        Returns:
            (is_duplicate, canonical_id)
        """
        entity_name = entity['name']
        entity_type = entity['type']
        normalized = self.normalize_name(entity_name)
        
        # Check exact match first
        if normalized in self.canonical_map:
            return True, self.canonical_map[normalized]
        
        # Check fuzzy match among same entity type
        for canonical_id, canonical_entity in self.entity_registry.items():
            if canonical_entity['type'] != entity_type:
                continue
            
            canonical_name = canonical_entity['name']
            canonical_normalized = self.normalize_name(canonical_name)
            
            # Fuzzy string matching
            similarity = fuzz.ratio(normalized, canonical_normalized)
            
            if similarity >= self.similarity_threshold:
                # Found duplicate
                self.canonical_map[normalized] = canonical_id
                return True, canonical_id
        
        return False, None
    
    def register_entity(self, entity: Dict) -> str:
        """
        Register entity and return canonical ID
        
        Args:
            entity: Entity dict with 'id', 'name', 'type', 'attributes'
            
        Returns:
            Canonical entity ID
        """
        is_duplicate, canonical_id = self.find_similar_entity(entity)
        
        # Ensure attributes exist (fallback to empty dict)
        entity_attrs = entity.get('attributes', {})
        
        if is_duplicate:
            # Merge attributes
            self.merge_attributes(canonical_id, entity_attrs)
            return canonical_id
        else:
            # New entity - register it
            canonical_id = entity['id']
            # Ensure the copy has attributes
            entity_copy = entity.copy()
            if 'attributes' not in entity_copy:
                entity_copy['attributes'] = {}
            self.entity_registry[canonical_id] = entity_copy
            normalized = self.normalize_name(entity['name'])
            self.canonical_map[normalized] = canonical_id
            return canonical_id
    
    def merge_attributes(self, canonical_id: str, new_attributes: Dict):
        """Merge new attributes into existing entity"""
        canonical_entity = self.entity_registry[canonical_id]
        
        for key, value in new_attributes.items():
            if key not in canonical_entity['attributes']:
                # New attribute - add it
                canonical_entity['attributes'][key] = value
            else:
                # Attribute exists - keep more specific/recent value
                existing = canonical_entity['attributes'][key]
                if value and value != existing:
                    # Handle conflicts (simple strategy: keep longer/more detailed)
                    if isinstance(value, str) and isinstance(existing, str):
                        if len(value) > len(existing):
                            canonical_entity['attributes'][key] = value
                    else:
                        canonical_entity['attributes'][key] = value
    
    def resolve_extraction(self, extraction: Dict) -> Dict:
        """
        Resolve all entities in an extraction result
        
        Args:
            extraction: Dict with 'entities' and 'relationships'
            
        Returns:
            Resolved extraction with canonical entity IDs
        """
        id_mapping = {}  # original_id -> canonical_id
        resolved_entities = []
        
        # Process entities
        for entity in extraction.get('entities', []):
            canonical_id = self.register_entity(entity)
            id_mapping[entity['id']] = canonical_id
            resolved_entities.append({
                **entity,
                'canonical_id': canonical_id
            })
        # Update relationships with canonical IDs
        resolved_relationships = []
        for rel in extraction.get('relationships', []):
            # Handle missing source_id/target_id fields
            source_id = rel.get('source_id')
            target_id = rel.get('target_id')
            
            if not source_id or not target_id:
                # Skip invalid relationships
                continue
            
            # Map to canonical IDs
            canonical_source = id_mapping.get(source_id, source_id)
            canonical_target = id_mapping.get(target_id, target_id)
            
            resolved_relationships.append({
                **rel,
                'source_id': canonical_source,
                'target_id': canonical_target,
                'original_source_id': source_id,
                'original_target_id': target_id
            })
        
        return {
            'entities': resolved_entities,
            'relationships': resolved_relationships,
            'chunk_id': extraction.get('chunk_id'),
            'chapter_name': extraction.get('chapter_name')
        }
    
    def resolve_batch(self, extractions: List[Dict]) -> List[Dict]:
        """Resolve entities across multiple extractions"""
        resolved = []
        
        for extraction in extractions:
            resolved_extraction = self.resolve_extraction(extraction)
            resolved.append(resolved_extraction)
        
        return resolved
    
    def get_entity_by_id(self, entity_id: str) -> Dict:
        """Get canonical entity by ID"""
        return self.entity_registry.get(entity_id)
    
    def get_all_entities(self) -> List[Dict]:
        """Get all unique canonical entities"""
        return list(self.entity_registry.values())
    
    def get_statistics(self) -> Dict:
        """Get resolution statistics"""
        entity_types = {}
        for entity in self.entity_registry.values():
            entity_type = entity['type']
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        return {
            'total_unique_entities': len(self.entity_registry),
            'total_aliases': len(self.canonical_map),
            'entity_type_counts': entity_types,
            'deduplication_ratio': len(self.canonical_map) / max(len(self.entity_registry), 1)
        }
