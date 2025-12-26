# IPO Intelligence Platform 🚀

A robust **Hybrid RAG (Retrieval-Augmented Generation)** system for analyzing IPO prospectus documents using both **Knowledge Graphs** and **Vector Embeddings**.

Built with Flask, PostgreSQL + pgvector, SentenceTransformers, and Ollama (LLaMA 3).

## 🌟 Key Features

- **Hybrid RAG Architecture**: Combines Knowledge Graph + Vector search for optimal answers
- **Database-Backed KG**: PostgreSQL stores entities and relationships for multi-hop queries
- **Multi-Hop Reasoning**: Traverse relationships like "Who is CEO of the company that owns X?"
- **Parallel KG Extraction**: Fast extraction using 3 parallel workers
- **Interactive Visualization**: PyVis-based KG visualization with hover details
- **Local LLM Support**: Fully private execution using Ollama (LLaMA 3)
- **Streaming Responses**: Real-time token streaming UI

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IPO INTELLIGENCE PLATFORM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐                                                           │
│  │ User Query   │                                                           │
│  │ "Who is CEO  │                                                           │
│  │ of PB Fintech│                                                           │
│  └──────┬───────┘                                                           │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FLASK API (/api/ask)                          │   │
│  └──────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                        │
│         ┌───────────────────────────┼───────────────────────────┐           │
│         │                           │                           │           │
│         ▼                           ▼                           ▼           │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐      │
│  │ VECTOR RAG  │            │   KG RAG    │            │ HYBRID RAG  │      │
│  │             │            │             │            │             │      │
│  │ pgvector    │            │ PostgreSQL  │            │ Both paths  │      │
│  │ similarity  │            │ traversal   │            │ combined    │      │
│  └──────┬──────┘            └──────┬──────┘            └──────┬──────┘      │
│         │                          │                          │             │
│         ▼                          ▼                          ▼             │
│  ┌─────────────┐            ┌─────────────┐                                 │
│  │ embeddings  │            │ kg_entities │                                 │
│  │   table     │            │   claims    │                                 │
│  │ VECTOR(384) │            │   tables    │                                 │
│  └─────────────┘            └─────────────┘                                 │
│                                                                              │
│         └───────────────────────┬───────────────────────┘                   │
│                                 │                                            │
│                                 ▼                                            │
│                       ┌─────────────────┐                                   │
│                       │ COMBINED CONTEXT│                                   │
│                       │ Text + KG Facts │                                   │
│                       └────────┬────────┘                                   │
│                                │                                            │
│                                ▼                                            │
│                       ┌─────────────────┐                                   │
│                       │  LLaMA 3 (LLM)  │                                   │
│                       │  via Ollama     │                                   │
│                       └────────┬────────┘                                   │
│                                │                                            │
│                                ▼                                            │
│                       ┌─────────────────┐                                   │
│                       │     ANSWER      │                                   │
│                       └─────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Knowledge Graph Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH EXTRACTION                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   PDF Document                                                        │
│        │                                                              │
│        ▼                                                              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│   │ Text Extract│────▶│  Chunking   │────▶│  Batching   │            │
│   │   PyMuPDF   │     │ 500-1000chr │     │ 10 chunks   │            │
│   └─────────────┘     └─────────────┘     └──────┬──────┘            │
│                                                  │                    │
│                                    ┌─────────────┼─────────────┐     │
│                                    │             │             │     │
│                                    ▼             ▼             ▼     │
│                              ┌─────────┐   ┌─────────┐   ┌─────────┐ │
│                              │ Worker 1│   │ Worker 2│   │ Worker 3│ │
│                              │ LLaMA 3 │   │ LLaMA 3 │   │ LLaMA 3 │ │
│                              └────┬────┘   └────┬────┘   └────┬────┘ │
│                                   │             │             │      │
│                                   └─────────────┼─────────────┘      │
│                                                 │                    │
│                                                 ▼                    │
│                                      ┌───────────────────┐           │
│                                      │  Entity Linking   │           │
│                                      │  Normalize names  │           │
│                                      │  Create/lookup IDs│           │
│                                      └─────────┬─────────┘           │
│                                                │                     │
│                              ┌─────────────────┼─────────────────┐   │
│                              ▼                 ▼                 ▼   │
│                       ┌───────────┐     ┌───────────┐     ┌──────────┐
│                       │kg_entities│     │  claims   │     │  events  │
│                       │   table   │     │   table   │     │  table   │
│                       └───────────┘     └───────────┘     └──────────┘
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Multi-Hop Query Example

```
Question: "Who is the CEO of the company that owns Policybazaar?"

┌─────────────────────────────────────────────────────────────────┐
│                     MULTI-HOP TRAVERSAL                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Hop 1: Find owner of Policybazaar                             │
│   ┌─────────────┐    OWNS    ┌─────────────┐                    │
│   │ PB Fintech  │───────────▶│ Policybazaar│                    │
│   │  Limited    │            │             │                    │
│   └──────┬──────┘            └─────────────┘                    │
│          │                                                       │
│   Hop 2: Find CEO of PB Fintech                                 │
│   ┌─────────────┐   CEO_OF   ┌─────────────┐                    │
│   │   Yashish   │───────────▶│ PB Fintech  │                    │
│   │   Dahiya    │            │  Limited    │                    │
│   └─────────────┘            └─────────────┘                    │
│                                                                  │
│   Answer: Yashish Dahiya                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Schema

```sql
-- Entities (Nodes)
CREATE TABLE kg_entities (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    canonical_name VARCHAR(500),
    entity_type VARCHAR(50),        -- PERSON, COMPANY, REGULATOR
    normalized_key VARCHAR(500),
    attributes JSONB
);

-- Relationships (Edges)
CREATE TABLE claims (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    subject_entity_id INTEGER REFERENCES kg_entities(id),
    predicate VARCHAR(100),         -- CEO_OF, OWNS, SUBSIDIARY_OF
    object_entity_id INTEGER REFERENCES kg_entities(id),
    object_value TEXT
);

-- Vector Embeddings
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES chunks(id),
    embedding VECTOR(384)           -- pgvector type
);
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ with pgvector extension
- [Ollama](https://ollama.ai) installed and running
- `llama3` model pulled (`ollama pull llama3`)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/ipo-qa.git
cd ipo-qa

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup database
psql -c "CREATE DATABASE ipo_intelligence;"
psql ipo_intelligence -f database/schema.sql
psql ipo_intelligence -f database/kg_schema.sql
```

### Running the Application

```bash
# Start Ollama (in separate terminal)
ollama serve

# Start Flask server
python src/app.py
```

Application runs at `http://localhost:5000`

---

## 📂 Project Structure

```
ipo_qa/
├── src/
│   ├── app.py                    # Flask API + RAG classes
│   ├── database/
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── connection.py         # DB connection
│   │   └── repositories/
│   │       ├── kg_repo.py        # KG queries (NEW)
│   │       ├── embedding_repo.py # Vector search
│   │       └── document_repo.py  # Document CRUD
│   └── utils/
│       ├── embedding_utils.py    # SentenceTransformer
│       ├── deepseek_client.py    # LLM client
│       └── graph_store.py        # Legacy JSON KG
├── scripts/
│   ├── build_kg_parallel.py      # KG extraction (3 workers)
│   └── visualize_kg_db.py        # PyVis visualization
├── database/
│   ├── schema.sql                # Core tables
│   └── kg_schema.sql             # KG tables
├── docs/
│   ├── KG_TECHNICAL_GUIDE.md     # KG documentation
│   └── KG_TECHNICAL_GUIDE.pdf    # PDF version
└── requirements.txt
```

---

## 🔧 Key Scripts

### Extract Knowledge Graph
```bash
python scripts/build_kg_parallel.py -d your_document_id
```
Extracts entities, claims, and events using parallel LLM calls.

### Visualize Knowledge Graph
```bash
python scripts/visualize_kg_db.py -d your_document_id --open
```
Creates interactive HTML visualization.

---

## 📝 License

MIT License. See [LICENSE](LICENSE) for details.
