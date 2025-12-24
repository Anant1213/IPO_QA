"""
Production KG Extraction Prompt Templates
Specialized prompts for each extraction stage
"""

# ============================================
# STAGE 1: DEFINITIONS EXTRACTION
# ============================================

DEFINITIONS_PROMPT = """You are extracting defined terms from an IPO DRHP document.

TEXT:
{chunk_text}

METADATA:
- Page: {page_number}
- Section: {section_title}
- Chunk ID: {chunk_id}

PATTERNS TO DETECT:
- "X" means/refers to/shall mean...
- "X" = definition...
- X has the meaning assigned...
- As used herein, "X" means...

OUTPUT FORMAT (strict JSON only):
{{
  "defined_terms": [
    {{
      "term": "exact term as written (with quotes if present)",
      "term_normalized": "lowercase_underscored",
      "definition": "the full definition text",
      "aliases": ["other names for same concept"],
      "evidence": {{
        "quote": "exact quote from text (max 25 words)",
        "page": {page_number},
        "section": "{section_title}",
        "chunk_id": "{chunk_id}"
      }}
    }}
  ]
}}

RULES:
1. Extract ONLY explicit definitions - do not infer
2. Quote must be verbatim from the text
3. If no definitions found, return {{"defined_terms": []}}
4. Do not add commentary, only JSON

OUTPUT:"""


# ============================================
# STAGE 2: ENTITY + ATTRIBUTE EXTRACTION
# ============================================

ENTITY_ATTRIBUTE_PROMPT = """You are extracting entities and attributes from an IPO document.

TEXT:
{chunk_text}

METADATA:
- Page: {page_number}
- Section: {section_title}
- Chunk ID: {chunk_id}

ENTITY TYPES (only use these):
- Company: registered companies (inc. subsidiaries, JVs)
- Person: individuals (directors, promoters, shareholders)
- Regulator: regulatory bodies (SEBI, RBI, IRDAI)
- Exchange: stock exchanges (BSE, NSE)
- Auditor: audit firms
- Registrar: registrar and transfer agents
- Security: equity shares, bonds, instruments
- Product: products, platforms, services
- Location: addresses, cities, registered offices

ATTRIBUTES TO EXTRACT:
- Company: CIN, incorporation_date, registered_office
- Person: DIN, designation, address, shares_held, percentage
- Security: face_value, issue_price, lot_size
- Financial: amount, currency, period, scope (consolidated/standalone)

OUTPUT FORMAT (strict JSON only):
{{
  "entities": [
    {{
      "name": "Official Name as stated",
      "normalized_key": "lowercase_underscored",
      "type": "ENTITY_TYPE",
      "attributes": {{
        "cin": "if available",
        "din": "if person",
        "designation": "role/title",
        "face_value": 2,
        "address": "full address"
      }},
      "evidence": {{
        "quote": "exact quote (max 25 words)",
        "page": {page_number},
        "section": "{section_title}",
        "chunk_id": "{chunk_id}"
      }}
    }}
  ]
}}

RULES:
1. Use canonical names (e.g., "PB Fintech Limited" not "the Company")
2. Include units for numeric values
3. Extract ALL entities visible in the text
4. If none found, return {{"entities": []}}

OUTPUT:"""


# ============================================
# STAGE 3: RELATIONSHIP EXTRACTION
# ============================================

RELATIONSHIP_PROMPT = """You are extracting relationships between entities from an IPO document.

TEXT:
{chunk_text}

KNOWN ENTITIES IN THIS DOCUMENT:
{entity_list}

METADATA:
- Page: {page_number}
- Section: {section_title}
- Chunk ID: {chunk_id}

RELATIONSHIP TYPES (only use these):
- subsidiary_of: X is subsidiary of Y
- parent_of: X is parent company of Y
- promoter_of: X is promoter of Y (person → company)
- founder_of: X founded Y
- director_of: X is director of Y
- ceo_of, cfo_of, chairman_of: X holds position at Y
- auditor_of: X audits Y
- registrar_of: X is registrar for Y
- regulated_by: X is regulated by Y
- listed_on: X is listed on Y (exchange)
- shareholder_of: X holds shares in Y (include percentage)
- selling_shareholder_in: X is selling shares in offer

OUTPUT FORMAT (strict JSON only):
{{
  "relationships": [
    {{
      "subject": "Entity Name (must match known entity)",
      "predicate": "relationship_type",
      "object": "Other Entity Name",
      "attributes": {{
        "percentage": 4.27,
        "shares": 17545000,
        "effective_date": "2021-04-01"
      }},
      "evidence": {{
        "quote": "exact quote (max 25 words)",
        "page": {page_number},
        "section": "{section_title}",
        "chunk_id": "{chunk_id}"
      }}
    }}
  ]
}}

RULES:
1. Both subject and object should be entities (or create new if not in list)
2. Include numeric attributes when stated (percentages, share counts)
3. If none found, return {{"relationships": []}}

OUTPUT:"""


# ============================================
# STAGE 4: EVENT EXTRACTION
# ============================================

EVENT_PROMPT = """You are extracting events and timeline facts from an IPO document.

TEXT:
{chunk_text}

METADATA:
- Page: {page_number}
- Section: {section_title}
- Chunk ID: {chunk_id}

EVENT TYPES (only use these):
- Incorporation: company was incorporated/founded
- NameChange: company changed name
- Appointment: person appointed to position
- Resignation: person resigned from position
- Acquisition: company acquired or invested in another
- Litigation: legal proceedings filed/resolved
- IPO_Filing: DRHP/RHP filed with SEBI
- IPO_Approval: SEBI approval received
- IPO_Listing: shares listed on exchange
- Agreement: material agreement signed
- Amendment: articles/MOA amended

OUTPUT FORMAT (strict JSON only):
{{
  "events": [
    {{
      "event_type": "NameChange",
      "date": "YYYY-MM-DD",
      "date_text": "June 4, 2008 (as written)",
      "description": "brief description of event",
      "participants": [
        {{"entity": "Entity Name", "role": "subject"}},
        {{"entity": "Old Name", "role": "previous_name"}}
      ],
      "evidence": {{
        "quote": "exact quote (max 25 words)",
        "page": {page_number},
        "section": "{section_title}",
        "chunk_id": "{chunk_id}"
      }}
    }}
  ]
}}

RULES:
1. Parse dates to YYYY-MM-DD if possible, keep original in date_text
2. If date unclear, set date to null but keep date_text
3. Include all relevant participants with their roles
4. If none found, return {{"events": []}}

OUTPUT:"""


# ============================================
# STAGE 5: ENTITY RESOLUTION
# ============================================

ENTITY_RESOLUTION_PROMPT = """You are identifying duplicate entities that should be merged.

ENTITY LIST:
{entity_batch_json}

Analyze these entities and identify:
1. Entities that are the same (different name variants)
2. Entities that might be aliases of each other

OUTPUT FORMAT (strict JSON only):
{{
  "merge_candidates": [
    {{
      "entity_a_id": "id of first entity",
      "entity_b_id": "id of second entity",
      "confidence": 0.95,
      "reason": "same CIN" | "name variant" | "alias in definition" | "abbreviation match"
    }}
  ],
  "confirmed_aliases": [
    {{
      "canonical_id": "id of main entity",
      "alias": "the alias name",
      "source": "name_variant" | "abbreviation" | "former_name"
    }}
  ]
}}

MATCHING SIGNALS:
- Same CIN or DIN
- One name contains the other (e.g., "PB Fintech" and "PB Fintech Limited")
- Abbreviation match (e.g., "SEBI" and "Securities and Exchange Board of India")
- Former/new name relationship
- "also known as" / "formerly known as" patterns

RULES:
1. Only flag high-confidence matches (>0.8)
2. Do not merge different legal entities
3. If no candidates, return empty arrays

OUTPUT:"""


# ============================================
# VALIDATION PROMPT (for extracted facts)
# ============================================

VALIDATION_PROMPT = """Review these extracted facts for accuracy and completeness.

EXTRACTED DATA:
{extracted_json}

SOURCE TEXT:
{chunk_text}

Validate each fact against the source text and report issues.

OUTPUT FORMAT (strict JSON only):
{{
  "validation_results": [
    {{
      "fact_id": "reference to fact",
      "is_valid": true,
      "issues": [],
      "suggested_fix": null
    }},
    {{
      "fact_id": "another fact reference",
      "is_valid": false,
      "issues": ["value not found in text", "incorrect percentage"],
      "suggested_fix": "correct value from text"
    }}
  ],
  "summary": {{
    "total_checked": 10,
    "valid": 8,
    "invalid": 2,
    "accuracy": 0.8
  }}
}}

VALIDATION CHECKS:
1. Quote exists verbatim in source text
2. Numeric values match source
3. Entity names are correctly transcribed
4. Dates are correctly parsed
5. Relationships are correctly identified

OUTPUT:"""
