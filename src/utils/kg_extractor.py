"""
Knowledge Graph Extractor - Extracts entities and relationships from IPO document chunks
Uses DeepSeek R1 with schema-guided prompting
"""

import json
import os
from typing import List, Dict, Tuple
from utils.deepseek_client import DeepSeekClient


class KnowledgeGraphExtractor:
    """Extract structured entities and relationships from text chunks"""
    
    def __init__(self, schema_path: str = "schema.json"):
        self.client = DeepSeekClient(use_local_fallback=True)
        self.schema = self._load_schema(schema_path)
        self.system_prompt = self._build_system_prompt()
        
    def _load_schema(self, schema_path: str) -> Dict:
        """Load knowledge graph schema"""
        with open(schema_path, 'r') as f:
            return json.load(f)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with schema definition"""
        entities = list(self.schema['entities'].keys())
        relationships = list(self.schema['relationships'].keys())
        
        prompt = f"""You are an expert IPO document analyst specializing in structured information extraction.

Your task is to extract entities and relationships from IPO prospectus text and output them as JSON.

ALLOWED ENTITY TYPES:
{json.dumps(entities, indent=2)}

ALLOWED RELATIONSHIP TYPES:
{json.dumps(relationships, indent=2)}

RULES:
1. Extract ALL entities you can identify from the text
2. Only use entity and relationship types from the allowed lists
3. For entities: identify the type and key attributes
4. For relationships: identify source entity, target entity, relationship type, and attributes
5. Use canonical names (e.g., "PB Fintech Limited" not "the Company")
6. Include numeric values with units (e.g., "₹37,500 million")
7. Extract temporal information (years, quarters, dates)

OUTPUT FORMAT:
{{
  "entities": [
    {{
      "id": "unique_identifier",
      "name": "entity_name",
      "type": "ENTITY_TYPE",
      "attributes": {{"key": "value"}}
    }}
  ],
  "relationships": [
    {{
      "source_id": "entity_id_1",
      "target_id": "entity_id_2",
      "type": "RELATIONSHIP_TYPE",
      "attributes": {{"key": "value"}}
    }}
  ]
}}

Be comprehensive but precise. If unsure about an entity type or relationship, skip it."""
        
        return prompt
    
    def _build_extraction_prompt(self, chunk_text: str, examples: bool = True) -> str:
        """Build extraction prompt for a specific chunk"""
        
        prompt = f"""Extract all entities and relationships from the following IPO document text:

TEXT:
{chunk_text}

"""
        
        if examples:
            prompt += self._get_few_shot_examples()
        
        prompt += "\nNow extract from the above TEXT and output JSON:"
        
        return prompt
    
    def _get_few_shot_examples(self) -> str:
        """Provide few-shot examples for better extraction"""
        return """
EXAMPLE 1:
TEXT: "Mr. Yashish Dahiya, the Chairman, Executive Director and Chief Executive Officer of our Company, holds 17,545,000 equity shares representing 4.27% stake."

OUTPUT:
{
  "entities": [
    {
      "id": "Yashish_Dahiya",
      "name": "Yashish Dahiya",
      "type": "PERSON",
      "attributes": {"role": "Chairman, Executive Director and CEO"}
    },
    {
      "id": "shareholding_yashish",
      "name": "17,545,000 equity shares (4.27%)",
      "type": "SHAREHOLDER",
      "attributes": {"shares": 17545000, "percentage": 4.27}
    }
  ],
  "relationships": [
    {
      "source_id": "Yashish_Dahiya",
      "target_id": "PB_Fintech_Limited",
      "type": "IS_CEO_OF",
      "attributes": {}
    },
    {
      "source_id": "Yashish_Dahiya",
      "target_id": "shareholding_yashish",
      "type": "OWNS_STAKE",
      "attributes": {"percentage": 4.27}
    }
  ]
}

EXAMPLE 2:
TEXT: "For the fiscal year ended March 31, 2021, the Company reported a loss after tax of ₹1,502.42 million compared to a loss of ₹3,040.29 million in fiscal 2020."

OUTPUT:
{
  "entities": [
    {
      "id": "loss_fy2021",
      "name": "Loss FY2021",
      "type": "FINANCIAL_METRIC",
      "attributes": {"metric_name": "Loss After Tax", "value": -1502.42, "currency": "INR", "unit": "million", "year": "2021"}
    },
    {
      "id": "loss_fy2020",
      "name": "Loss FY2020",
      "type": "FINANCIAL_METRIC",
      "attributes": {"metric_name": "Loss After Tax", "value": -3040.29, "currency": "INR", "unit": "million", "year": "2020"}
    }
  ],
  "relationships": [
    {
      "source_id": "PB_Fintech_Limited",
      "target_id": "loss_fy2021",
      "type": "HAS_LOSS",
      "attributes": {"fiscal_year": "2021"}
    },
    {
      "source_id": "PB_Fintech_Limited",
      "target_id": "loss_fy2020",
      "type": "HAS_LOSS",
      "attributes": {"fiscal_year": "2020"}
    }
  ]
}

"""
    
    def extract_from_chunk(self, chunk_text: str) -> Dict:
        """
        Extract entities and relationships from a single chunk
        
        Args:
            chunk_text: Text chunk from IPO document
            
        Returns:
            Dict with 'entities' and 'relationships' lists
        """
        extraction_prompt = self._build_extraction_prompt(chunk_text)
        
        result = self.client.extract_with_reasoning(
            prompt=extraction_prompt,
            system_prompt=self.system_prompt,
            max_tokens=4096
        )
        
        # Parse output
        try:
            if isinstance(result['output'], str):
                extracted = json.loads(result['output'])
            else:
                extracted = result['output']
            
            # Validate structure
            if 'entities' not in extracted:
                extracted['entities'] = []
            if 'relationships' not in extracted:
                extracted['relationships'] = []
            
            # Add metadata
            extracted['reasoning'] = result.get('reasoning', '')
            
            return extracted
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse extraction output: {e}")
            print(f"Raw output: {result['output']}")
            return {'entities': [], 'relationships': [], 'error': str(e)}
    
    def extract_from_chunks(
        self, 
        chunks: List[Dict],
        max_chunks: int = None,
        show_progress: bool = True
    ) -> List[Dict]:
        """
        Extract from multiple chunks with progress tracking
        
        Args:
            chunks: List of chunk dicts with 'text' field
            max_chunks: Limit number of chunks to process (for testing)
            show_progress: Print progress updates
            
        Returns:
            List of extraction results
        """
        if max_chunks:
            chunks = chunks[:max_chunks]
        
        results = []
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            if show_progress:
                print(f"\rExtracting from chunk {i+1}/{total}...", end='', flush=True)
            
            try:
                chunk_text = chunk.get('text', '')
                if not chunk_text.strip():
                    continue
                
                extracted = self.extract_from_chunk(chunk_text)
                extracted['chunk_id'] = chunk.get('chunk_id', i)
                extracted['chapter_name'] = chunk.get('chapter_name', '')
                results.append(extracted)
                
            except Exception as e:
                print(f"\nError processing chunk {i}: {e}")
                continue
        
        if show_progress:
            print(f"\nCompleted extraction from {len(results)} chunks")
        
        return results
    
    def save_extractions(self, extractions: List[Dict], output_path: str):
        """Save extraction results to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(extractions, f, indent=2)
        print(f"Saved extractions to {output_path}")


if __name__ == "__main__":
    # Test extraction on a sample
    extractor = KnowledgeGraphExtractor()
    
    test_text = """
    PB Fintech Limited was incorporated as 'ETECHACES Marketing and Consulting Private Limited' 
    on June 4, 2008. Mr. Yashish Dahiya and Mr. Alok Bansal are the promoters. The company reported 
    a total income of ₹9,574.13 million for fiscal year 2021. The fresh issue size is up to 
    ₹37,500 million.
    """
    
    result = extractor.extract_from_chunk(test_text)
    print(json.dumps(result, indent=2))
