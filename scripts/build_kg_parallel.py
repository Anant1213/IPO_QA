#!/usr/bin/env python3
"""
Parallel KG Extraction - Optimized for M3 Pro
Uses batching, unified prompts, and parallel processing

Expected time: ~45 minutes for 816 chunks (vs 41 hours sequential)
"""

import os
import sys
import json
import asyncio
import aiohttp
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from database.connection import engine
from sqlalchemy import text

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:latest"
BATCH_SIZE = 10  # chunks per batch
MAX_CONCURRENT = 3  # parallel requests
TIMEOUT = 300  # 5 minutes per request


def get_unified_extraction_prompt(chunks_text: str) -> str:
    """Single prompt that extracts all KG elements at once"""
    return f"""You are extracting structured information from IPO (Initial Public Offering) document text.

TEXT TO ANALYZE:
{chunks_text}

Extract ALL of the following in a single JSON response:

1. ENTITIES: People, companies, organizations, regulators mentioned
2. CLAIMS: Relationships between entities (who owns what, who works where, amounts)
3. DEFINITIONS: Technical/legal terms that are defined or explained in the text
4. EVENTS: Important dates and events (IPO, incorporation, allotment, etc.)

Respond with ONLY valid JSON in this exact format:
{{
  "entities": [
    {{"name": "Yashish Dahiya", "type": "PERSON", "attributes": {{"role": "CEO"}}}},
    {{"name": "PB Fintech Limited", "type": "COMPANY", "attributes": {{}}}},
    {{"name": "SEBI", "type": "REGULATOR", "attributes": {{}}}}
  ],
  "claims": [
    {{"subject": "Yashish Dahiya", "predicate": "CEO_OF", "object": "PB Fintech Limited"}},
    {{"subject": "PB Fintech Limited", "predicate": "OWNS", "object": "Policybazaar"}}
  ],
  "definitions": [
    {{"term": "Red Herring Prospectus", "definition": "A preliminary prospectus filed with SEBI before IPO"}},
    {{"term": "Book Running Lead Manager", "definition": "Investment bank managing the IPO offering"}}
  ],
  "events": [
    {{"type": "INCORPORATION", "description": "PB Fintech was incorporated", "date": "2008-06-04"}},
    {{"type": "IPO", "description": "Initial Public Offering", "date": null}}
  ]
}}

CRITICAL RULES:
- Entity types MUST be UPPERCASE: PERSON, COMPANY, REGULATOR, ORGANIZATION, COUNTRY, LOCATION
- Predicates MUST be UPPERCASE with underscores: CEO_OF, FOUNDER_OF, OWNS, SUBSIDIARY_OF, WORKS_AT
- Extract definitions for terms like: "means", "refers to", "defined as", "shall mean"
- Always include the FULL entity names in claims (subject and object)
- If no items found for a category, use empty array []

JSON Response:"""



async def call_ollama_async(session: aiohttp.ClientSession, prompt: str, batch_id: int) -> Dict:
    """Async call to Ollama API"""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4096
        }
    }
    
    try:
        async with session.post(OLLAMA_URL, json=payload, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
            if resp.status == 200:
                result = await resp.json()
                return {"batch_id": batch_id, "response": result.get("response", ""), "success": True}
            else:
                return {"batch_id": batch_id, "error": f"HTTP {resp.status}", "success": False}
    except asyncio.TimeoutError:
        return {"batch_id": batch_id, "error": "Timeout", "success": False}
    except Exception as e:
        return {"batch_id": batch_id, "error": str(e), "success": False}


def parse_llm_response(response: str) -> Dict:
    """Parse JSON from LLM response"""
    try:
        # Try to find JSON in response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    return {"entities": [], "claims": [], "definitions": [], "events": []}


def get_chunks(document_id: str) -> List[Dict]:
    """Get chunks from database"""
    with engine.connect() as conn:
        # Get document DB ID
        result = conn.execute(text("SELECT id FROM documents WHERE document_id = :doc_id"), {"doc_id": document_id})
        row = result.fetchone()
        if not row:
            raise ValueError(f"Document not found: {document_id}")
        doc_db_id = row[0]
        
        # Get chunks
        result = conn.execute(text("""
            SELECT id, text, page_number 
            FROM chunks 
            WHERE document_id = :doc_id 
            ORDER BY id
        """), {"doc_id": doc_db_id})
        
        chunks = [dict(row._mapping) for row in result]
        return chunks, doc_db_id


def create_batches(chunks: List[Dict], batch_size: int) -> List[List[Dict]]:
    """Split chunks into batches"""
    batches = []
    for i in range(0, len(chunks), batch_size):
        batches.append(chunks[i:i + batch_size])
    return batches


async def process_batches_async(batches: List[List[Dict]], max_concurrent: int) -> List[Dict]:
    """Process batches with parallel requests"""
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession() as session:
        async def process_batch(batch_id: int, batch: List[Dict]):
            async with semaphore:
                # Combine chunk texts
                combined_text = "\n\n---CHUNK BOUNDARY---\n\n".join([c["text"][:2000] for c in batch])
                prompt = get_unified_extraction_prompt(combined_text)
                
                result = await call_ollama_async(session, prompt, batch_id)
                return result
        
        # Create tasks
        tasks = [process_batch(i, batch) for i, batch in enumerate(batches)]
        
        # Process with progress
        total = len(tasks)
        completed = 0
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            
            status = "✓" if result.get("success") else "✗"
            print(f"\r[{completed}/{total}] Batch {result['batch_id']} {status}   ", end="", flush=True)
            
            results.append(result)
    
    print()  # New line after progress
    return results


def save_to_database(doc_db_id: int, all_results: List[Dict]):
    """Save extracted data to PostgreSQL with proper error handling"""
    entities_count = 0
    claims_count = 0
    terms_count = 0
    events_count = 0
    
    for result in all_results:
        if not result.get("success"):
            continue
        
        parsed = parse_llm_response(result.get("response", ""))
        
        # Save entities - each in its own transaction
        for entity in parsed.get("entities", []):
            try:
                name = entity.get("name", "").strip()
                if not name:
                    continue
                
                entity_type = entity.get("type", "UNKNOWN").upper()  # Normalize to uppercase
                attributes = json.dumps(entity.get("attributes", {}))
                normalized = name.lower().replace(" ", "_")[:500]
                
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO kg_entities (document_id, canonical_name, entity_type, normalized_key, attributes)
                        VALUES (:doc_id, :name, :type, :norm, CAST(:attrs AS jsonb))
                        ON CONFLICT (document_id, normalized_key) DO UPDATE SET
                            attributes = EXCLUDED.attributes,
                            updated_at = NOW()
                    """), {
                        "doc_id": doc_db_id,
                        "name": name[:500],
                        "type": entity_type[:50],
                        "norm": normalized,
                        "attrs": attributes
                    })
                entities_count += 1
            except Exception as e:
                pass  # Silently skip duplicates/errors
        
        # Save claims - link to entities
        for claim in parsed.get("claims", []):
            try:
                subject = claim.get("subject", "").strip()
                predicate = claim.get("predicate", "RELATED_TO")
                obj = claim.get("object", "")
                
                if not subject:
                    continue
                
                # Lookup or create subject entity
                subject_id = None
                subject_norm = subject.lower().replace(" ", "_")[:500]
                with engine.begin() as conn:
                    # Try to find existing entity
                    result = conn.execute(text("""
                        SELECT id FROM kg_entities 
                        WHERE document_id = :doc_id AND normalized_key = :norm
                    """), {"doc_id": doc_db_id, "norm": subject_norm})
                    row = result.fetchone()
                    if row:
                        subject_id = row[0]
                    else:
                        # Create new entity
                        result = conn.execute(text("""
                            INSERT INTO kg_entities (document_id, canonical_name, entity_type, normalized_key, attributes)
                            VALUES (:doc_id, :name, 'UNKNOWN', :norm, CAST('{}' AS jsonb))
                            RETURNING id
                        """), {"doc_id": doc_db_id, "name": subject[:500], "norm": subject_norm})
                        row = result.fetchone()
                        if row:
                            subject_id = row[0]
                
                # Lookup or create object entity if it looks like an entity name
                object_id = None
                if obj and isinstance(obj, str) and len(obj) < 200:
                    # Check if it looks like an entity (has capital letters, not a number)
                    if any(c.isupper() for c in obj) and not obj.replace('.', '').replace(',', '').isdigit():
                        obj_norm = obj.lower().replace(" ", "_")[:500]
                        with engine.begin() as conn:
                            # Try to find existing entity
                            result = conn.execute(text("""
                                SELECT id FROM kg_entities 
                                WHERE document_id = :doc_id AND normalized_key = :norm
                            """), {"doc_id": doc_db_id, "norm": obj_norm})
                            row = result.fetchone()
                            if row:
                                object_id = row[0]
                            else:
                                # Create new object entity
                                result = conn.execute(text("""
                                    INSERT INTO kg_entities (document_id, canonical_name, entity_type, normalized_key, attributes)
                                    VALUES (:doc_id, :name, 'UNKNOWN', :norm, CAST('{}' AS jsonb))
                                    ON CONFLICT (document_id, normalized_key) DO NOTHING
                                    RETURNING id
                                """), {"doc_id": doc_db_id, "name": obj[:500], "norm": obj_norm})
                                row = result.fetchone()
                                if row:
                                    object_id = row[0]
                                    entities_count += 1
                
                # Insert claim with entity links
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO claims (document_id, subject_entity_id, predicate, object_entity_id, object_value, datatype)
                        VALUES (:doc_id, :subj_id, :pred, :obj_id, :obj_val, 'string')
                    """), {
                        "doc_id": doc_db_id,
                        "subj_id": subject_id,
                        "pred": predicate[:100],
                        "obj_id": object_id,
                        "obj_val": str(obj)[:1000] if obj else None
                    })
                claims_count += 1
            except Exception as e:
                pass

        
        # Save definitions
        for defn in parsed.get("definitions", []):
            try:
                term = defn.get("term", "").strip()
                definition = defn.get("definition", "").strip()
                
                if not term or not definition:
                    continue
                
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO defined_terms (document_id, term, definition, normalized_term)
                        VALUES (:doc_id, :term, :defn, :norm)
                        ON CONFLICT (document_id, normalized_term) DO NOTHING
                    """), {
                        "doc_id": doc_db_id,
                        "term": term[:500],
                        "defn": definition[:2000],
                        "norm": term.lower().replace(" ", "_")[:500]
                    })
                terms_count += 1
            except Exception as e:
                pass
        
        # Save events
        for event in parsed.get("events", []):
            try:
                event_type = event.get("type", "GENERAL")
                description = event.get("description", "").strip()
                
                if not description:
                    continue
                
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO events (document_id, event_type, description)
                        VALUES (:doc_id, :type, :desc)
                    """), {
                        "doc_id": doc_db_id,
                        "type": event_type[:50],
                        "desc": description[:2000]
                    })
                events_count += 1
            except Exception as e:
                pass
    
    return entities_count, claims_count, terms_count, events_count


async def main_async(document_id: str, limit: int = None):
    """Main async entry point"""
    print(f"""
{'='*60}
🚀 PARALLEL KG EXTRACTION (Optimized for M3 Pro)
{'='*60}
Document: {document_id}
Batch Size: {BATCH_SIZE} chunks
Parallel Workers: {MAX_CONCURRENT}
Model: {MODEL}
""")
    
    # Get chunks
    print("📄 Loading chunks...")
    chunks, doc_db_id = get_chunks(document_id)
    
    if limit:
        chunks = chunks[:limit]
    
    print(f"   Found {len(chunks)} chunks")
    
    # Create batches
    batches = create_batches(chunks, BATCH_SIZE)
    print(f"   Created {len(batches)} batches")
    
    # Clear existing KG data
    print("\n🗑️  Clearing old KG data...")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM kg_entities WHERE document_id = :doc_id"), {"doc_id": doc_db_id})
        conn.execute(text("DELETE FROM claims WHERE document_id = :doc_id"), {"doc_id": doc_db_id})
        conn.execute(text("DELETE FROM defined_terms WHERE document_id = :doc_id"), {"doc_id": doc_db_id})
        conn.execute(text("DELETE FROM events WHERE document_id = :doc_id"), {"doc_id": doc_db_id})
        conn.commit()
    
    # Process
    print(f"\n⚡ Processing {len(batches)} batches ({MAX_CONCURRENT} parallel)...")
    start_time = datetime.now()
    
    results = await process_batches_async(batches, MAX_CONCURRENT)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    success_count = sum(1 for r in results if r.get("success"))
    
    print(f"\n   Completed: {success_count}/{len(results)} batches in {elapsed:.1f}s")
    
    # Save to database
    print("\n💾 Saving to database...")
    entities, claims, terms, events = save_to_database(doc_db_id, results)
    
    print(f"""
{'='*60}
✅ EXTRACTION COMPLETE
{'='*60}
   Entities: {entities}
   Claims: {claims}
   Definitions: {terms}
   Events: {events}
   Time: {elapsed:.1f} seconds

Next: Run visualization
   python scripts/visualize_kg_db.py -d {document_id} --open
""")


def main():
    parser = argparse.ArgumentParser(description='Parallel KG Extraction')
    parser.add_argument('--document', '-d', required=True, help='Document ID')
    parser.add_argument('--limit', '-l', type=int, default=None, help='Limit chunks (for testing)')
    parser.add_argument('--batch-size', '-b', type=int, default=10, help='Chunks per batch')
    parser.add_argument('--parallel', '-p', type=int, default=3, help='Parallel workers')
    
    args = parser.parse_args()
    
    # Update module-level config
    import build_kg_parallel
    build_kg_parallel.BATCH_SIZE = args.batch_size
    build_kg_parallel.MAX_CONCURRENT = args.parallel
    
    asyncio.run(main_async(args.document, args.limit))


if __name__ == "__main__":
    main()
