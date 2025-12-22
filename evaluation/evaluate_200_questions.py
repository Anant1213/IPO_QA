"""
200-Question RAG Evaluation Script
Extracts Q&A pairs from PDF and tests both KG RAG and Vector RAG.
"""

import fitz  # PyMuPDF
import requests
import json
import time
import re
import os
from datetime import datetime

# Configuration
PDF_PATH = '/Users/anant/Downloads/KG _project/ipo_qa/kg_rag_eval_200_pbfintech_final.pdf'
API_URL = "http://localhost:5000/api/ask"
DOCUMENT_ID = "policybazar_ipo"
OUTPUT_DIR = "evaluation_200"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_qa_pairs(pdf_path):
    """Extract question-answer pairs from the PDF."""
    doc = fitz.open(pdf_path)
    
    full_text = ''
    for page in doc:
        full_text += page.get_text() + '\n'
    
    # Pattern to match Q&A pairs
    # Format: PB-EVAL-### followed by Q: ... A: ...
    pattern = r'(PB-EVAL-\d+)\s*\n?\s*Q:\s*(.*?)\s*\n?\s*A:\s*(.*?)(?=PB-EVAL-\d+|$)'
    
    matches = re.findall(pattern, full_text, re.DOTALL)
    
    qa_pairs = []
    for match in matches:
        qa_id = match[0].strip()
        question = match[1].strip().replace('\n', ' ')
        answer = match[2].strip().replace('\n', ' ')
        
        # Clean up extra whitespace
        question = ' '.join(question.split())
        answer = ' '.join(answer.split())
        
        if question and answer:
            qa_pairs.append({
                'id': qa_id,
                'question': question,
                'reference_answer': answer
            })
    
    return qa_pairs

def query_api(question, rag_mode):
    """Query the RAG API."""
    payload = {
        "question": question,
        "document_id": DOCUMENT_ID,
        "rag_mode": rag_mode
    }
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, stream=True, timeout=120)
        
        full_answer = ""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if data.get("type") == "token":
                        full_answer += data.get("content", "")
                    elif data.get("type") == "error":
                        return None, 0, f"Error: {data.get('msg')}"
                except:
                    pass
                    
        latency = time.time() - start_time
        return full_answer, latency, None
        
    except Exception as e:
        return None, 0, str(e)

def compute_similarity_score(reference, generated):
    """Simple keyword-based similarity score."""
    if not generated or not reference:
        return 0.0
    
    ref_words = set(reference.lower().split())
    gen_words = set(generated.lower().split())
    
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'in', 'to', 'for', 'and', 'or', 'on', 'at', 'by', 'as'}
    ref_words = ref_words - stop_words
    gen_words = gen_words - stop_words
    
    if not ref_words:
        return 0.0
    
    overlap = ref_words.intersection(gen_words)
    return len(overlap) / len(ref_words)

def run_evaluation():
    """Run the full 200-question evaluation."""
    print("="*60)
    print("200-Question RAG Evaluation")
    print("="*60)
    
    # Extract Q&A pairs
    print("\n📄 Extracting Q&A pairs from PDF...")
    qa_pairs = extract_qa_pairs(PDF_PATH)
    print(f"   Found {len(qa_pairs)} Q&A pairs")
    
    if len(qa_pairs) == 0:
        print("ERROR: No Q&A pairs found!")
        return
    
    # Results storage
    results = []
    kg_scores = []
    vector_scores = []
    kg_latencies = []
    vector_latencies = []
    
    print(f"\n🚀 Starting evaluation of {len(qa_pairs)} questions...")
    print("-"*60)
    
    for i, qa in enumerate(qa_pairs):
        print(f"[{i+1}/{len(qa_pairs)}] {qa['id']}: {qa['question'][:50]}...")
        
        # Test KG RAG
        kg_ans, kg_lat, kg_err = query_api(qa['question'], 'kg')
        kg_score = compute_similarity_score(qa['reference_answer'], kg_ans) if kg_ans else 0.0
        
        # Test Vector RAG
        vec_ans, vec_lat, vec_err = query_api(qa['question'], 'vector')
        vec_score = compute_similarity_score(qa['reference_answer'], vec_ans) if vec_ans else 0.0
        
        result = {
            'id': qa['id'],
            'question': qa['question'],
            'reference_answer': qa['reference_answer'],
            'kg_answer': kg_ans if kg_ans else "ERROR: " + str(kg_err),
            'kg_score': round(kg_score, 3),
            'kg_latency': round(kg_lat, 2),
            'vector_answer': vec_ans if vec_ans else "ERROR: " + str(vec_err),
            'vector_score': round(vec_score, 3),
            'vector_latency': round(vec_lat, 2)
        }
        
        results.append(result)
        
        if kg_ans:
            kg_scores.append(kg_score)
            kg_latencies.append(kg_lat)
        if vec_ans:
            vector_scores.append(vec_score)
            vector_latencies.append(vec_lat)
        
        print(f"   KG: {kg_score:.2f} ({kg_lat:.1f}s) | Vector: {vec_score:.2f} ({vec_lat:.1f}s)")
        
        # Brief pause to not overwhelm server
        time.sleep(0.5)
        
        # Save intermediate results every 20 questions
        if (i + 1) % 20 == 0:
            with open(f"{OUTPUT_DIR}/results_intermediate.json", 'w') as f:
                json.dump(results, f, indent=2)
            print(f"   [Checkpoint saved: {i+1} questions]")
    
    # Calculate final metrics
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    avg_kg_score = sum(kg_scores) / len(kg_scores) if kg_scores else 0
    avg_vec_score = sum(vector_scores) / len(vector_scores) if vector_scores else 0
    avg_kg_latency = sum(kg_latencies) / len(kg_latencies) if kg_latencies else 0
    avg_vec_latency = sum(vector_latencies) / len(vector_latencies) if vector_latencies else 0
    
    # Count wins
    kg_wins = sum(1 for r in results if r['kg_score'] > r['vector_score'])
    vec_wins = sum(1 for r in results if r['vector_score'] > r['kg_score'])
    ties = sum(1 for r in results if r['kg_score'] == r['vector_score'])
    
    summary = {
        'total_questions': len(qa_pairs),
        'kg_avg_score': round(avg_kg_score, 3),
        'vector_avg_score': round(avg_vec_score, 3),
        'kg_avg_latency': round(avg_kg_latency, 2),
        'vector_avg_latency': round(avg_vec_latency, 2),
        'kg_wins': kg_wins,
        'vector_wins': vec_wins,
        'ties': ties,
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"\n📊 Summary:")
    print(f"   Total Questions: {summary['total_questions']}")
    print(f"   KG RAG Avg Score: {summary['kg_avg_score']:.3f}")
    print(f"   Vector RAG Avg Score: {summary['vector_avg_score']:.3f}")
    print(f"   KG Wins: {summary['kg_wins']} | Vector Wins: {summary['vector_wins']} | Ties: {summary['ties']}")
    print(f"   KG Avg Latency: {summary['kg_avg_latency']:.2f}s")
    print(f"   Vector Avg Latency: {summary['vector_avg_latency']:.2f}s")
    
    # Save results
    with open(f"{OUTPUT_DIR}/results_full.json", 'w') as f:
        json.dump({'summary': summary, 'results': results}, f, indent=2)
    
    with open(f"{OUTPUT_DIR}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Results saved to {OUTPUT_DIR}/")
    
    return summary, results

if __name__ == "__main__":
    run_evaluation()
