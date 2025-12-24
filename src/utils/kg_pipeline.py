"""
Production KG Extraction Pipeline
Multi-stage extraction with specialized prompts
"""

import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

from utils.deepseek_client import DeepSeekClient
from utils.kg_prompts import (
    DEFINITIONS_PROMPT,
    ENTITY_ATTRIBUTE_PROMPT,
    RELATIONSHIP_PROMPT,
    EVENT_PROMPT,
    ENTITY_RESOLUTION_PROMPT
)


class KGPipeline:
    """Production-grade Knowledge Graph extraction pipeline"""
    
    def __init__(self, use_local: bool = True):
        self.client = DeepSeekClient(use_local_fallback=use_local)
        self.pipeline_version = "2.0.0"
    
    def normalize_key(self, text: str) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        result = text.strip()
        result = re.sub(r'[–—]', '-', result)
        result = result.lower()
        result = re.sub(r'\s+', '_', result)
        return result
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response"""
        # Try to find JSON in response
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {}
    
    def _call_llm(self, prompt: str, max_tokens: int = 4096) -> Dict:
        """Call LLM and parse JSON response"""
        try:
            result = self.client.query(prompt, "", max_tokens=max_tokens)
            return self._extract_json(result)
        except Exception as e:
            print(f"LLM call failed: {e}")
            return {}
    
    # ==========================================
    # Stage 1: Definitions Extraction
    # ==========================================
    
    def extract_definitions(self, chunk: Dict) -> List[Dict]:
        """Extract defined terms from a chunk"""
        prompt = DEFINITIONS_PROMPT.format(
            chunk_text=chunk['text'],
            page_number=chunk.get('page_number', 0),
            section_title=chunk.get('section_title', ''),
            chunk_id=chunk.get('chunk_id', '')
        )
        
        result = self._call_llm(prompt)
        terms = result.get('defined_terms', [])
        
        # Post-process
        for term in terms:
            if 'term_normalized' not in term:
                term['term_normalized'] = self.normalize_key(term.get('term', ''))
        
        return terms
    
    # ==========================================
    # Stage 2: Entity + Attribute Extraction
    # ==========================================
    
    def extract_entities(self, chunk: Dict) -> List[Dict]:
        """Extract entities and attributes from a chunk"""
        prompt = ENTITY_ATTRIBUTE_PROMPT.format(
            chunk_text=chunk['text'],
            page_number=chunk.get('page_number', 0),
            section_title=chunk.get('section_title', ''),
            chunk_id=chunk.get('chunk_id', '')
        )
        
        result = self._call_llm(prompt)
        entities = result.get('entities', [])
        
        # Post-process
        for entity in entities:
            if 'normalized_key' not in entity:
                entity['normalized_key'] = self.normalize_key(entity.get('name', ''))
            # Validate entity type
            valid_types = ['Company', 'Person', 'Regulator', 'Exchange', 
                          'Auditor', 'Registrar', 'Security', 'Product', 'Location']
            if entity.get('type') not in valid_types:
                entity['type'] = 'Unknown'
        
        return entities
    
    # ==========================================
    # Stage 3: Relationship Extraction
    # ==========================================
    
    def extract_relationships(self, chunk: Dict, known_entities: List[str]) -> List[Dict]:
        """Extract relationships from a chunk"""
        entity_list = "\n".join([f"- {e}" for e in known_entities[:50]])  # Limit to 50
        
        prompt = RELATIONSHIP_PROMPT.format(
            chunk_text=chunk['text'],
            entity_list=entity_list,
            page_number=chunk.get('page_number', 0),
            section_title=chunk.get('section_title', ''),
            chunk_id=chunk.get('chunk_id', '')
        )
        
        result = self._call_llm(prompt)
        relationships = result.get('relationships', [])
        
        # Validate predicate types
        valid_predicates = [
            'subsidiary_of', 'parent_of', 'promoter_of', 'founder_of',
            'director_of', 'ceo_of', 'cfo_of', 'chairman_of',
            'auditor_of', 'registrar_of', 'regulated_by', 'listed_on',
            'shareholder_of', 'selling_shareholder_in'
        ]
        
        for rel in relationships:
            if rel.get('predicate') not in valid_predicates:
                rel['predicate'] = 'related_to'  # Fallback
        
        return relationships
    
    # ==========================================
    # Stage 4: Event Extraction
    # ==========================================
    
    def extract_events(self, chunk: Dict) -> List[Dict]:
        """Extract events from a chunk"""
        prompt = EVENT_PROMPT.format(
            chunk_text=chunk['text'],
            page_number=chunk.get('page_number', 0),
            section_title=chunk.get('section_title', ''),
            chunk_id=chunk.get('chunk_id', '')
        )
        
        result = self._call_llm(prompt)
        events = result.get('events', [])
        
        # Parse dates
        for event in events:
            if event.get('date') and not self._is_valid_date(event['date']):
                event['date'] = None  # Keep date_text only
        
        return events
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is valid YYYY-MM-DD format"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except (ValueError, TypeError):
            return False
    
    # ==========================================
    # Stage 5: Entity Resolution
    # ==========================================
    
    def resolve_entities(self, entities: List[Dict], batch_size: int = 20) -> Dict:
        """Find duplicate entities to merge"""
        # Process in batches
        all_merge_candidates = []
        all_aliases = []
        
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i+batch_size]
            batch_json = json.dumps(batch, indent=2)
            
            prompt = ENTITY_RESOLUTION_PROMPT.format(entity_batch_json=batch_json)
            result = self._call_llm(prompt)
            
            all_merge_candidates.extend(result.get('merge_candidates', []))
            all_aliases.extend(result.get('confirmed_aliases', []))
        
        return {
            'merge_candidates': all_merge_candidates,
            'confirmed_aliases': all_aliases
        }
    
    # ==========================================
    # Full Pipeline Execution
    # ==========================================
    
    def process_chunk(self, chunk: Dict, known_entities: List[str] = None) -> Dict:
        """Process a single chunk through all stages"""
        result = {
            'chunk_id': chunk.get('chunk_id'),
            'page_number': chunk.get('page_number'),
            'section_title': chunk.get('section_title'),
            'defined_terms': [],
            'entities': [],
            'relationships': [],
            'events': [],
            'errors': []
        }
        
        # Stage 1: Definitions
        try:
            result['defined_terms'] = self.extract_definitions(chunk)
        except Exception as e:
            result['errors'].append(f"definitions: {str(e)}")
        
        # Stage 2: Entities
        try:
            result['entities'] = self.extract_entities(chunk)
        except Exception as e:
            result['errors'].append(f"entities: {str(e)}")
        
        # Stage 3: Relationships (needs known entities)
        try:
            if known_entities is None:
                known_entities = [e['name'] for e in result['entities']]
            result['relationships'] = self.extract_relationships(chunk, known_entities)
        except Exception as e:
            result['errors'].append(f"relationships: {str(e)}")
        
        # Stage 4: Events
        try:
            result['events'] = self.extract_events(chunk)
        except Exception as e:
            result['errors'].append(f"events: {str(e)}")
        
        return result
    
    def process_document(
        self, 
        chunks: List[Dict], 
        progress_callback: callable = None
    ) -> Dict:
        """Process all chunks in a document"""
        all_results = {
            'pipeline_version': self.pipeline_version,
            'processed_at': datetime.now().isoformat(),
            'total_chunks': len(chunks),
            'defined_terms': [],
            'entities': [],
            'relationships': [],
            'events': [],
            'errors': []
        }
        
        known_entities = []
        
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i + 1, len(chunks))
            
            print(f"\rProcessing chunk {i+1}/{len(chunks)}...", end='', flush=True)
            
            result = self.process_chunk(chunk, known_entities)
            
            # Accumulate results
            all_results['defined_terms'].extend(result['defined_terms'])
            all_results['entities'].extend(result['entities'])
            all_results['relationships'].extend(result['relationships'])
            all_results['events'].extend(result['events'])
            all_results['errors'].extend(result['errors'])
            
            # Update known entities for next chunk
            known_entities.extend([e['name'] for e in result['entities']])
        
        print(f"\n✅ Processed {len(chunks)} chunks")
        
        # Stage 5: Entity resolution
        print("Resolving entities...")
        resolution = self.resolve_entities(all_results['entities'])
        all_results['merge_candidates'] = resolution['merge_candidates']
        all_results['confirmed_aliases'] = resolution['confirmed_aliases']
        
        # Summary stats
        all_results['summary'] = {
            'total_definitions': len(all_results['defined_terms']),
            'total_entities': len(all_results['entities']),
            'total_relationships': len(all_results['relationships']),
            'total_events': len(all_results['events']),
            'total_errors': len(all_results['errors']),
            'merge_candidates': len(all_results['merge_candidates'])
        }
        
        return all_results


# ==========================================
# Convenience function for CLI usage
# ==========================================

def run_pipeline(document_id: str, chunks_path: str, output_path: str):
    """Run pipeline on a document"""
    import json
    
    # Load chunks
    with open(chunks_path, 'r') as f:
        chunks = json.load(f)
    
    # Add chunk_id if missing
    for i, chunk in enumerate(chunks):
        if 'chunk_id' not in chunk:
            chunk['chunk_id'] = f"{document_id}_chunk_{i}"
    
    # Run pipeline
    pipeline = KGPipeline()
    results = pipeline.process_document(chunks)
    
    # Save results
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Results saved to {output_path}")
    print(f"   Definitions: {results['summary']['total_definitions']}")
    print(f"   Entities: {results['summary']['total_entities']}")
    print(f"   Relationships: {results['summary']['total_relationships']}")
    print(f"   Events: {results['summary']['total_events']}")
    
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        run_pipeline(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: python kg_pipeline.py <document_id> <chunks.json> <output.json>")
