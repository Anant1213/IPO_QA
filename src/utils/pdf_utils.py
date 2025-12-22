"""
PDF processing utilities for extracting text from IPO documents.
"""

import fitz  # PyMuPDF
from typing import List, Dict


def extract_pages(pdf_path: str) -> List[Dict]:
    """
    Extract text from PDF page by page.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dicts with page_num and text for each page
    """
    print(f"Opening PDF: {pdf_path}")
    
    pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        print(f"Total pages in PDF: {total_pages}")
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text("text")
            
            pages.append({
                "page_num": page_num + 1,  # 1-indexed for user-friendliness
                "text": text
            })
            
            if (page_num + 1) % 10 == 0:
                print(f"Processed {page_num + 1}/{total_pages} pages...")
        
        doc.close()
        print(f"Successfully extracted text from {total_pages} pages")
        
    except Exception as e:
        print(f"Error extracting pages from PDF: {e}")
        raise
    
    return pages
