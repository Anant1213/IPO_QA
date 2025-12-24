#!/usr/bin/env python3
"""
Build Knowledge Graph for a Document
Production pipeline that saves to PostgreSQL

Usage:
    python scripts/build_kg_v2.py --document policybazar_ipo
    python scripts/build_kg_v2.py --document policybazar_ipo --limit 10  # Test mode
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from utils.kg_pipeline import KGPipeline
from database.connection import get_db
from database.repositories import DocumentRepository
from database.kg_repositories import (
    EvidenceRepository, KGEntityRepository, DefinedTermRepository,
    ClaimRepository, EventRepository, ValidationReportRepository
)


def get_document_db_id(document_id: str) -> int:
    """Get database ID for document"""
    doc = DocumentRepository.get_by_id(document_id)
    if not doc:
        raise ValueError(f"Document not found: {document_id}")
    
    # Get actual DB ID
    with get_db() as db:
        from sqlalchemy import text
        result = db.execute(
            text("SELECT id FROM documents WHERE document_id = :doc_id"),
            {"doc_id": document_id}
        ).fetchone()
        if result:
            return result[0]
    raise ValueError(f"Document not in database: {document_id}")


def save_extraction_results(doc_db_id: int, results: dict):
    """Save extraction results to database"""
    
    stats = {
        'entities_saved': 0,
        'definitions_saved': 0,
        'claims_saved': 0,
        'events_saved': 0,
        'errors': []
    }
    
    # Entity ID mapping for relationships
    entity_id_map = {}
    
    print("\n📦 Saving to database...")
    
    # 1. Save entities
    print("  Saving entities...")
    for entity in results.get('entities', []):
        try:
            # Create evidence first
            evidence_id = None
            if entity.get('evidence'):
                ev = EvidenceRepository.create({
                    'document_id': doc_db_id,
                    'quote': entity['evidence'].get('quote', '')[:500],
                    'page_number': entity['evidence'].get('page'),
                    'section_title': entity['evidence'].get('section', '')
                })
                evidence_id = ev['id']
            
            # Create entity
            saved = KGEntityRepository.create({
                'document_id': doc_db_id,
                'entity_type': entity.get('type', 'Unknown'),
                'canonical_name': entity.get('name', 'Unknown'),
                'attributes': entity.get('attributes', {}),
                'confidence': entity.get('confidence', 1.0),
                'evidence_id': evidence_id
            })
            
            # Track for relationships
            norm_key = entity.get('normalized_key', entity.get('name', '').lower())
            entity_id_map[norm_key] = saved['id']
            entity_id_map[entity.get('name', '').lower()] = saved['id']
            
            stats['entities_saved'] += 1
            
        except Exception as e:
            stats['errors'].append(f"entity: {str(e)}")
    
    # 2. Save definitions
    print("  Saving definitions...")
    for term in results.get('defined_terms', []):
        try:
            evidence_id = None
            if term.get('evidence'):
                ev = EvidenceRepository.create({
                    'document_id': doc_db_id,
                    'quote': term['evidence'].get('quote', '')[:500],
                    'page_number': term['evidence'].get('page'),
                    'section_title': term['evidence'].get('section', '')
                })
                evidence_id = ev['id']
            
            DefinedTermRepository.create({
                'document_id': doc_db_id,
                'term': term.get('term', ''),
                'definition': term.get('definition', ''),
                'evidence_id': evidence_id
            })
            stats['definitions_saved'] += 1
            
        except Exception as e:
            stats['errors'].append(f"definition: {str(e)}")
    
    # 3. Save relationships as claims
    print("  Saving relationships...")
    for rel in results.get('relationships', []):
        try:
            subject_key = rel.get('subject', '').lower()
            object_key = rel.get('object', '').lower()
            
            subject_id = entity_id_map.get(subject_key)
            object_id = entity_id_map.get(object_key)
            
            if subject_id:
                evidence_id = None
                if rel.get('evidence'):
                    ev = EvidenceRepository.create({
                        'document_id': doc_db_id,
                        'quote': rel['evidence'].get('quote', '')[:500],
                        'page_number': rel['evidence'].get('page'),
                        'section_title': rel['evidence'].get('section', '')
                    })
                    evidence_id = ev['id']
                
                ClaimRepository.create({
                    'document_id': doc_db_id,
                    'subject_entity_id': subject_id,
                    'predicate': rel.get('predicate', 'related_to'),
                    'object_value': rel.get('object') if not object_id else None,
                    'object_entity_id': object_id,
                    'datatype': 'entity' if object_id else 'string',
                    'evidence_id': evidence_id
                })
                stats['claims_saved'] += 1
                
        except Exception as e:
            stats['errors'].append(f"relationship: {str(e)}")
    
    # 4. Save events
    print("  Saving events...")
    for event in results.get('events', []):
        try:
            evidence_id = None
            if event.get('evidence'):
                ev = EvidenceRepository.create({
                    'document_id': doc_db_id,
                    'quote': event['evidence'].get('quote', '')[:500],
                    'page_number': event['evidence'].get('page'),
                    'section_title': event['evidence'].get('section', '')
                })
                evidence_id = ev['id']
            
            EventRepository.create({
                'document_id': doc_db_id,
                'event_type': event.get('event_type', 'Unknown'),
                'event_date': event.get('date'),
                'event_date_text': event.get('date_text'),
                'description': event.get('description'),
                'evidence_id': evidence_id
            })
            stats['events_saved'] += 1
            
        except Exception as e:
            stats['errors'].append(f"event: {str(e)}")
    
    return stats


def build_kg(document_id: str, limit: int = None):
    """Build KG for a document"""
    
    print("=" * 60)
    print(f"🔨 BUILDING KNOWLEDGE GRAPH v2.0")
    print(f"   Document: {document_id}")
    print(f"   Limit: {limit or 'All chunks'}")
    print("=" * 60)
    
    # Get document DB ID
    doc_db_id = get_document_db_id(document_id)
    print(f"✅ Document found (DB ID: {doc_db_id})")
    
    # Load chunks
    chunks_path = f"data/documents/{document_id}/chunks.json"
    if not os.path.exists(chunks_path):
        raise FileNotFoundError(f"Chunks not found: {chunks_path}")
    
    with open(chunks_path, 'r') as f:
        chunks = json.load(f)
    
    print(f"📄 Loaded {len(chunks)} chunks")
    
    if limit:
        chunks = chunks[:limit]
        print(f"⚠️  Limited to {limit} chunks for testing")
    
    # Prepare chunks with metadata
    for i, chunk in enumerate(chunks):
        chunk['chunk_id'] = f"{document_id}_chunk_{i}"
        chunk['page_number'] = chunk.get('page_start', 0)
        chunk['section_title'] = chunk.get('chapter_name', '')
    
    # Run pipeline
    print("\n🚀 Running extraction pipeline...")
    pipeline = KGPipeline(use_local=True)
    results = pipeline.process_document(chunks)
    
    # Save to database
    save_stats = save_extraction_results(doc_db_id, results)
    
    # Save JSON backup
    output_dir = f"data/documents/{document_id}/knowledge_graph_v2"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = f"{output_dir}/extraction_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ KG BUILD COMPLETE")
    print("=" * 60)
    print(f"📊 Extraction Summary:")
    print(f"   Definitions: {results['summary']['total_definitions']}")
    print(f"   Entities: {results['summary']['total_entities']}")
    print(f"   Relationships: {results['summary']['total_relationships']}")
    print(f"   Events: {results['summary']['total_events']}")
    print(f"\n💾 Database Summary:")
    print(f"   Entities saved: {save_stats['entities_saved']}")
    print(f"   Definitions saved: {save_stats['definitions_saved']}")
    print(f"   Claims saved: {save_stats['claims_saved']}")
    print(f"   Events saved: {save_stats['events_saved']}")
    print(f"   Errors: {len(save_stats['errors'])}")
    print(f"\n📁 JSON backup: {output_file}")
    print("=" * 60)
    
    return results, save_stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build KG v2 for document')
    parser.add_argument('--document', '-d', required=True, help='Document ID')
    parser.add_argument('--limit', '-l', type=int, default=None, help='Limit chunks (for testing)')
    
    args = parser.parse_args()
    build_kg(args.document, args.limit)
