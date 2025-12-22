
import requests
import json
import time
import csv
import os
import numpy as np
from datetime import datetime

# Configuration
API_URL = "http://localhost:5000/api/ask"
DOCUMENT_ID = "policybazar_ipo"
OUTPUT_FILE_JSON = "evaluation_results.json"
OUTPUT_FILE_CSV = "evaluation_results.csv"

# Dataset: 10 Questions (Low, Medium, High)
DATASET = [
    {
        "id": "Q1",
        "difficulty": "Low",
        "category": "Basic Fact",
        "question": "What is the full name of the company?",
        "keywords": ["PB Fintech Limited", "Policybazaar"]
    },
    {
        "id": "Q2",
        "difficulty": "Low",
        "category": "Basic Fact",
        "question": "Who is the CEO of the company?",
        "keywords": ["Yashish Dahiya"]
    },
    {
        "id": "Q3",
        "difficulty": "Low",
        "category": "Basic Fact",
        "question": "Where is the registered office located?",
        "keywords": ["Gurugram", "Haryana", "122001"]
    },
    {
        "id": "Q4",
        "difficulty": "Medium",
        "category": "List/Structure",
        "question": "Who are the promoters of the company?",
        "keywords": ["Yashish Dahiya", "Alok Bansal", "SVF Python"]
    },
    {
        "id": "Q5",
        "difficulty": "Medium",
        "category": "Financial",
        "question": "What was the Total Revenue for Fiscal 2021?",
        "keywords": ["2021", "5913", "million"] # 5,913 million (approx 6k)
    },
    {
        "id": "Q6",
        "difficulty": "Medium",
        "category": "Risk",
        "question": "What are the internal risk factors?",
        "keywords": ["maintain", "partners", "brand", "reputation", "relationships"] # General risk keywords found in risk section
    },
    {
        "id": "Q7",
        "difficulty": "High",
        "category": "Reasoning",
        "question": "Who are the Selling Shareholders in the Offer for Sale?",
        "keywords": ["SVF Python", "Yashish Dahiya", "Alok Bansal", "Founder United Trust", "Shikha Dahiya"]
    },
    {
        "id": "Q8",
        "difficulty": "High",
        "category": "Synthesis",
        "question": "Explain the company's business model.",
        "keywords": ["insurance", "lending", "platform", "consumers", "insurers", "partners", "online"]
    },
    {
        "id": "Q9",
        "difficulty": "High",
        "category": "Complex Financial",
        "question": "What is the restated loss for the year 2021?",
        "keywords": ["2021", "2965", "2980", "million", "loss"] # Value is approx 2900-3000
    },
    {
        "id": "Q10",
        "difficulty": "High",
        "category": "Specificity",
        "question": "Does the company have any subsidiaries? List them.",
        "keywords": ["Policybazaar", "Paisabazaar", "Docprime", "Imo-Ad", "Accurex"]
    }
]

def query_api(question, rag_mode):
    payload = {
        "question": question,
        "document_id": DOCUMENT_ID,
        "rag_mode": rag_mode
    }
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, stream=True)
        
        full_answer = ""
        context_found = False
        
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

def score_answer(answer, expected_keywords):
    if not answer:
        return 0.0
    
    answer_lower = answer.lower()
    matches = 0
    for kw in expected_keywords:
        if kw.lower() in answer_lower:
            matches += 1
            
    return matches / len(expected_keywords) if expected_keywords else 0.0

def run_evaluation():
    results = []
    
    print(f"Starting Evaluation on {len(DATASET)} Questions...")
    print("-" * 60)
    
    for item in DATASET:
        print(f"Processing Q{item['id']}: {item['question']}...")
        
        # Test KG RAG
        kg_ans, kg_lat, kg_err = query_api(item['question'], 'kg')
        kg_score = score_answer(kg_ans, item['keywords'])
        
        # Test Vector RAG
        vec_ans, vec_lat, vec_err = query_api(item['question'], 'vector')
        vec_score = score_answer(vec_ans, item['keywords'])
        
        result_entry = {
            "id": item['id'],
            "question": item['question'],
            "difficulty": item['difficulty'],
            "category": item['category'],
            "expected_keywords": item['keywords'],
            
            "kg_answer": kg_ans if kg_ans else "ERROR",
            "kg_latency": round(kg_lat, 2),
            "kg_score": round(kg_score, 2),
            "kg_error": kg_err,
            
            "vector_answer": vec_ans if vec_ans else "ERROR",
            "vector_latency": round(vec_lat, 2),
            "vector_score": round(vec_score, 2),
            "vector_error": vec_err
        }
        
        results.append(result_entry)
        print(f"   KG Score: {kg_score:.2f} | Vector Score: {vec_score:.2f}")
        time.sleep(1) # Slight pause to be nice to server
        
    # Save Results
    with open(OUTPUT_FILE_JSON, 'w') as f:
        json.dump(results, f, indent=2)
        
    # Save CSV
    with open(OUTPUT_FILE_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Question', 'Difficulty', 'Category', 
                         'KG Answer', 'KG Latency', 'KG Score', 
                         'Vector Answer', 'Vector Latency', 'Vector Score'])
        for r in results:
            writer.writerow([
                r['id'], r['question'], r['difficulty'], r['category'],
                r['kg_answer'][:100].replace('\n', ' ') + '...', r['kg_latency'], r['kg_score'],
                r['vector_answer'][:100].replace('\n', ' ') + '...', r['vector_latency'], r['vector_score']
            ])
            
    print("-" * 60)
    print(f"Evaluation Complete. Results saved to {OUTPUT_FILE_JSON} and {OUTPUT_FILE_CSV}")

if __name__ == "__main__":
    run_evaluation()
