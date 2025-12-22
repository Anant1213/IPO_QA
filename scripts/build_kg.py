"""
Production Knowledge Graph Extraction Pipeline
Parallel processing with 10 cores for fast extraction
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from utils.kg_extractor import KnowledgeGraphExtractor
from utils.entity_resolver import EntityResolver
from utils.graph_store import GraphStore


def extract_batch(batch_args):
    """Extract entities from a batch of chunks (runs in separate process)"""
    chunks, schema_path = batch_args
    
    # Initialize extractor in each process
    extractor = KnowledgeGraphExtractor(schema_path=schema_path)
    
    print(f"Process {os.getpid()}: Processing {len(chunks)} chunks...")
    
    results = []
    for chunk in chunks:
        try:
            extraction = extractor.extract_from_chunk(chunk['text'])
            extraction['chunk_id'] = chunk.get('chunk_id')
            extraction['chapter_name'] = chunk.get('chapter_name', '')
            extraction['page_start'] = chunk.get('page_start')
            results.append(extraction)
        except Exception as e:
            print(f"Error in chunk {chunk.get('chunk_id')}: {e}")
            results.append({
                'chunk_id': chunk.get('chunk_id'),
                'entities': [],
                'relationships': [],
                'error': str(e)
            })
    
    return results


def build_knowledge_graph(document_id: str, num_workers: int = 10, max_chunks: int = None):
    """
    Build knowledge graph for a document using parallel processing
    
    Args:
        document_id: Document folder name
        num_workers: Number of parallel workers (cores)
        max_chunks: Limit chunks for testing (None = process all)
    """
    
    print("=" * 80)
    print(f"KNOWLEDGE GRAPH EXTRACTION - PARALLEL PROCESSING")
    print(f"Document: {document_id}")
    print(f"Workers: {num_workers} cores")
    print("=" * 80)
    
    # Load chunks
    doc_folder = f"data/documents/{document_id}"
    chunks_file = f"{doc_folder}/chunks.json"
    
    if not os.path.exists(chunks_file):
        print(f"❌ Error: Chunks file not found: {chunks_file}")
        return
    
    print(f"\n1. Loading chunks from {chunks_file}...")
    with open(chunks_file, 'r') as f:
        chunks = json.load(f)
    
    total_chunks = len(chunks)
    print(f"   Total chunks: {total_chunks}")
    
    # Limit for testing
    if max_chunks and max_chunks < total_chunks:
        chunks = chunks[:max_chunks]
        print(f"   ⚠️  Limited to first {max_chunks} chunks for testing")
    
    # Split into batches for parallel processing
    batch_size = max(1, len(chunks) // num_workers)
    batches = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batches.append((batch, "schema.json"))
    
    print(f"\n2. Extracting entities and relationships...")
    print(f"   Batches: {len(batches)} (batch size: ~{batch_size} chunks)")
    print(f"   Model: llama3:latest")
    
    # Parallel extraction
    start_time = time.time()
    all_extractions = []
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all batches
        futures = {executor.submit(extract_batch, batch): i for i, batch in enumerate(batches)}
        
        # Collect results as they complete
        completed = 0
        for future in as_completed(futures):
            batch_num = futures[future]
            try:
                batch_results = future.result()
                all_extractions.extend(batch_results)
                completed += 1
                
                # Progress update
                progress = (completed / len(batches)) * 100
                elapsed = time.time() - start_time
                print(f"   Progress: {completed}/{len(batches)} batches ({progress:.1f}%) - {elapsed:.1f}s elapsed")
                
            except Exception as e:
                print(f"   ❌ Batch {batch_num} failed: {e}")
    
    extraction_time = time.time() - start_time
    print(f"\n   ✓ Extraction complete in {extraction_time:.1f} seconds")
    print(f"   Average: {extraction_time / len(chunks):.2f}s per chunk")
    
    # Save raw extractions
    output_dir = f"{doc_folder}/knowledge_graph"
    os.makedirs(output_dir, exist_ok=True)
    
    extractions_file = f"{output_dir}/raw_extractions.json"
    print(f"\n3. Saving raw extractions to {extractions_file}...")
    with open(extractions_file, 'w') as f:
        json.dump(all_extractions, f, indent=2)
    
    # Count entities and relationships
    total_entities = sum(len(e.get('entities', [])) for e in all_extractions)
    total_relationships = sum(len(e.get('relationships', [])) for e in all_extractions)
    print(f"   ✓ Extracted {total_entities} entities, {total_relationships} relationships")
    
    # Entity resolution
    print(f"\n4. Resolving duplicate entities...")
    resolver = EntityResolver(similarity_threshold=85)
    
    resolved_start = time.time()
    resolved_extractions = resolver.resolve_batch(all_extractions)
    resolution_time = time.time() - resolved_start
    
    stats = resolver.get_statistics()
    print(f"   ✓ Resolution complete in {resolution_time:.1f}s")
    print(f"   Unique entities: {stats['total_unique_entities']}")
    print(f"   Entity types: {stats['entity_type_counts']}")
    print(f"   Deduplication ratio: {stats['deduplication_ratio']:.2f}")
    
    # Save resolved extractions
    resolved_file = f"{output_dir}/resolved_extractions.json"
    print(f"\n5. Saving resolved extractions to {resolved_file}...")
    with open(resolved_file, 'w') as f:
        json.dump(resolved_extractions, f, indent=2)
    
    # Save unique entities
    entities_file = f"{output_dir}/entities.json"
    print(f"   Saving unique entities to {entities_file}...")
    with open(entities_file, 'w') as f:
        json.dump(resolver.get_all_entities(), f, indent=2)
    
    # Build graph
    print(f"\n6. Building knowledge graph...")
    graph_start = time.time()
    
    graph = GraphStore()
    graph.build_from_extractions(resolved_extractions)
    
    graph_time = time.time() - graph_start
    print(f"   ✓ Graph built in {graph_time:.1f}s")
    
    # Graph statistics
    graph_stats = graph.get_statistics()
    print(f"\n   Graph Statistics:")
    print(f"   - Nodes: {graph_stats['num_nodes']}")
    print(f"   - Edges: {graph_stats['num_edges']}")
    print(f"   - Connected: {graph_stats['is_connected']}")
    print(f"   - Components: {graph_stats['num_connected_components']}")
    print(f"   - Density: {graph_stats['density']:.4f}")
    
    # Save graph
    graph_file = f"{output_dir}/knowledge_graph.json"
    print(f"\n7. Saving knowledge graph to {graph_file}...")
    graph.save(graph_file)
    
    # Save visualization export
    viz_file = f"{output_dir}/graph_viz.json"
    print(f"   Saving visualization data to {viz_file}...")
    viz_data = graph.export_for_visualization()
    with open(viz_file, 'w') as f:
        json.dump(viz_data, f, indent=2)
    
    # Summary
    total_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Chunks processed: {len(chunks)}")
    print(f"Entities extracted: {total_entities} → {stats['total_unique_entities']} unique")
    print(f"Relationships: {total_relationships}")
    print(f"Graph nodes: {graph_stats['num_nodes']}")
    print(f"Graph edges: {graph_stats['num_edges']}")
    print(f"\nOutput directory: {output_dir}/")
    print("=" * 80)
    
    return graph, resolver, all_extractions


def main():
    parser = argparse.ArgumentParser(description='Build Knowledge Graph from IPO Document')
    parser.add_argument('--document', type=str, required=True, 
                       help='Document ID (folder name in data/documents/)')
    parser.add_argument('--workers', type=int, default=10,
                       help='Number of parallel workers (default: 10)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of chunks for testing (default: all)')
    
    args = parser.parse_args()
    
    build_knowledge_graph(
        document_id=args.document,
        num_workers=args.workers,
        max_chunks=args.limit
    )


if __name__ == "__main__":
    main()
