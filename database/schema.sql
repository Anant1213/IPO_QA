-- ============================================
-- POSTGRESQL SCHEMA FOR IPO INTELLIGENCE
-- ============================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- DOCUMENTS TABLE
-- ============================================

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    filename VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Document stats
    total_pages INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    
    -- Processing status
    upload_date TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    
    -- Metadata (flexible JSON)
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX idx_documents_document_id ON documents(document_id);
CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_created ON documents(created_at DESC);

-- ============================================
-- CHAPTERS TABLE
-- ============================================

CREATE TABLE chapters (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    chapter_number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (document_id, chapter_number)
);

CREATE INDEX idx_chapters_document ON chapters(document_id);

-- ============================================
-- CHUNKS TABLE
-- ============================================

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    
    -- Position metadata
    page_number INTEGER,
    
    -- Stats
    word_count INTEGER,
    
    -- Metadata (flexible JSON)
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_document_index ON chunks(document_id, chunk_index);

-- ============================================
-- EMBEDDINGS TABLE (with pgvector)
-- ============================================

CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    
    -- Vector column (384 dimensions for all-MiniLM-L6-v2)
    embedding vector(384) NOT NULL,
    
    model_name VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_embeddings_chunk ON embeddings(chunk_id);

-- CRITICAL: Create HNSW index for fast similarity search
CREATE INDEX idx_embeddings_vector ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================
-- Helper Functions
-- ============================================

CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_emb vector(384),
    doc_id VARCHAR(255),
    top_k INTEGER DEFAULT 5
)
RETURNS TABLE (
    chunk_id INTEGER,
    chunk_text TEXT,
    page_number INTEGER,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.text,
        c.page_number,
        1 - (e.embedding <=> query_emb) as sim
    FROM embeddings e
    JOIN chunks c ON c.id = e.chunk_id
    JOIN documents d ON d.id = c.document_id
    WHERE d.document_id = doc_id
    ORDER BY e.embedding <=> query_emb
    LIMIT top_k;
END;
$$ LANGUAGE plpgsql;
