-- ============================================
-- KG SCHEMA EXTENSION FOR IPO INTELLIGENCE
-- Production-grade Knowledge Graph storage
-- ============================================

-- ============================================
-- EVIDENCE TABLE (Provenance tracking)
-- ============================================

CREATE TABLE evidence (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
    
    -- Quote from source (≤25 words)
    quote TEXT NOT NULL,
    
    -- Location info
    page_number INTEGER,
    section_title VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_evidence_document ON evidence(document_id);
CREATE INDEX idx_evidence_chunk ON evidence(chunk_id);

-- ============================================
-- KG ENTITIES TABLE (Canonical entities)
-- ============================================

CREATE TABLE kg_entities (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Entity identification
    entity_type VARCHAR(50) NOT NULL,
    canonical_name VARCHAR(500) NOT NULL,
    normalized_key VARCHAR(500) NOT NULL,  -- lowercase, trimmed, underscored
    
    -- Flexible attributes
    attributes JSONB DEFAULT '{}',
    
    -- Confidence and source
    confidence FLOAT DEFAULT 1.0,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(document_id, normalized_key)
);

CREATE INDEX idx_kg_entities_document ON kg_entities(document_id);
CREATE INDEX idx_kg_entities_type ON kg_entities(entity_type);
CREATE INDEX idx_kg_entities_normalized ON kg_entities(normalized_key);
CREATE INDEX idx_kg_entities_name_gin ON kg_entities USING gin(canonical_name gin_trgm_ops);

-- ============================================
-- ENTITY ALIASES TABLE (Name variants)
-- ============================================

CREATE TABLE entity_aliases (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    
    alias VARCHAR(500) NOT NULL,
    alias_normalized VARCHAR(500) NOT NULL,
    
    -- How was this alias discovered
    source VARCHAR(50) DEFAULT 'extraction',  -- extraction, resolution, manual
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_entity_aliases_entity ON entity_aliases(entity_id);
CREATE INDEX idx_entity_aliases_normalized ON entity_aliases(alias_normalized);

-- ============================================
-- DEFINED TERMS TABLE (Glossary/Definitions)
-- ============================================

CREATE TABLE defined_terms (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Term and definition
    term VARCHAR(500) NOT NULL,
    term_normalized VARCHAR(500) NOT NULL,
    definition TEXT NOT NULL,
    
    -- Provenance
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(document_id, term_normalized)
);

CREATE INDEX idx_defined_terms_document ON defined_terms(document_id);
CREATE INDEX idx_defined_terms_normalized ON defined_terms(term_normalized);

-- ============================================
-- CLAIMS TABLE (Facts with provenance)
-- ============================================

CREATE TABLE claims (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Subject (always an entity)
    subject_entity_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    
    -- Predicate (relationship/property name)
    predicate VARCHAR(100) NOT NULL,
    
    -- Object (value OR entity reference)
    object_value TEXT,                    -- For literal values
    object_entity_id INTEGER REFERENCES kg_entities(id) ON DELETE SET NULL,  -- For entity refs
    
    -- Typing
    datatype VARCHAR(50) NOT NULL,        -- string, number, date, entity, percentage
    
    -- Temporal scope (for financial metrics)
    period_label VARCHAR(50),             -- FY2021, Q1FY22, etc.
    period_scope VARCHAR(50),             -- consolidated, standalone
    
    -- Quality
    confidence FLOAT DEFAULT 1.0,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_claims_document ON claims(document_id);
CREATE INDEX idx_claims_subject ON claims(subject_entity_id);
CREATE INDEX idx_claims_predicate ON claims(predicate);
CREATE INDEX idx_claims_object_entity ON claims(object_entity_id);

-- ============================================
-- EVENTS TABLE (Timeline tracking)
-- ============================================

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Event classification
    event_type VARCHAR(100) NOT NULL,
    
    -- Temporal info
    event_date DATE,
    event_date_text VARCHAR(100),  -- Original text if parsing uncertain
    
    -- Description
    description TEXT,
    
    -- Provenance
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_document ON events(document_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_date ON events(event_date);

-- ============================================
-- EVENT PARTICIPANTS TABLE
-- ============================================

CREATE TABLE event_participants (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    
    -- Role in event
    role VARCHAR(100) NOT NULL,  -- subject, target, acquirer, appointee, etc.
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_event_participants_event ON event_participants(event_id);
CREATE INDEX idx_event_participants_entity ON event_participants(entity_id);

-- ============================================
-- VALIDATION REPORTS TABLE
-- ============================================

CREATE TABLE validation_reports (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Run metadata
    run_at TIMESTAMP DEFAULT NOW(),
    pipeline_version VARCHAR(50),
    
    -- Counts
    total_entities INTEGER DEFAULT 0,
    total_claims INTEGER DEFAULT 0,
    total_events INTEGER DEFAULT 0,
    total_definitions INTEGER DEFAULT 0,
    
    -- Issues
    violations JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    
    -- Summary
    is_valid BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_validation_reports_document ON validation_reports(document_id);

-- ============================================
-- MERGE CANDIDATES TABLE (Entity resolution)
-- ============================================

CREATE TABLE merge_candidates (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    
    entity_a_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    entity_b_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    
    confidence FLOAT NOT NULL,
    reason VARCHAR(255),
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, merged, rejected
    reviewed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_merge_candidates_document ON merge_candidates(document_id);
CREATE INDEX idx_merge_candidates_status ON merge_candidates(status);

-- ============================================
-- Enable pg_trgm for fuzzy matching
-- ============================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- Helper Functions
-- ============================================

-- Normalize text for matching
CREATE OR REPLACE FUNCTION normalize_key(text_input TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                TRIM(text_input),
                '[–—]', '-', 'g'  -- Unify dashes
            ),
            '\s+', '_', 'g'  -- Spaces to underscores
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Get entity with all aliases
CREATE OR REPLACE FUNCTION get_entity_with_aliases(ent_id INTEGER)
RETURNS TABLE (
    entity_id INTEGER,
    canonical_name VARCHAR,
    entity_type VARCHAR,
    aliases TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.canonical_name,
        e.entity_type,
        ARRAY_AGG(DISTINCT a.alias) FILTER (WHERE a.alias IS NOT NULL)
    FROM kg_entities e
    LEFT JOIN entity_aliases a ON a.entity_id = e.id
    WHERE e.id = ent_id
    GROUP BY e.id, e.canonical_name, e.entity_type;
END;
$$ LANGUAGE plpgsql;

-- Search entities by name (fuzzy)
CREATE OR REPLACE FUNCTION search_entities(
    doc_id INTEGER,
    search_term VARCHAR,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    entity_id INTEGER,
    canonical_name VARCHAR,
    entity_type VARCHAR,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.canonical_name,
        e.entity_type,
        similarity(e.canonical_name, search_term) as sim
    FROM kg_entities e
    WHERE e.document_id = doc_id
      AND (
          e.canonical_name ILIKE '%' || search_term || '%'
          OR e.normalized_key ILIKE '%' || normalize_key(search_term) || '%'
          OR EXISTS (
              SELECT 1 FROM entity_aliases a 
              WHERE a.entity_id = e.id 
              AND a.alias ILIKE '%' || search_term || '%'
          )
      )
    ORDER BY similarity(e.canonical_name, search_term) DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;
