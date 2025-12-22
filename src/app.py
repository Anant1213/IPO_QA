"""
Flask backend for multi-document IPO Q&A system.
"""

# IMPORTANT: Set threading limits BEFORE importing torch-dependent libraries
# This prevents mutex lock issues on Apple Silicon (M1/M2/M3)
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'

import torch
torch.set_num_threads(1)
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, stream_with_context
from werkzeug.utils import secure_filename
import os
import json
import hashlib
import numpy as np
import requests
from datetime import datetime

# Import configuration
from utils.config import (
    UPLOAD_FOLDER,
    DATA_DIR,
    DOCUMENTS_FOLDER,
    MAX_CONTENT_LENGTH,
    ALLOWED_EXTENSIONS,
    DOCUMENTS_INDEX,
    EMBEDDING_MODEL_NAME,
    OLLAMA_BASE_URL,
    DEFAULT_TOP_K,
    LLM_TEMPERATURE,
    LLM_NUM_PREDICT,
    LLM_TOP_P
)

# Constants for KG Retrieval
PRIORITY_RELATIONS = {
    'IS_CEO_OF', 'HAS_CEO', 'IS_PROMOTER_OF', 'HAS_PROMOTER',
    'IS_CHAIRMAN_OF', 'IS_DIRECTOR_OF', 'IS_FOUNDER_OF',
    'OWNS_STAKE', 'HAS_SHAREHOLDER', 'HAS_MAJOR_SHAREHOLDER',
    'IS_PARENT_OF', 'IS_SUBSIDIARY_OF', 'IS_MD_OF', 'HAS_MD',
    # NEW: Extended relationships for better coverage
    'IS_SELLING_SHAREHOLDER_OF', 'HAS_SELLING_SHAREHOLDER', 'OFFERS_FOR_SALE',
    'HAS_REGISTERED_OFFICE', 'LOCATED_AT', 'HAS_ADDRESS',
    'IS_SUBSIDIARY_OF', 'HAS_SUBSIDIARY', 'OWNS'
}

# Synonym/Alias Mapping for Entity Name Variations
ENTITY_SYNONYMS = {
    'pb fintech': ['policybazaar fintech', 'pb fintech limited', 'policybazaar fintech limited', 'etechaces'],
    'policybazaar': ['policy bazaar', 'pb', 'policybazaar insurance'],
    'paisabazaar': ['paisa bazaar', 'paisabazaar marketing'],
    'yashish dahiya': ['yashish', 'dahiya', 'mr. yashish dahiya', 'mr yashish dahiya'],
    'alok bansal': ['alok', 'bansal', 'mr. alok bansal', 'mr alok bansal'],
    'svf python': ['svf python ii', 'svf python ii (cayman)', 'softbank', 'svf'],
}

# Query Keyword Expansion for Better Retrieval
QUERY_EXPANSION = {
    'owner': ['promoter', 'founder', 'shareholder', 'stakeholder'],
    'selling': ['offer for sale', 'ofs', 'selling shareholder'],
    'office': ['registered office', 'corporate office', 'address', 'location', 'headquarters'],
    'subsidiary': ['subsidiaries', 'group company', 'owned company', 'child company'],
    'revenue': ['total revenue', 'income', 'sales', 'turnover'],
    'loss': ['restated loss', 'net loss', 'loss for the year', 'deficit'],
    'profit': ['net profit', 'earnings', 'income'],
}

from utils.pdf_utils import extract_pages
# from utils.embedding_utils import search_similar_chunks, get_embedding_model, cosine_similarity  # Lazy loaded
from utils.graph_store import GraphStore
from utils.answer_formatter import AnswerFormatter
from utils.deepseek_client import DeepSeekClient

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATA_FOLDER'] = DATA_DIR
app.config['DOCUMENTS_FOLDER'] = DOCUMENTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOCUMENTS_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def find_entities_by_relationship(graph_store, rel_type, direction='outgoing'):
    """Find all entities with a specific relationship type"""
    matching_entities = []
    seen_ids = set()
    
    for entity_id, entity_data in graph_store.graph.nodes(data=True):
        if entity_id in seen_ids:
            continue
            
        rels = graph_store.query_relationships(entity_id, rel_type, direction)
        if rels:
            matching_entities.append({
                'id': entity_id,
                'name': entity_data.get('name', entity_id),
                'type': entity_data.get('type'),
                'attributes': entity_data.get('attributes', {})
            })
            seen_ids.add(entity_id)
    
    return matching_entities

def find_entities_by_attribute(entity_map, attr_key, attr_value_substring):
    """Find entities by searching their attributes"""
    matching_entities = []
    attr_value_lower = attr_value_substring.lower()
    
    for name, entity in entity_map.items():
        if attr_key in entity.get('attributes', {}):
            attr_val = str(entity['attributes'][attr_key]).lower()
            if attr_value_lower in attr_val:
                matching_entities.append(entity)
    
    return matching_entities

def expand_query_terms(query_words, query_lower):
    """Expand query terms using QUERY_EXPANSION mapping"""
    expanded_terms = set(query_words)
    
    for word in query_words:
        if word in QUERY_EXPANSION:
            expanded_terms.update(QUERY_EXPANSION[word])
    
    # Check for multi-word patterns
    for key, expansions in QUERY_EXPANSION.items():
        if key in query_lower:
            expanded_terms.update(expansions)
    
    return list(expanded_terms)

def find_entities_by_any_attribute(entity_list, search_terms):
    """Search ALL attributes of entities for matching terms"""
    matching_entities = []
    
    for entity in entity_list:
        attrs = entity.get('attributes', {})
        entity_name = entity.get('name', '').lower()
        
        # Check entity name first
        for term in search_terms:
            if term.lower() in entity_name:
                if entity not in matching_entities:
                    matching_entities.append(entity)
                break
        
        # Check all attribute values
        for attr_key, attr_val in attrs.items():
            attr_str = str(attr_val).lower()
            for term in search_terms:
                if term.lower() in attr_str or term.lower() in attr_key.lower():
                    if entity not in matching_entities:
                        matching_entities.append(entity)
                    break
    
    return matching_entities

def match_entity_by_synonym(entity_name_lower, query_terms):
    """Check if entity name matches any query term via synonyms"""
    for canonical, synonyms in ENTITY_SYNONYMS.items():
        if canonical in entity_name_lower or any(syn in entity_name_lower for syn in synonyms):
            # Check if any query term matches canonical or synonyms
            for term in query_terms:
                term_lower = term.lower()
                if term_lower in canonical or any(term_lower in syn for syn in synonyms):
                    return True
                if canonical in term_lower or any(syn in term_lower for syn in synonyms):
                    return True
    return False

def get_file_hash(filepath):
    """Calculate MD5 hash of file."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def load_documents_index():
    """Load the master documents index."""
    if os.path.exists(DOCUMENTS_INDEX):
        try:
            with open(DOCUMENTS_INDEX, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_documents_index(documents):
    """Save the master documents index."""
    with open(DOCUMENTS_INDEX, 'w') as f:
        json.dump(documents, f, indent=2)

def check_duplicate(file_hash):
    """Check if a file with this hash already exists."""
    documents = load_documents_index()
    for doc in documents:
        if doc.get('file_hash') == file_hash:
            return doc
    return None

def generate_document_id(filename):
    """Generate a unique document ID from filename."""
    base_name = os.path.splitext(filename)[0]
    doc_id = ''.join(c if c.isalnum() or c == '_' else '_' for c in base_name).lower()
    documents = load_documents_index()
    existing_ids = {doc['document_id'] for doc in documents}
    
    if doc_id not in existing_ids:
        return doc_id
    
    counter = 1
    while f"{doc_id}_{counter}" in existing_ids:
        counter += 1
    return f"{doc_id}_{counter}"

class QueryRouter:
    """Routes queries to appropriate RAG system based on intent"""
    def __init__(self):
        pass

    def route(self, question):
        q_lower = question.lower()
        
        # 1. Structural/Graph indicators (High Confidence)
        structural_keywords = [
            'who owns', 'subsidiary', 'subsidiaries', 'promoter', 'shareholder', 
            'relationship', 'connect', 'path', 'hierarchy', 'structure', 
            'hold', 'ownership', 'founder', 'director', 'board', 'management',
            'role', 'auditor', 'registrar'
        ]
        if any(x in q_lower for x in structural_keywords):
            return 'kg'
            
        # 2. Aggregation/Financial indicators (Medium Confidence for KG)
        financial_keywords = ['total', 'sum', 'count', 'list all', 'how many']
        metric_keywords = ['share', 'revenue', 'profit', 'employee', 'amount', 'value']
        if any(x in q_lower for x in financial_keywords) and any(x in q_lower for x in metric_keywords):
            return 'kg'

        # 3. Definition/Textual indicators (High Confidence for Vector)
        textual_keywords = [
            'define', 'what is', 'meaning', 'explain', 'summary', 'policy', 
            'clause', 'section', 'refer', 'mentioned', 'formerly known as',
            'stand for', 'abbreviation'
        ]
        if any(x in q_lower for x in textual_keywords):
            return 'vector'

        # 4. Fallback to Hybrid
        return 'hybrid'

class KnowledgeGraphRAG:
    """KG-based RAG using structural retrieval"""
    def __init__(self, graph_store, entity_map):
        self.graph_store = graph_store
        self.entity_map = entity_map
        self.entity_list = list(entity_map.values())
        self.client = DeepSeekClient()
        self.formatter = AnswerFormatter()

    def retrieve_context(self, question):
        query_clean = ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in question)
        query_words = query_clean.split()
        query_lower = question.lower()
        
        # Expand terms
        search_terms = expand_query_terms(query_words, query_lower)
        
        # 1. Broad entity search
        found_entities = find_entities_by_any_attribute(self.entity_list, search_terms)
        
        # 2. Synonym matching
        for name, entity in self.entity_map.items():
            if match_entity_by_synonym(name.lower(), search_terms):
                if entity not in found_entities:
                    found_entities.append(entity)
        
        # 3. Relationship-based search (simplified for class)
        if 'subsidiary' in query_lower:
            found_entities.extend(find_entities_by_relationship(self.graph_store, 'IS_SUBSIDIARY_OF', 'both'))
            found_entities.extend(find_entities_by_relationship(self.graph_store, 'HAS_SUBSIDIARY', 'both'))
        
        if 'owner' in query_lower or 'promoter' in query_lower or 'founder' in query_lower:
            found_entities.extend(find_entities_by_relationship(self.graph_store, 'IS_PROMOTER_OF', 'outgoing'))
            found_entities.extend(find_entities_by_relationship(self.graph_store, 'IS_FOUNDER_OF', 'outgoing'))
            
        # 4. Deduplicate and prioritize limit
        seen_ids = set()
        final_entities = []
        for e in found_entities:
            if e['id'] not in seen_ids:
                final_entities.append(e)
                seen_ids.add(e['id'])
        
        # Hard limit to prevent context overflow
        final_entities = final_entities[:15]
        
        # Build context string
        context_parts = []
        for entity in final_entities:
            eid = entity['id']
            entity_info = f"**{entity['name']}** ({entity['type']})"
            if entity.get('attributes'):
                attrs_str = json.dumps(entity['attributes'], indent=2)
                entity_info += f"\nAttributes: {attrs_str}"
            context_parts.append(entity_info)
            
            # Fetch relationships
            rels = self.graph_store.query_relationships(eid, direction='both')
            priority_rels = [r for r in rels if r[2] in PRIORITY_RELATIONS]
            other_rels = [r for r in rels if r[2] not in PRIORITY_RELATIONS]
            selected_rels = (priority_rels + other_rels)[:50]
            
            for src, tgt, rel_type, rel_data in selected_rels:
                src_node = self.graph_store.query_entity(src)
                tgt_node = self.graph_store.query_entity(tgt)
                if src_node and tgt_node:
                    rel_str = f"{src_node.get('name', src)} --[{rel_type}]--> {tgt_node.get('name', tgt)}"
                    context_parts.append(rel_str)
                    
        return "\n\n".join(context_parts) if context_parts else "No relevant entities found in Knowledge Graph."

    def query(self, question):
        context = self.retrieve_context(question)
        
        system_prompt = """You are an expert analyst answering questions using a Knowledge Graph.
        Relationships are shown as: EntityA --[RELATIONSHIP_TYPE]--> EntityB.
        Use the context to answer directly."""
        
        user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        
        output = self.client.query(user_prompt, system_prompt)
        return self.formatter.format(output, question)

class HybridRAG:
    """Orchestrates KG and Vector RAG"""
    def __init__(self, kg_rag, vector_rag):
        self.kg_rag = kg_rag
        self.vector_rag = vector_rag
        self.router = QueryRouter()
        self.client = vector_rag.client
        self.formatter = vector_rag.formatter
    
    def query(self, question):
        mode = self.router.route(question)
        print(f"🔀 HybridRAG: Routing query to '{mode}' mode")
        
        if mode == 'kg':
            return self.kg_rag.query(question)
        elif mode == 'vector':
            return self.vector_rag.query(question)
        else:
            # Hybrid
            print("⚡ HybridRAG: Fetching context from both systems...")
            kg_context = self.kg_rag.retrieve_context(question)
            vec_context = self.vector_rag.retrieve_context(question)
            
            combined_context = f"""
            [STRUCTURED DATA from Knowledge Graph]
            {kg_context}
            
            [TEXTUAL EVIDENCE from Document Chunks]
            {vec_context}
            """
            
            system_prompt = """You are an expert analyst. You have access to both a Knowledge Graph (structured data) and Document Chunks (text).
            - Use KG data for specific relationships, ownership paths, and specific stats.
            - Use Textual Evidence for definitions, policies, and detailed descriptions.
            - Resolve conflicts by prioritizing the Textual Evidence if it quotes the document directly, unless the Question is about graph structure (e.g. paths)."""
            
            user_prompt = f"Context:\n{combined_context}\n\nQuestion: {question}\n\nAnswer:"
            
            output = self.client.query(user_prompt, system_prompt)
            return self.formatter.format(output, question)

class VectorRAG:
    """Vector-based RAG using embeddings and cosine similarity"""
    
    def __init__(self, doc_folder):
        # Lazy import to avoid dependency issues at startup
        from utils.embedding_utils import get_embedding_model, cosine_similarity
        
        self.doc_folder = doc_folder
        self.client = DeepSeekClient()
        self.formatter = AnswerFormatter()
        self.cosine_similarity = cosine_similarity  # Store reference
        
        # Load chunks
        chunks_path = os.path.join(doc_folder, 'chunks.json')
        with open(chunks_path, 'r') as f:
            self.chunks = json.load(f)
        
        # Load embeddings
        embeddings_path = os.path.join(doc_folder, 'embeddings.npy')
        self.embeddings = np.load(embeddings_path)
        
        # Get embedding model for query encoding
        self.model = get_embedding_model()
        
        print(f"Vector RAG loaded: {len(self.chunks)} chunks")
    
    def retrieve_context(self, question, top_k=5):
        """Retrieve relevant context chunks"""
        # Encode question
        question_embedding = self.model.encode([question], convert_to_numpy=True)[0]
        
        # Compute cosine similarity
        similarities = self.cosine_similarity(question_embedding, self.embeddings)
        
        # Get top-K chunks
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Build context from top chunks
        context_parts = []
        for idx in top_indices:
            chunk = self.chunks[idx]
            score = float(similarities[idx])
            context_parts.append(f"[Score: {score:.3f}] {chunk['text']}")
        
        return "\n\n".join(context_parts)

    def query(self, question, top_k=5):
        """Query using vector similarity"""
        context = self.retrieve_context(question, top_k)
        
        # Generate answer
        system_prompt = """You are an expert analyst answering questions about IPO documents.

Use the provided text chunks to answer the question accurately and concisely.
Each chunk has a relevance score. Higher scores indicate more relevant content.
Cite specific information from the chunks in your answer."""

        user_prompt = f"""Context:
{context}

Question: {question}

Answer:"""
        
        output = self.client.query(user_prompt, system_prompt)
        return self.formatter.format(output, question)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/simple')
def simple():
    return render_template('simple.html')

@app.route('/api/documents', methods=['GET'])
def list_documents():
    documents = load_documents_index()
    return jsonify({'documents': documents})

@app.route('/api/upload', methods=['POST'])
def upload_and_process():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"File uploaded: {filename}")
        
        # Calculate hash
        file_hash = get_file_hash(filepath)
        
        # Check for duplicate
        duplicate = check_duplicate(file_hash)
        if duplicate:
            os.remove(filepath)
            return jsonify({
                'error': 'Duplicate file',
                'message': f'This document already exists as "{duplicate["display_name"]}"',
                'existing_document': duplicate
            }), 409
        
        # Generate document ID
        document_id = generate_document_id(filename)
        doc_folder = os.path.join(app.config['DOCUMENTS_FOLDER'], document_id)
        os.makedirs(doc_folder, exist_ok=True)
        
        print(f"Processing document: {document_id}")
        
        # Extract and process (Simplified for now - no embeddings)
        pages = extract_pages(filepath)
        # chapters = detect_chapters(pages)
        # chunks = build_chunks(pages, chapters)
        
        # NOTE: Embedding generation disabled to avoid dependency issues
        # embeddings, embedding_meta = encode_chunks(chunks)
        
        # Create document metadata
        document_meta = {
            'document_id': document_id,
            'filename': filename,
            'display_name': os.path.splitext(filename)[0].replace('_', ' ').title(),
            'file_hash': file_hash,
            'upload_date': datetime.now().isoformat(),
            'total_pages': len(pages),
            'total_chapters': 0, # len(chapters),
            'total_chunks': 0, # len(chunks),
            'file_path': filepath
        }
        
        # Add to index
        documents = load_documents_index()
        documents.append(document_meta)
        save_documents_index(documents)
        
        print(f"Document processed successfully: {document_id}")
        
        return jsonify({
            'document': document_meta,
            'message': f'Successfully processed {filename} (KG generation pending)'
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# Initialize global RAG instances
kg_rag = None
vector_rag = None
hybrid_rag = None

@app.route('/api/ask', methods=['POST'])
def ask_question():
    data = request.json
    question = data.get('question', '').strip()
    document_id = data.get('document_id', '').strip()
    rag_mode = data.get('rag_mode', 'auto').strip().lower()  # explicit 'kg', 'vector' or 'auto'/'hybrid'
    
    print(f"\n{'='*50}\n🔔 BACKEND RECEIVED QUESTION: {question}\n📄 DOCUMENT ID: {document_id}\n🔧 RAG MODE: {rag_mode.upper()}\n{'='*50}\n", flush=True)
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    if not document_id:
        return jsonify({'error': 'No document selected'}), 400
    
    def generate():
        global kg_rag, vector_rag, hybrid_rag
        
        try:
            doc_folder = os.path.join(app.config['DOCUMENTS_FOLDER'], document_id)
            
            # Initialize Vector RAG if needed
            if vector_rag is None and rag_mode in ['vector', 'auto', 'hybrid']:
                yield json.dumps({"type": "status", "msg": "Initializing Vector RAG..."}) + "\n"
                chunks_path = os.path.join(doc_folder, 'chunks.json')
                embeddings_path = os.path.join(doc_folder, 'embeddings.npy')
                if not os.path.exists(chunks_path) or not os.path.exists(embeddings_path):
                     yield json.dumps({"type": "error", "msg": "Vector embeddings not found"}) + "\n"
                     return
                vector_rag = VectorRAG(doc_folder)

            # Initialize KG RAG if needed
            if kg_rag is None and rag_mode in ['kg', 'auto', 'hybrid']:
                 yield json.dumps({"type": "status", "msg": "Initializing Knowledge Graph..."}) + "\n"
                 kg_path = os.path.join(doc_folder, 'knowledge_graph', 'knowledge_graph.json')
                 if not os.path.exists(kg_path):
                     yield json.dumps({"type": "error", "msg": "Knowledge Graph not found"}) + "\n"
                     return
                 
                 # Load entity map
                 with open(os.path.join(doc_folder, 'knowledge_graph', 'entities_enriched.json'), 'r') as f:
                    entities = json.load(f)
                    entity_map = {e['name'].lower(): e for e in entities}
                 
                 graph_store = GraphStore.load(kg_path)
                 kg_rag = KnowledgeGraphRAG(graph_store, entity_map)
            
            # Initialize Hybrid RAG
            if hybrid_rag is None and rag_mode in ['auto', 'hybrid']:
                # Ensure components are available
                if kg_rag is None or vector_rag is None:
                     yield json.dumps({"type": "error", "msg": "Hybrid mode requires both KG and Vector RAG"}) + "\n"
                     return
                hybrid_rag = HybridRAG(kg_rag, vector_rag)

            
            # Execute Query
            yield json.dumps({"type": "status", "msg": f"Analyzing query (Mode: {rag_mode})..."}) + "\n"
            
            answer = ""
            if rag_mode == 'vector':
                answer = vector_rag.query(question)
            elif rag_mode == 'kg':
                answer = kg_rag.query(question)
            else:
                # 'auto' or 'hybrid'
                answer = hybrid_rag.query(question)
                
            yield json.dumps({"type": "token", "content": answer}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "msg": str(e)}) + "\n"

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

if __name__ == '__main__':
    print("Server starting (Hybrid RAG Mode)...")
    # Disable debug/reloader to prevent mutex lock issues on Apple Silicon
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
