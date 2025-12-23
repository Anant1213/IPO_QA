#!/usr/bin/env python3
"""Test script to verify database search is filtering by document correctly."""

import sys
sys.path.insert(0, 'src')

from database.repositories import EmbeddingRepository
from utils.embedding_utils import get_embedding_model

# Get model 
print("Loading embedding model...")
model = get_embedding_model()

# Create embedding for 'who is ceo'
query = 'who is ceo'
embedding = model.encode([query], convert_to_numpy=True)[0]

print("\n" + "="*60)
print("Testing search for EMT IPO...")
print("="*60)
results = EmbeddingRepository.search_similar(
    query_embedding=embedding,
    document_id='emt_ipo',
    top_k=3
)

print(f"Found {len(results)} results for emt_ipo:")
for i, r in enumerate(results):
    print(f"\n--- Result {i+1} ---")
    print(f"Score: {r['similarity']:.4f}")
    print(f"Text: {r['text'][:200]}...")

print("\n" + "="*60)
print("Testing search for Policybazar IPO...")
print("="*60)
results2 = EmbeddingRepository.search_similar(
    query_embedding=embedding,
    document_id='policybazar_ipo',
    top_k=3
)

print(f"Found {len(results2)} results for policybazar_ipo:")
for i, r in enumerate(results2):
    print(f"\n--- Result {i+1} ---")
    print(f"Score: {r['similarity']:.4f}")
    print(f"Text: {r['text'][:200]}...")
