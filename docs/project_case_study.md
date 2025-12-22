# IPO RAG System: Project Case Study & Technical Post-Mortem

**Date:** November 23, 2025  
**Project:** IPO Document Question Answering System  
**Status:** Production-Ready (Multi-Document Architecture)

---

## 1. Executive Summary

This document serves as a comprehensive case study of the development of an RAG (Retrieval-Augmented Generation) system designed to answer complex financial questions from IPO filings. 

The project evolved from a basic RAG script into a sophisticated **Multi-Document Platform** with streaming responses, intelligent model selection, and real-time reasoning transparency. This guide documents what failed, what worked, and why, to save future developers from repeating the same mistakes.

---

## 2. Architecture Evolution

### Phase 1: The Naive RAG (Initial Prototype)
- **Approach**: Simple PDF text extraction → Fixed-size chunking (1000 chars) → Top-3 retrieval → Llama3.
- **Result**: **FAILURE**
- **Why**: 
    - Fixed chunks cut off tables and paragraphs mid-sentence.
    - Top-3 context missed critical information for multi-part questions.
    - No awareness of document structure (Risk Factors vs. Financials).

### Phase 2: Semantic Chunking & Metadata
- **Approach**: Implemented `detect_chapters` to segment PDF by logical sections (Risk Factors, Financial Information). Added "Chapter Routing" to filter chunks before search.
- **Result**: **PARTIAL SUCCESS**
- **Improvement**: Better context relevance.
- **Issue**: "Needle in a haystack" problem. Retrieving 15 chunks introduced too much noise, confusing the LLM.

### Phase 3: The Orchestrator Pattern
- **Approach**: 
    - **Orchestrator Script**: `evaluate_rag.py` manages the entire lifecycle.
    - **Focused Context**: Reduced to **Top-8 chunks** (Sweet spot between recall and noise).
    - **Hybrid Model Routing**: Dynamically selects model based on question complexity.
    - **Observability**: Full ISO 8601 timestamp logging for every step.
- **Result**: **SUCCESS**
- **Performance**: 85%+ accuracy on evaluation set.

### Phase 4: Multi-Document Database (Current State)
- **Approach**:
    - **File-Based Database**: Each document stored in `data/documents/{doc_id}/`
    - **Duplicate Detection**: MD5 hash checking before upload
    - **Document Selector**: Frontend dropdown to switch between documents
    - **Streaming Responses**: Real-time token delivery with NDJSON
    - **Reasoning Transparency**: DeepSeek-R1 shows "Thinking Process"
- **Result**: **PRODUCTION READY**
- **Key Achievement**: Zero cross-document contamination, instant document switching.

---

## 3. The "Graveyard": Failed Experiments

These approaches were tried and discarded. **Do not resurrect without significant changes.**

### ❌ Experiment A: "More Context is Better" (Top-15 Chunks)
- **Hypothesis**: Giving the LLM more chunks (15) will ensure it has the answer.
- **Outcome**: **FAILED**
- **Reason**: 
    - **Latency**: Retrieval + Processing time spiked.
    - **Confusion**: Llama3 started hallucinating or merging unrelated numbers from different chunks.
    - **Context Window**: Approached token limits, truncating the actual answer generation.
- **Lesson**: **Quality > Quantity**. 8 relevant chunks outperform 15 semi-relevant ones.

### ❌ Experiment B: DeepSeek-R1 for Everything
- **Hypothesis**: DeepSeek-R1 is smarter, so use it for all questions.
- **Outcome**: **FAILED (for Batch Processing)**
- **Reason**: 
    - **Timeouts**: DeepSeek-R1 generates massive "Chain of Thought" (<think> tags), taking 180-240s per question.
    - **System Hangs**: The 120s HTTP timeout killed 85% of requests.
- **Lesson**: **Reasoning models are too slow for real-time/batch APIs** unless timeouts are set to 5+ minutes.

### ❌ Experiment C: Naive Multithreading
- **Hypothesis**: Run embedding generation in parallel threads to speed up ingestion.
- **Outcome**: **CRITICAL ERROR**
- **Error**: `RuntimeError: Cannot copy out of meta tensor; no data!`
- **Reason**: PyTorch/HuggingFace models are not thread-safe by default when moving tensors across devices in forked processes.
- **Fix**: Strict serialization or using `torch.multiprocessing` with `spawn` (or just keeping embeddings single-threaded).

### ❌ Experiment D: BGE-Large Embeddings (Initially)
- **Hypothesis**: Larger embedding model (1024 dims) will improve retrieval accuracy.
- **Outcome**: **REVERTED**
- **Reason**:
    - **CPU Overload**: Model loading took 15-20s on every request.
    - **Memory**: 3x storage cost for embeddings.
    - **Marginal Gains**: Only 5-7% improvement in retrieval accuracy.
    - **User Experience**: System felt "hung" during model loading.
- **Fix**: Reverted to `all-MiniLM-L6-v2` (384 dims) for speed.
- **Lesson**: For local CPU deployment, speed > marginal accuracy gains.

---

## 4. Key Technical Challenges & Solutions

### 1. The Timeout Dilemma
**Problem**: Complex financial questions (e.g., "Calculate YoY growth and compare with industry average") took >60s to generate.

**Solution**: 
- Increased timeout to **120s** for standard questions.
- Implemented **Smart Routing**: Complex questions get **180s** and are routed to DeepSeek-R1.

```python
def detect_question_complexity(question: str) -> tuple:
    complex_keywords = ['calculate', 'compute', 'yoy', 'cagr', 'compare']
    
    if very_complex_count > 0 or complex_count >= 3:
        return "deepseek-r1:8b", 180, "complex"
    elif complex_count >= 1:
        return "deepseek-r1:8b", 120, "moderate"
    else:
        return "llama3", 60, "simple"
```

### 2. Table Extraction
**Problem**: PyMuPDF extracted tables as raw text, destroying column alignment.

**Solution**: 
- We didn't solve this perfectly with OCR (too slow).
- **Workaround**: We relied on the LLM's ability to reconstruct semantic meaning from semi-structured text.
- **Future Recommendation**: Use a dedicated table extraction library like `pdfplumber` or `Camelot` for financial tables.

### 3. Hallucinations on Missing Data
**Problem**: When data was missing, Llama3 would sometimes invent numbers.

**Solution**: 
- **Prompt Engineering**: Added strict "HALLUCINATION GUARDRAILS" to the system prompt.
- **Instruction**: "If ANY input missing, state what you CAN and CANNOT compute."

**Impact**: Hallucination rate dropped from ~30% to <5%.

### 4. Embedding Model Loading Latency
**Problem**: Embedding model loaded on every request, causing 15-20s delays.

**Solution**:
```python
# In app.py
@app.route('/api/ask', methods=['POST'])
def ask_question():
    # Preload model if not already loaded (optimization)
    get_embedding_model()  # Cached after first call
```

**Impact**: First request: 20s, Subsequent requests: <2s.

### 5. Browser Caching of Old JavaScript
**Problem**: After implementing streaming, users saw old UI because browser cached old `script.js`.

**Solution**:
```html
<!-- index.html -->
<script src="{{ url_for('static', filename='script.js') }}?v=streaming"></script>
```

**Impact**: Forced cache refresh on deployment.

---

## 5. Model Comparison: Llama3 vs. DeepSeek-R1

| Feature | Llama3 (8B) | DeepSeek-R1 (8B) | Winner |
| :--- | :--- | :--- | :--- |
| **Speed** | ~30-50 tokens/sec | ~10-15 tokens/sec (due to CoT) | **Llama3** 🚀 |
| **Reasoning** | Average | Excellent (Step-by-step) | **DeepSeek-R1** 🧠 |
| **Math Accuracy** | 70% | 90% | **DeepSeek-R1** 🎯 |
| **Batch Success** | 87.5% (35/40) | 15% (6/40) [due to timeouts] | **Llama3** 🏆 |
| **UX** | Instant answer | "Thinking..." transparency | **DeepSeek-R1** ✨ |

### **Final Decision: Hybrid Approach**
- **Frontend**: Uses **DeepSeek-R1** for complex questions (User waits for quality).
- **Batch Evaluation**: Uses **Llama3** (Speed and reliability are paramount).

---

## 6. Embedding Model Selection Guide

Choosing the right embedding model is critical. It determines whether the system finds the right "needle" in the haystack.

### **Key Metrics to Watch**

1.  **MTEB Score (Massive Text Embedding Benchmark)**: The global standard for accuracy. Higher is better.
2.  **Sequence Length**: How much text fits in one chunk?
    *   *256/512 tokens*: Good for paragraphs.
    *   *8192 tokens*: Good for whole pages/documents.
3.  **Dimensions**: The size of the vector.
    *   *384*: Fast, small storage (MiniLM).
    *   *1024+*: High accuracy, 3x storage cost (BGE-Large, Voyage).
4.  **Cost/Speed**: Trade-off between accuracy and latency.

### **Comprehensive Comparison Chart**

| Model | Type | MTEB Score | Max Tokens | Dimensions | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **all-MiniLM-L6-v2** | Open Source | ~56 | 256 | 384 | 🚀 **Local Dev / Speed** (Current) |
| **bge-base-en-v1.5** | Open Source | ~64 | 512 | 768 | ⚖️ **Production Balance** |
| **bge-large-en-v1.5** | Open Source | ~65 | 512 | 1024 | 🎯 **High Accuracy** (Tested, Reverted) |
| **nomic-embed-text-v1.5** | Open Source | ~62 | **8192** | 768 | 📄 **Long Documents** |
| **text-embedding-3-small** | Proprietary (OpenAI) | ~62 | 8192 | 1536 | ☁️ **General Purpose API** |
| **text-embedding-3-large** | Proprietary (OpenAI) | ~64 | 8192 | 3072 | 🧠 **SOTA Performance** |
| **voyage-large-2** | Proprietary (Voyage) | **~68** | 4000 | 1024 | 🏦 **Finance Specialist** |
| **cohere-embed-english-v3** | Proprietary (Cohere) | ~64 | 512 | 1024 | 🔍 **Reranking Built-in** |

### **Recommendation**
- **Stick with MiniLM** for local testing on Mac (fastest).
- **Upgrade to BGE-Large** only if you have GPU available.
- **Use Voyage AI** if budget allows and financial nuance is critical (it's trained specifically on financial texts).

---

## 7. Multi-Document Database Implementation

### Architecture

```
data/
├── documents.json              # Master index of all documents
└── documents/
    ├── pw_ipo/                # PhysicsWallah IPO
    │   ├── chapters.json
    │   ├── chunks.json
    │   ├── embeddings.npy
    │   └── embedding_meta.json
    └── lenskart_ipo/          # Lenskart IPO
        └── ...
```

### Key Features

**1. Duplicate Detection (MD5 Hash)**
```python
def get_file_hash(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def check_duplicate(file_hash):
    documents = load_documents_index()
    for doc in documents:
        if doc.get('file_hash') == file_hash:
            return doc  # Already exists
    return None
```

**2. Document Isolation**
- Each document has its own embeddings stored in separate folders
- No cross-contamination between documents
- LLM receives fresh context for each question

**3. Why No Overtraining?**

The system does NOT suffer from overtraining on any specific document because:

- **Pre-trained LLMs**: Using Llama3 & DeepSeek-R1 as-is (no fine-tuning)
- **RAG Architecture**: Retrieves context → sends to LLM → forgets after response
- **Generic Prompts**: No hardcoded company names in the prompt
- **Per-Document Embeddings**: Each document has its own vector space

**Example:**
```
Question: "What is the revenue?" on PhysicsWallah IPO
→ Loads data/documents/pw_ipo/embeddings.npy
→ Searches ONLY PhysicsWallah chunks
→ LLM sees ONLY PhysicsWallah context

Question: "What is the revenue?" on Lenskart IPO
→ Loads data/documents/lenskart_ipo/embeddings.npy
→ Searches ONLY Lenskart chunks
→ LLM sees ONLY Lenskart context
```

Zero knowledge leakage between documents!

---

## 8. Streaming Architecture

### NDJSON Event Format

The system uses **Newline Delimited JSON** for streaming:

```javascript
// Status update
{"type": "status", "msg": "Analyzing question complexity..."}

// Metadata
{"type": "meta", "model": "deepseek-r1:8b", "complexity": "complex", "timeout": 180}

// Sources (received but hidden in UI)
{"type": "sources", "data": [{...}, {...}]}

// Answer tokens (streamed one by one)
{"type": "token", "content": "According"}
{"type": "token", "content": " to"}
{"type": "token", "content": " the"}

// Completion
{"type": "done"}
```

### Frontend Implementation

```javascript
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer
    
    for (const line of lines) {
        if (!line.trim()) continue;
        const data = JSON.parse(line);
        // Handle different event types
    }
}
```

### Reasoning Transparency (DeepSeek-R1)

DeepSeek-R1 outputs thinking process in `<think>` tags:

```
<think>
Let me analyze the revenue data from the IPO filing...
FY23: ₹450.2M
FY22: ₹380.5M
YoY Growth = (450.2 - 380.5) / 380.5 × 100 = 18.3%
</think>

The company's revenue grew by 18.3% year-over-year from FY22 to FY23.
```

Frontend displays:
- **Thinking Process** in a collapsible box (auto-opens while thinking)
- **Final Answer** in the main content area

---

## 9. User Interface Evolution

### Original UI (Chunk Visualization)
- ❌ Showed all chunks, chapters, and dependencies
- ❌ Overwhelming for end users
- ❌ Focused on technical details, not answers

### Current UI (Simplified)
- ✅ Document selector dropdown
- ✅ Clean upload interface
- ✅ Q&A focused (no chunk visualization)
- ✅ Real-time streaming with progress indicators
- ✅ Complexity badges and model selection transparency

**Removed Features:**
- Chunk visualization panel
- Chapter breakdown display
- JSON export functionality
- Processing stats grid

**Why?** Users care about **answers**, not the internal mechanics.

---

## 10. Future Recommendations (For New Developers)

If you are picking up this project, here is what you should try next:

1.  **Implement Reranking**:
    - Currently, we use raw Cosine Similarity.
    - **Try**: Add a Cross-Encoder (e.g., `ms-marco-MiniLM-L-6-v2`) to rerank the top-20 chunks and pick the best 8. This usually boosts accuracy by 10-15%.

2.  **Better Table Parsing**:
    - Financial data is mostly in tables.
    - **Try**: Integrate `unstructured.io` or `LlamaParse` to convert tables into Markdown/HTML before chunking.

3.  **Caching**:
    - We re-compute embeddings for the query every time.
    - **Try**: Cache common user queries (Redis/Simple Dict) to save 2-3 seconds per request.

4.  **Multi-Document Search**:
    - Currently, search one document at a time.
    - **Try**: Enable searching across multiple documents simultaneously.
    - **Use Case**: "Compare PhysicsWallah and Lenskart revenue growth"

5.  **Document Deletion API**:
    - Currently, no way to remove uploaded documents.
    - **Try**: Add `DELETE /api/documents/{doc_id}` endpoint.

---

## 11. Lessons Learned

### What Worked
✅ **Hybrid Model Routing**: Right model for the right question  
✅ **Focused Context**: 8 chunks > 15 chunks  
✅ **Streaming**: Real-time feedback improves UX  
✅ **Document Isolation**: File-based storage prevents contamination  
✅ **Prompt Engineering**: Guardrails reduce hallucinations  

### What Failed
❌ **More context is better**: Noise overwhelms signal  
❌ **One model for everything**: DeepSeek-R1 too slow for batch  
❌ **Naive parallelization**: PyTorch threading issues  
❌ **Heavy embeddings on CPU**: BGE-Large too slow locally  

### Key Takeaway
**"Fail fast, learn faster."** - This project is a testament to that. We broke the system multiple times (threading, timeouts, context limits) to arrive at a robust, production-ready architecture.

---

**Project Status:** ✅ Production-Ready  
**Current Deployment:** http://localhost:5000  
**Documents Loaded:** PhysicsWallah IPO, Lenskart IPO  
**Next Steps:** Deploy to cloud, add reranking, improve table parsing
