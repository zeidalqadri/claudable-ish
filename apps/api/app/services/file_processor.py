"""
Document Context Processor
Simple text extraction from PDFs and text files for Claude context
"""
import os
import tempfile
from typing import Optional
import logging

# Setup logging
logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Custom exception for document processing errors"""
    pass


async def extract_text_from_pdf(pdf_content: bytes, filename: str) -> str:
    """
    Extract text from PDF content for Claude context
    
    Args:
        pdf_content: Raw PDF file content
        filename: Original filename for error reporting
        
    Returns:
        Extracted text content
    """
    try:
        # Import PyPDF2 for PDF processing
        import PyPDF2
        import io
        
        # Read PDF from bytes
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        
        # Extract text from all pages (limit to first 20 pages for context)
        max_pages = min(20, len(pdf_reader.pages))
        text_content = []
        
        for page_num in range(max_pages):
            try:
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text.strip():
                    text_content.append(text.strip())
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1} of {filename}: {e}")
                continue
        
        full_text = "\n\n".join(text_content)
        
        # Truncate if too long for context (Claude has token limits)
        max_chars = 50000  # Approximately 12,500 tokens
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n\n[Content truncated for context length...]"
        
        logger.info(f"Extracted {len(full_text)} characters from PDF: {filename}")
        return full_text
        
    except ImportError:
        raise DocumentProcessingError("PyPDF2 not installed. Cannot process PDF files.")
    except Exception as e:
        logger.error(f"PDF text extraction failed for {filename}: {e}")
        raise DocumentProcessingError(f"Failed to extract text from PDF: {str(e)}")


async def extract_text_from_file(file_content: bytes, filename: str, mime_type: str) -> str:
    """
    Extract text from uploaded file for Claude context
    
    Args:
        file_content: Raw file content
        filename: Original filename
        mime_type: MIME type of the file
        
    Returns:
        Extracted text content
    """
    try:
        # Handle PDF files
        if mime_type == 'application/pdf':
            return await extract_text_from_pdf(file_content, filename)
        
        # Handle text files
        elif mime_type.startswith('text/'):
            try:
                # Try UTF-8 first
                text = file_content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    # Fallback to latin-1
                    text = file_content.decode('latin-1')
                except UnicodeDecodeError:
                    # Last resort - ignore errors
                    text = file_content.decode('utf-8', errors='ignore')
            
            # Truncate if too long
            max_chars = 50000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Content truncated for context length...]"
                
            logger.info(f"Extracted {len(text)} characters from text file: {filename}")
            return text
        
        # Handle other document types that might contain text
        elif mime_type in ['application/rtf', 'application/msword']:
            # For now, just return a message that the file type is not supported
            return f"[Document '{filename}' uploaded but text extraction not supported for {mime_type}]"
        
        else:
            return f"[File '{filename}' uploaded but is not a text or PDF document]"
            
    except Exception as e:
        logger.error(f"Text extraction failed for {filename}: {e}")
        return f"[Failed to extract text from '{filename}': {str(e)}]"


def validate_document_file(file_content: bytes, mime_type: str, max_size_mb: int = 50) -> bool:
    """
    Validate document file for security and size
    
    Args:
        file_content: Raw file content
        mime_type: MIME type of the file
        max_size_mb: Maximum file size in MB
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check file size
        size_mb = len(file_content) / (1024 * 1024)
        if size_mb > max_size_mb:
            logger.warning(f"File too large: {size_mb:.1f}MB > {max_size_mb}MB limit")
            return False
        
        # Validate PDF header if it's a PDF
        if mime_type == 'application/pdf':
            if not file_content.startswith(b'%PDF-'):
                logger.warning("Invalid PDF file - missing PDF header")
                return False
        
        # Basic validation passed
        return True
        
    except Exception as e:
        logger.error(f"File validation failed: {e}")
        return False