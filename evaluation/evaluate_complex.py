
import requests
import json
import time
import os
import argparse
from typing import List, Dict

# Configuration
API_URL = "http://localhost:5000/api/ask"
DOCUMENT_ID = "policybazar_ipo"
QUESTIONS_FILE = "complex_questions.json"
OUTPUT_DIR = "evaluation_complex"

def load_questions(filepath: str) -> List[Dict]:
    with open(filepath, 'r') as f:
        return json.load(f)

def query_rag(question: str, rag_mode: str) -> Dict:
    """Query the RAG API"""
    payload = {
        "question": question,
        "document_id": DOCUMENT_ID,
        "rag_mode": rag_mode
    }
    
    try:
        start_time = time.time()
        # Enable streaming to handle NDJSON
        response = requests.post(API_URL, json=payload, stream=True)
        
        if response.status_code == 200:
            full_answer = ""
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        # The API sends the full answer in a "token" message
                        if data.get("type") == "token":
                            full_answer += data.get("content", "")
                    except json.JSONDecodeError:
                        continue
            
            latency = time.time() - start_time
            return {
                "answer": full_answer,
                "latency": latency,
                "error": None
            }
        else:
            return {
                "answer": "",
                "latency": 0,
                "error": f"API Error: {response.status_code}"
            }
    except Exception as e:
        return {
            "answer": "",
            "latency": 0,
            "error": str(e)
        }

def evaluate_complex_questions():
    print(f"Loading questions from {QUESTIONS_FILE}...")
    questions = load_questions(QUESTIONS_FILE)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    results = []
    
    print(f"Starting evaluation of {len(questions)} complex questions...")
    print("-" * 80)
    
    for i, q in enumerate(questions):
        q_id = q['id']
        question_text = q['question']
        expected = q['expected_answer']
        
        print(f"\n[{i+1}/{len(questions)}] Processing {q_id}...")
        print(f"Question: {question_text[:100]}...")
        
        # Query KG RAG
        print("  Querying KG RAG...", end="", flush=True)
        kg_result = query_rag(question_text, "kg")
        print(f" Done ({kg_result['latency']:.2f}s)")
        
        # Query Vector RAG
        print("  Querying Vector RAG...", end="", flush=True)
        vector_result = query_rag(question_text, "vector")
        print(f" Done ({vector_result['latency']:.2f}s)")
        
        # Query Hybrid RAG
        print("  Querying Hybrid RAG...", end="", flush=True)
        hybrid_result = query_rag(question_text, "auto")
        print(f" Done ({hybrid_result['latency']:.2f}s)")
        
        # Store result
        result_entry = {
            "id": q_id,
            "question": question_text,
            "expected_answer": expected,
            "kg_rag": {
                "answer": kg_result['answer'],
                "latency": kg_result['latency'],
                "error": kg_result['error']
            },
            "vector_rag": {
                "answer": vector_result['answer'],
                "latency": vector_result['latency'],
                "error": vector_result['error']
            },
            "hybrid_rag": {
                "answer": hybrid_result['answer'],
                "latency": hybrid_result['latency'],
                "error": hybrid_result['error']
            }
        }
        results.append(result_entry)
        
        # Save intermediate
        with open(f"{OUTPUT_DIR}/results_intermediate.json", 'w') as f:
            json.dump(results, f, indent=2)
            
    # Save final results
    final_path = f"{OUTPUT_DIR}/complex_eval_results.json"
    with open(final_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 80)
    print(f"Evaluation complete. Results saved to {final_path}")
    print("=" * 80)

if __name__ == "__main__":
    evaluate_complex_questions()
