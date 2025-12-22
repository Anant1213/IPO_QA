"""
Configuration file for IPO Q&A system.
"""

# Embedding Model
# EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"  # High accuracy (1024 dim) - Too slow for local CPU
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"      # Fast (384 dim) - Best for local CPU

# Chunking parameters
MIN_CHUNK_WORDS = 150
MAX_CHUNK_WORDS = 300
TARGET_CHUNK_WORDS = 200

# Chapter detection parameters
MIN_HEADING_LENGTH = 10
UPPERCASE_THRESHOLD = 0.7  # 70% of characters should be uppercase

# Common IPO section names (for chapter detection)
IPO_SECTION_KEYWORDS = [
    "RISK FACTORS",
    "BUSINESS OVERVIEW",
    "INDUSTRY OVERVIEW",
    "FINANCIAL INFORMATION",
    "CAPITAL STRUCTURE",
    "PROMOTERS AND SHAREHOLDING",
    "OBJECTS OF THE ISSUE",
    "MANAGEMENT",
    "REGULATORY",
    "LEGAL",
    "OUTSTANDING LITIGATION",
    "DIVIDEND POLICY",
    "TERMS OF THE ISSUE",
]

# Search parameters
DEFAULT_TOP_K = 5

# Chapter routing keywords
CHAPTER_ROUTING_RULES = {
    "RISK": ["risk", "risks", "threat", "uncertainty", "challenge", "concern"],
    "FINANCIAL": ["revenue", "profit", "ebitda", "pat", "income", "loss", "financial", "earnings", "sales"],
    "PROMOTER": ["promoter", "promoters", "shareholding", "dilution", "equity", "ownership"],
    "BUSINESS": ["business", "operations", "products", "services", "customers"],
    "INDUSTRY": ["industry", "market", "competition", "sector"],
}

# Data paths
DATA_DIR = "data"
# DeepSeek R1 config for Knowledge Graph Extraction
# Using local Llama 3 for fast, reliable extraction
DEEPSEEK_API_KEY = ""  # Not needed for local model
DEEPSEEK_BASE_URL = "http://localhost:11434"  # Local Ollama
DEEPSEEK_MODEL = "llama3:latest"  # Fast and reliable for structured extraction
DEEPSEEK_TEMPERATURE = 0.1  # Low temperature for extraction accuracy
USE_LOCAL_DEEPSEEK = True  # Use local model instead of API
CHAPTERS_FILE = f"{DATA_DIR}/chapters.json"
CHUNKS_FILE = f"{DATA_DIR}/chunks.json"
EMBEDDINGS_FILE = f"{DATA_DIR}/embeddings.npy"
EMBEDDING_META_FILE = f"{DATA_DIR}/embedding_meta.json"
DOCUMENTS_INDEX = f"{DATA_DIR}/documents.json"

# App config
UPLOAD_FOLDER = "uploads"
DOCUMENTS_FOLDER = f"{DATA_DIR}/documents"
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf'}

# Ollama config
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_TEMPERATURE = 0.1
LLM_NUM_PREDICT = 1024
LLM_TOP_P = 0.9
