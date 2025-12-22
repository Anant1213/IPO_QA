"""
Text processing utilities for chapter detection and chunking.
"""

from typing import List, Dict, Set
import re
from utils.config import (
    MIN_HEADING_LENGTH,
    UPPERCASE_THRESHOLD,
    IPO_SECTION_KEYWORDS,
    MIN_CHUNK_WORDS,
    MAX_CHUNK_WORDS,
    TARGET_CHUNK_WORDS,
    CHAPTER_ROUTING_RULES,
)


def is_potential_heading(line: str) -> bool:
    """
    Check if a line is likely a chapter heading.
    
    Criteria:
    - Mostly uppercase
    - Above minimum length
    - Not too long (likely not a heading if > 100 chars)
    """
    line = line.strip()
    
    if len(line) < MIN_HEADING_LENGTH or len(line) > 100:
        return False
    
    # Count uppercase letters
    alpha_chars = [c for c in line if c.isalpha()]
    if not alpha_chars:
        return False
    
    uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
    
    return uppercase_ratio >= UPPERCASE_THRESHOLD


def detect_chapters(pages: List[Dict]) -> List[Dict]:
    """
    Detect chapters based on heading patterns.
    
    Args:
        pages: List of page dicts with page_num and text
        
    Returns:
        List of chapter dicts with chapter_id, name, start_page, end_page
    """
    print("\n=== Detecting Chapters ===")
    
    chapters = []
    chapter_id = 0
    
    for i, page in enumerate(pages):
        page_num = page["page_num"]
        text = page["text"]
        
        # Look at first few lines of the page
        lines = text.split('\n')[:10]  # Check first 10 lines
        
        for line in lines:
            line = line.strip()
            
            if is_potential_heading(line):
                # Check if it matches known IPO section keywords
                line_upper = line.upper()
                is_known_section = any(keyword in line_upper for keyword in IPO_SECTION_KEYWORDS)
                
                if is_known_section or len(chapters) == 0:  # Always accept first heading
                    # Close previous chapter if exists
                    if chapters:
                        chapters[-1]["end_page"] = page_num - 1
                    
                    # Start new chapter
                    chapters.append({
                        "chapter_id": chapter_id,
                        "name": line,
                        "start_page": page_num,
                        "end_page": page_num  # Will be updated
                    })
                    
                    print(f"Chapter {chapter_id}: '{line}' (starts at page {page_num})")
                    chapter_id += 1
                    break  # Only one heading per page
    
    # Close last chapter
    if chapters:
        chapters[-1]["end_page"] = pages[-1]["page_num"]
    
    # If no chapters detected, create a single chapter for entire document
    if not chapters:
        print("No chapters detected. Creating single chapter for entire document.")
        chapters.append({
            "chapter_id": 0,
            "name": "FULL DOCUMENT",
            "start_page": pages[0]["page_num"],
            "end_page": pages[-1]["page_num"]
        })
    
    print(f"\nTotal chapters detected: {len(chapters)}")
    return chapters


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def build_chunks(pages: List[Dict], chapters: List[Dict]) -> List[Dict]:
    """
    Build chunks from pages and chapters.
    
    Args:
        pages: List of page dicts
        chapters: List of chapter dicts
        
    Returns:
        List of chunk dicts
    """
    print("\n=== Building Chunks ===")
    
    chunks = []
    chunk_id = 0
    
    # Create page lookup
    page_lookup = {p["page_num"]: p for p in pages}
    
    for chapter in chapters:
        chapter_id = chapter["chapter_id"]
        chapter_name = chapter["name"]
        start_page = chapter["start_page"]
        end_page = chapter["end_page"]
        
        print(f"\nProcessing Chapter {chapter_id}: '{chapter_name}' (pages {start_page}-{end_page})")
        
        # Collect all text for this chapter
        chapter_text = ""
        for page_num in range(start_page, end_page + 1):
            if page_num in page_lookup:
                chapter_text += page_lookup[page_num]["text"] + "\n"
        
        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', chapter_text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Accumulate paragraphs into chunks
        current_chunk_text = ""
        current_chunk_words = 0
        chunk_start_page = start_page
        
        for para in paragraphs:
            para_words = count_words(para)
            
            # If adding this paragraph would exceed max, save current chunk
            if current_chunk_words > 0 and (current_chunk_words + para_words) > MAX_CHUNK_WORDS:
                # Save current chunk
                chunks.append({
                    "chunk_id": chunk_id,
                    "ipo_id": 1,  # Single IPO for now
                    "chapter_id": chapter_id,
                    "chapter_name": chapter_name,
                    "page_start": chunk_start_page,
                    "page_end": end_page,  # Approximate
                    "text": current_chunk_text.strip()
                })
                chunk_id += 1
                
                # Start new chunk
                current_chunk_text = para + "\n"
                current_chunk_words = para_words
            else:
                # Add to current chunk
                current_chunk_text += para + "\n"
                current_chunk_words += para_words
                
                # If we've reached target size, save chunk
                if current_chunk_words >= TARGET_CHUNK_WORDS:
                    chunks.append({
                        "chunk_id": chunk_id,
                        "ipo_id": 1,
                        "chapter_id": chapter_id,
                        "chapter_name": chapter_name,
                        "page_start": chunk_start_page,
                        "page_end": end_page,
                        "text": current_chunk_text.strip()
                    })
                    chunk_id += 1
                    
                    # Reset
                    current_chunk_text = ""
                    current_chunk_words = 0
        
        # Save any remaining text as final chunk for this chapter
        if current_chunk_text.strip() and current_chunk_words >= MIN_CHUNK_WORDS:
            chunks.append({
                "chunk_id": chunk_id,
                "ipo_id": 1,
                "chapter_id": chapter_id,
                "chapter_name": chapter_name,
                "page_start": chunk_start_page,
                "page_end": end_page,
                "text": current_chunk_text.strip()
            })
            chunk_id += 1
        
        print(f"Created {chunk_id - sum(1 for c in chunks if c['chapter_id'] < chapter_id)} chunks for this chapter")
    
    print(f"\nTotal chunks created: {len(chunks)}")
    return chunks


def route_question_to_chapters(question: str, chapters: List[Dict]) -> Set[int]:
    """
    Route a question to relevant chapters based on keywords.
    
    Args:
        question: User's question
        chapters: List of chapter dicts
        
    Returns:
        Set of chapter_ids to search
    """
    question_lower = question.lower()
    selected_chapter_ids = set()
    
    # Check each routing rule
    for chapter_keyword, question_keywords in CHAPTER_ROUTING_RULES.items():
        if any(kw in question_lower for kw in question_keywords):
            # Find chapters matching this keyword
            for chapter in chapters:
                if chapter_keyword in chapter["name"].upper():
                    selected_chapter_ids.add(chapter["chapter_id"])
    
    # If no specific chapters matched, return all chapters
    if not selected_chapter_ids:
        selected_chapter_ids = {c["chapter_id"] for c in chapters}
    
    return selected_chapter_ids


def detect_question_complexity(question: str) -> tuple:
    """
    Detect question complexity and return appropriate model and timeout.
    
    Returns:
        tuple: (model_name, timeout_seconds, complexity_level)
    """
    question_lower = question.lower()
    
    # Keywords indicating complex reasoning/calculations
    complex_keywords = [
        'calculate', 'compute', 'yoy', 'year-over-year', 'cagr', 'ratio', 'margin',
        'compare', 'analyze', 'trend', 'growth rate', 'debt-to-equity',
        'combine', 'relate', 'explain how', 'cross-section', 'integrate',
        'revenue per user', 'arpu', 'standalone vs consolidated',
        'multiple parts', 'breakdown', 'step-by-step'
    ]
    
    # Keywords indicating very complex multi-part questions
    very_complex_keywords = [
        'using risk factors + financial', 'combine information from',
        'relate the company', 'based on our business, risk factors',
        '(a)', '(b)', '(c)',  # Multi-part questions
    ]
    
    # Count complexity indicators
    complex_count = sum(1 for keyword in complex_keywords if keyword in question_lower)
    very_complex_count = sum(1 for keyword in very_complex_keywords if keyword in question_lower)
    
    # Use Llama3 for all questions - more reliable and consistent
    # DeepSeek-R1 doesn't follow formatting instructions properly
    if very_complex_count > 0 or complex_count >= 3:
        # Very complex - use Llama3 with extended timeout and more tokens
        return "llama3", 300, "complex"
    elif complex_count >= 1:
        # Moderately complex - use Llama3 with standard timeout
        return "llama3", 180, "moderate"
    else:
        # Simple - use Llama3 for speed
        return "llama3", 120, "simple"
