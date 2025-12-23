"""
Migrate existing file-based data to PostgreSQL database
"""
import json
import numpy as np
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database.repositories import DocumentRepository, ChunkRepository, EmbeddingRepository

def migrate_documents():
    """Migrate documents.json to database"""
    print("\n📄 Migrating documents...")
    
    documents_file = 'src/data/documents.json'
    
    if not os.path.exists(documents_file):
        print(f"❌ File not found: {documents_file}")
        return []
    
    with open(documents_file, 'r') as f:
        docs = json.load(f)
    
    migrated = []
    for doc in docs:
        try:
            result = DocumentRepository.create({
                'document_id': doc['document_id'],
                'filename': doc['filename'],
                'display_name': doc['display_name'],
                'file_hash': doc['file_hash'],
                'file_path': doc.get('file_path', f"uploads/{doc['filename']}"),
                'total_pages': doc.get('total_pages', 0),
                'total_chunks': doc.get('total_chunks', 0),
                'doc_metadata': {}
            })
            print(f"  ✅ {doc['document_id']}")
            migrated.append(doc['document_id'])
        except Exception as e:
            print(f"  ❌ {doc['document_id']}: {e}")
    
    print(f"\n✅ Migrated {len(migrated)}/{len(docs)} documents")
    return migrated

def migrate_document_chunks(document_id):
    """Migrate chunks and embeddings for a single document"""
    print(f"\n📦 Migrating chunks for {document_id}...")
    
    doc_folder = f"src/data/documents/{document_id}"
    
    # Check if folder exists
    if not os.path.exists(doc_folder):
        print(f"  ⚠️  Folder not found: {doc_folder}")
        return False
    
    # Load chunks
    chunks_file = f"{doc_folder}/chunks.json"
    if not os.path.exists(chunks_file):
        print(f"  ⚠️  Chunks file not found: {chunks_file}")
        return False
    
    with open(chunks_file, 'r') as f:
        chunks = json.load(f)
    
    # Load embeddings
    embeddings_file = f"{doc_folder}/embeddings.npy"
    if not os.path.exists(embeddings_file):
        print(f"  ⚠️  Embeddings file not found: {embeddings_file}")
        return False
    
    embeddings = np.load(embeddings_file)
    
    if len(chunks) != len(embeddings):
        print(f"  ❌ Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
        return False
    
    # Get document database ID
    doc = DocumentRepository.get_by_id(document_id)
    if not doc:
        print(f"  ❌ Document not found in database: {document_id}")
        return False
    
    doc_db_id = doc['id']
    
    print(f"  Processing {len(chunks)} chunks...")
    
    # Prepare chunk data for bulk insert
    chunks_data = []
    for idx, chunk in enumerate(chunks):
        chunks_data.append({
            'document_id': doc_db_id,
            'chunk_index': idx,
            'text': chunk['text'],
            'page_number': chunk.get('page_number'),
            'word_count': len(chunk['text'].split()),
            'chunk_metadata': {
                'page_numbers': chunk.get('page_numbers', []),
                'chapter': chunk.get('chapter', '')
            }
        })
    
    # Bulk insert chunks
    try:
        chunk_ids = ChunkRepository.create_many(chunks_data)
        print(f"  ✅ Inserted {len(chunk_ids)} chunks")
    except Exception as e:
        print(f"  ❌ Failed to insert chunks: {e}")
        return False
    
    # Prepare embedding data for bulk insert
    embeddings_data = []
    for chunk_id, embedding in zip(chunk_ids, embeddings):
        embeddings_data.append({
            'chunk_id': chunk_id,
            'embedding': embedding.tolist(),  # Convert numpy to list
            'model_name': 'all-MiniLM-L6-v2'
        })
    
    # Bulk insert embeddings
    try:
        count = EmbeddingRepository.create_many(embeddings_data)
        print(f"  ✅ Inserted {count} embeddings")
    except Exception as e:
        print(f"  ❌ Failed to insert embeddings: {e}")
        return False
    
    # Update document total_chunks
    DocumentRepository.update(document_id, {'total_chunks': len(chunks)})
    
    print(f"  ✅ Migration complete for {document_id}")
    return True

def main():
    """Main migration function"""
    print("=" * 60)
    print("  DATABASE MIGRATION")
    print("=" * 60)
    
    # Migrate documents first
    doc_ids = migrate_documents()
    
    if not doc_ids:
        print("\n❌ No documents to migrate")
        return
    
    # Migrate each document's chunks and embeddings
    success_count = 0
    for doc_id in doc_ids:
        if migrate_document_chunks(doc_id):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"  MIGRATION SUMMARY")
    print("=" * 60)
    print(f"  Documents: {len(doc_ids)}")
    print(f"  Successfully migrated: {success_count}")
    print(f"  Failed: {len(doc_ids) - success_count}")
    print("=" * 60)
    
    if success_count == len(doc_ids):
        print("\n✅ All data migrated successfully!")
    else:
        print("\n⚠️  Some migrations failed. Check logs above.")

if __name__ == '__main__':
    main()
