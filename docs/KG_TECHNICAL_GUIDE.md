# Knowledge Graph (KG) - Complete Technical Guide

## Table of Contents
1. [What is a Knowledge Graph?](#what-is-a-knowledge-graph)
2. [Core Concepts](#core-concepts)
3. [Vector Database & Embeddings](#vector-database--embeddings)
4. [Side-by-Side: Vector RAG vs KG-RAG](#side-by-side-vector-rag-vs-kg-rag)
5. [How Our KG is Structured](#how-our-kg-is-structured)
6. [The Extraction Pipeline](#the-extraction-pipeline)
7. [Multi-Hop Relationships](#multi-hop-relationships)
8. [How RAG Uses the KG](#how-rag-uses-the-kg)
9. [Database Schema](#database-schema)

---

## Vector Database & Embeddings

### What We Use

| Component | Technology | Description |
|-----------|------------|-------------|
| **Vector Database** | PostgreSQL + pgvector | Vector storage and similarity search |
| **Embedding Model** | all-MiniLM-L6-v2 | 384-dimensional sentence embeddings |
| **Index Type** | HNSW | Fast approximate nearest neighbor search |

### How Embeddings Work

**Step 1: Text → Numbers**
```
"PB Fintech is an insurance company" 
    ↓
    [0.023, -0.156, 0.089, ..., 0.041]  (384 numbers)
```

**Step 2: Store in PostgreSQL**
```sql
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES chunks(id),
    embedding VECTOR(384)  -- pgvector type
);
```

**Step 3: Find Similar Text (Cosine Similarity)**
```sql
-- Find chunks similar to question
SELECT chunk_id, 1 - (embedding <=> :question_embedding) as similarity
FROM embeddings
ORDER BY embedding <=> :question_embedding
LIMIT 5;
```

### pgvector Distance Operators

| Operator | Distance Type | Use Case |
|----------|--------------|----------|
| `<=>` | Cosine distance | Text similarity (most common) |
| `<->` | L2 (Euclidean) | Geometric distance |
| `<#>` | Inner product | Normalized vectors |

---

## Side-by-Side: Vector RAG vs KG-RAG

### Complete Flow Comparison

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              VECTOR RAG (Traditional)                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────┐    ┌───────────┐    ┌───────────────┐    ┌───────────┐    ┌────────┐ │
│  │ Question │───▶│  Embed    │───▶│ Vector Search │───▶│ Top-K     │───▶│  LLM   │ │
│  │          │    │ (384-dim) │    │ (pgvector)    │    │ Chunks    │    │ Answer │ │
│  └──────────┘    └───────────┘    └───────────────┘    └───────────┘    └────────┘ │
│                                                                                      │
│  Example: "Who is CEO of Policybazaar?"                                             │
│                                                                                      │
│  ✅ Finds chunks mentioning "CEO" and "Policybazaar"                                │
│  ❌ May miss if CEO name is in different chunk                                       │
│  ❌ No explicit relationship understanding                                           │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              KG-ENHANCED RAG (Our System)                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────┐                                                                        │
│  │ Question │                                                                        │
│  └────┬─────┘                                                                        │
│       │                                                                              │
│       ├──────────────────────────────────────┐                                       │
│       │                                      │                                       │
│       ▼                                      ▼                                       │
│  ┌───────────────────────┐          ┌───────────────────────┐                       │
│  │     VECTOR PATH       │          │       KG PATH          │                       │
│  │                       │          │                        │                       │
│  │ ┌─────────────────┐   │          │ ┌──────────────────┐   │                       │
│  │ │ Embed Question  │   │          │ │ Extract Entities │   │                       │
│  │ │ (384 dimensions)│   │          │ │ "Policybazaar"   │   │                       │
│  │ └────────┬────────┘   │          │ └────────┬─────────┘   │                       │
│  │          ▼            │          │          ▼             │                       │
│  │ ┌─────────────────┐   │          │ ┌──────────────────┐   │                       │
│  │ │ pgvector Search │   │          │ │ Lookup Entity    │   │                       │
│  │ │ cosine distance │   │          │ │ in kg_entities   │   │                       │
│  │ └────────┬────────┘   │          │ └────────┬─────────┘   │                       │
│  │          ▼            │          │          ▼             │                       │
│  │ ┌─────────────────┐   │          │ ┌──────────────────┐   │                       │
│  │ │ Top-K Chunks    │   │          │ │ Traverse Claims  │   │                       │
│  │ │ (text excerpts) │   │          │ │ (multi-hop)      │   │                       │
│  │ └────────┬────────┘   │          │ └────────┬─────────┘   │                       │
│  │          │            │          │          │             │                       │
│  └──────────┼────────────┘          └──────────┼─────────────┘                       │
│             │                                  │                                     │
│             └───────────────┬──────────────────┘                                     │
│                             ▼                                                        │
│                    ┌────────────────┐                                                │
│                    │ COMBINE CONTEXT│                                                │
│                    │                │                                                │
│                    │ Text chunks +  │                                                │
│                    │ KG facts       │                                                │
│                    └───────┬────────┘                                                │
│                            ▼                                                         │
│                    ┌────────────────┐                                                │
│                    │      LLM       │                                                │
│                    │   (Ollama)     │                                                │
│                    └───────┬────────┘                                                │
│                            ▼                                                         │
│                    ┌────────────────┐                                                │
│                    │ BETTER ANSWER  │                                                │
│                    └────────────────┘                                                │
│                                                                                      │
│  ✅ Finds relevant text chunks                                                       │
│  ✅ Finds explicit relationship: Yashish Dahiya → CEO_OF → PB Fintech → OWNS         │
│  ✅ Multi-hop reasoning across entities                                              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Comparison

| Step | Vector RAG | KG-Enhanced RAG |
|------|------------|-----------------|
| **1. Input** | "Who is CEO of company owning Policybazaar?" | Same question |
| **2. Process** | Embed → Search similar chunks | Embed + Extract entities |
| **3. Search** | Find top-5 similar text chunks | Find chunks + lookup "Policybazaar" entity |
| **4. Reasoning** | LLM reads chunks, hopes answer is there | Traverse: Policybazaar ← OWNS ← PB Fintech ← CEO_OF ← Yashish |
| **5. Context** | Only text excerpts | Text + structured facts |
| **6. Answer** | May be incomplete | Complete and verified |

### Example: Same Question, Different Approaches

**Question:** "Who are all the independent directors at PB Fintech?"

#### Vector RAG Approach:
```
1. Embed question → [0.12, -0.34, ...]
2. pgvector search → Find similar chunks
3. Results:
   - Chunk 45: "...Ms. Lilian Jessie Paul serves as..."
   - Chunk 102: "...appointed as independent director..."
   - Chunk 278: "...governance structure includes..."
4. LLM reads chunks → Answers with whatever names it finds
5. PROBLEM: Might miss directors mentioned in other chunks!
```

#### KG-Enhanced RAG Approach:
```
1. Embed question → Same vector search
2. Extract entity: "PB Fintech"
3. KG Lookup: Find entity ID = 456
4. KG Traverse: Find all → INDEPENDENT_DIRECTOR_OF → 456
5. KG Returns:
   ┌─────────────────────────────────────┐
   │ Gopalan Srinivasan                  │
   │ Lilian Jessie Paul                  │
   │ Kitty Agarwal                       │
   └─────────────────────────────────────┘
6. Combine with text chunks for context
7. LLM has COMPLETE list → Accurate answer!
```

### When Each Approach Shines

| Scenario | Best Approach | Why |
|----------|---------------|-----|
| "What does the document say about risks?" | Vector RAG | Needs text understanding |
| "Who owns Policybazaar?" | KG-RAG | Direct relationship lookup |
| "List all subsidiaries" | KG-RAG | Entity traversal |
| "Explain the business model" | Vector RAG | Needs context synthesis |
| "Who is CEO of subsidiary X?" | KG-RAG | Multi-hop relationship |
| "What are the key financials?" | Both | Text + structured data |



---

## What is a Knowledge Graph?

A **Knowledge Graph** is a structured way to represent real-world entities and their relationships. Unlike plain text, a KG stores facts as **triples**:

```
(Subject) --[Predicate]--> (Object)
```

**Example:**
```
(Yashish Dahiya) --[CEO_OF]--> (PB Fintech Limited)
```

This means:
- **Subject**: Yashish Dahiya (a PERSON entity)
- **Predicate**: CEO_OF (the relationship type)
- **Object**: PB Fintech Limited (a COMPANY entity)

---

## Core Concepts

### 1. Entities (Nodes)

Entities are the **things** we extract from documents. Each entity has:

| Property | Description | Example |
|----------|-------------|---------|
| `canonical_name` | Official name | "PB Fintech Limited" |
| `entity_type` | Category | PERSON, COMPANY, REGULATOR |
| `normalized_key` | Lookup key | "pb_fintech_limited" |
| `attributes` | Extra info (JSON) | `{"role": "CEO"}` |

**Entity Types in our KG:**
- **PERSON**: People (CEOs, Directors, Founders)
- **COMPANY**: Companies and subsidiaries
- **REGULATOR**: SEBI, RBI, RoC, etc.
- **ORGANIZATION**: Non-company orgs
- **COUNTRY/LOCATION**: Geographic entities

### 2. Claims (Edges/Relationships)

Claims are the **relationships** between entities. Each claim has:

| Property | Description | Example |
|----------|-------------|---------|
| `subject_entity_id` | Who/what is doing | Yashish Dahiya (ID: 123) |
| `predicate` | The relationship | CEO_OF |
| `object_entity_id` | To whom/what | PB Fintech (ID: 456) |
| `object_value` | Text backup | "PB Fintech Limited" |

**Common Predicates:**
```
CEO_OF, FOUNDER_OF, OWNS, SUBSIDIARY_OF, WORKS_AT,
SHAREHOLDER_OF, REGULATED_BY, LOCATED_IN, PARTNER_OF
```

### 3. Events (Timeline)

Special facts with dates:

| Property | Example |
|----------|---------|
| `event_type` | INCORPORATION, IPO, ALLOTMENT |
| `description` | "Company was incorporated" |
| `event_date` | 2008-06-04 |

---

## How Our KG is Structured

```
┌─────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────┐    CEO_OF     ┌─────────────┐               │
│   │ Yashish  │──────────────▶│ PB Fintech  │               │
│   │ Dahiya   │               │  Limited    │               │
│   │ (PERSON) │               │ (COMPANY)   │               │
│   └──────────┘               └──────┬──────┘               │
│        │                            │                       │
│        │ FOUNDER_OF                 │ OWNS                  │
│        │                            ▼                       │
│        │                     ┌─────────────┐               │
│        └────────────────────▶│ Policybazaar│               │
│                              │ (COMPANY)   │               │
│                              └──────┬──────┘               │
│                                     │                       │
│                                     │ REGULATED_BY          │
│                                     ▼                       │
│                              ┌─────────────┐               │
│                              │    SEBI     │               │
│                              │ (REGULATOR) │               │
│                              └─────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## The Extraction Pipeline

### Step 1: Document Ingestion
```
PDF → Text Extraction → Chunking (500-1000 chars each)
```
The IPO prospectus is split into 816 chunks.

### Step 2: LLM Extraction
For each batch of 10 chunks, we send a prompt to LLaMA 3:

```python
prompt = """
Extract from this text:
1. ENTITIES: People, companies, regulators
2. CLAIMS: Relationships between entities
3. DEFINITIONS: Legal terms defined
4. EVENTS: Important dates

Return as JSON with format:
{
  "entities": [{"name": "...", "type": "PERSON", "attributes": {}}],
  "claims": [{"subject": "...", "predicate": "CEO_OF", "object": "..."}],
  ...
}
"""
```

### Step 3: Entity Resolution
When saving claims, we:
1. **Lookup** existing entities by normalized key
2. **Create** new entities if not found
3. **Link** subject_entity_id and object_entity_id

```python
# Normalize: "PB Fintech Limited" → "pb_fintech_limited"
normalized = name.lower().replace(" ", "_")

# Lookup or create entity
entity = lookup_or_create(normalized)

# Save claim with entity IDs
INSERT INTO claims (subject_entity_id, predicate, object_entity_id)
VALUES (entity_a_id, 'CEO_OF', entity_b_id)
```

### Step 4: Parallel Processing
We use 3 parallel workers to speed up extraction:
- 82 batches × 10 chunks = 816 chunks
- ~45 minutes instead of 41 hours sequential

---

## Multi-Hop Relationships

**Multi-hop** means following multiple edges to find connected facts.

### Example Query
> "Who is the CEO of the company that owns Policybazaar?"

### Single-Hop (Won't work)
```
Yashish Dahiya → CEO_OF → ??? (not directly connected to Policybazaar)
```

### Multi-Hop (Works!)
```
Hop 1: Policybazaar ← OWNS ← PB Fintech Limited
Hop 2: PB Fintech Limited ← CEO_OF ← Yashish Dahiya

Answer: Yashish Dahiya
```

### SQL Query for Multi-Hop
```sql
-- Find CEO of company that owns Policybazaar
SELECT ceo.canonical_name
FROM kg_entities target
JOIN claims owns ON owns.object_entity_id = target.id AND owns.predicate = 'OWNS'
JOIN kg_entities company ON company.id = owns.subject_entity_id
JOIN claims ceo_claim ON ceo_claim.object_entity_id = company.id AND ceo_claim.predicate = 'CEO_OF'
JOIN kg_entities ceo ON ceo.id = ceo_claim.subject_entity_id
WHERE target.canonical_name = 'Policybazaar';
```

---

## How RAG Uses the KG

### Traditional RAG (Vector Only)
```
Query → Vector Embed → Find Similar Chunks → Send to LLM → Answer
```
**Problem**: May miss facts not in retrieved chunks.

### KG-Enhanced RAG
```
Query → Vector Embed → Find Similar Chunks
                     ↓
              Extract Entity Names
                     ↓
              KG Lookup & Traversal
                     ↓
         Combine Chunks + KG Facts
                     ↓
              Send to LLM → Answer
```

### Example Flow
1. **User asks**: "Who are all the directors at PB Fintech?"
2. **Vector search** finds chunks mentioning directors
3. **KG lookup** finds entity "PB Fintech Limited"
4. **KG traversal** finds all incoming `DIRECTOR_OF` edges
5. **Context for LLM**:
   ```
   From Knowledge Graph:
   - Yashish Dahiya (CEO_OF PB Fintech Limited)
   - Alok Bansal (COO_OF PB Fintech Limited) 
   - Gopalan Srinivasan (INDEPENDENT_DIRECTOR_OF PB Fintech Limited)
   - Lilian Jessie Paul (INDEPENDENT_DIRECTOR_OF PB Fintech Limited)
   
   From document chunks:
   [relevant text excerpts...]
   ```
6. **LLM generates** complete, accurate answer

---

## Database Schema

### kg_entities
```sql
CREATE TABLE kg_entities (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    canonical_name VARCHAR(500),    -- "PB Fintech Limited"
    entity_type VARCHAR(50),        -- "COMPANY"
    normalized_key VARCHAR(500),    -- "pb_fintech_limited"
    attributes JSONB,               -- {"founded": "2008"}
    UNIQUE(document_id, normalized_key)
);
```

### claims
```sql
CREATE TABLE claims (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    subject_entity_id INTEGER REFERENCES kg_entities(id),
    predicate VARCHAR(100),         -- "CEO_OF"
    object_entity_id INTEGER REFERENCES kg_entities(id),
    object_value TEXT               -- Backup text value
);
```

### Relationship Diagram
```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│ kg_entities │◄──────│    claims    │──────►│ kg_entities │
│ (subject)   │  FK   │              │  FK   │  (object)   │
└─────────────┘       └──────────────┘       └─────────────┘
```

---

## Summary

| Concept | What It Does |
|---------|--------------|
| **Entity** | Represents a thing (person, company, regulator) |
| **Claim** | Represents a fact/relationship between entities |
| **Predicate** | The type of relationship (CEO_OF, OWNS, etc.) |
| **Multi-Hop** | Following multiple relationships to find connected facts |
| **Entity Resolution** | Linking text mentions to unique entity IDs |
| **KG-RAG** | Combining vector search with graph traversal |

The Knowledge Graph transforms unstructured IPO documents into a queryable network of facts, enabling:
- **Precise answers** to relationship questions
- **Multi-hop reasoning** across connected entities
- **Structured context** for LLM responses
