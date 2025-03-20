"""
Handles downloading and processing PDF files to extract relevant text.
"""
import logging
import os
import re
import tempfile
from typing import Dict, List, Any, Optional, Tuple
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from pdfminer.high_level import extract_text
from io import BytesIO

import config
from utils import clean_text, sanitize_filename, normalize_whitespace

logger = logging.getLogger(__name__)

class PDFProcessor:
    """Downloads and processes PDF files to extract relevant information."""
    
    def __init__(self):
        """Initialize the PDF processor."""
        self.session = requests.Session()
        self.session.headers.update(config.REQUEST_HEADERS)
        
        # Create download directory if it doesn't exist
        os.makedirs(config.PDF_DOWNLOAD_DIR, exist_ok=True)
    
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=config.RETRY_BACKOFF)
    )
    def download_pdf(self, url: str) -> Optional[str]:
        """
        Downloads a PDF file from a URL.
        
        Args:
            url (str): URL of the PDF to download.
            
        Returns:
            Optional[str]: Path to the downloaded file or None if download failed.
        """
        try:
            # Send a HEAD request first to check the file size
            head_response = self.session.head(url, timeout=config.REQUEST_TIMEOUT, allow_redirects=True)
            
            # Check if the URL is actually a PDF
            content_type = head_response.headers.get('Content-Type', '').lower()
            if 'application/pdf' not in content_type and not url.lower().endswith('.pdf'):
                logger.warning(f"URL {url} is not a PDF: {content_type}")
                return None
            
            # Check file size
            content_length = head_response.headers.get('Content-Length')
            if content_length and int(content_length) > config.MAX_PDF_SIZE:
                logger.warning(f"PDF at {url} is too large ({content_length} bytes)")
                return None
            
            # Download the PDF
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            
            # Create a safe filename from the URL
            filename = sanitize_filename(os.path.basename(url))
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
                
            # Save to file
            filepath = os.path.join(config.PDF_DOWNLOAD_DIR, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Successfully downloaded PDF from {url} to {filepath}")
            return filepath
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading PDF from {url}: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extracts text content from a PDF file.
        
        Args:
            pdf_path (str): Path to the PDF file.
            
        Returns:
            Optional[str]: Extracted text content or None if extraction failed.
        """
        try:
            logger.info(f"Extracting text from {pdf_path}")
            text = extract_text(pdf_path)
            
            if not text:
                logger.warning(f"No text content extracted from {pdf_path}")
                return None
                
            # Clean and normalize the extracted text
            text = normalize_whitespace(text)
            logger.info(f"Successfully extracted {len(text)} characters from {pdf_path}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return None
    
    def process_pdf_content(self, pdf_text: str, context: str = "") -> Dict[str, Any]:
        """
        Processes PDF text to extract structured information.
        
        Args:
            pdf_text (str): The text content of the PDF.
            context (str): Context about the PDF from the link.
            
        Returns:
            Dict[str, Any]: Structured information extracted from the PDF.
        """
        if not pdf_text:
            return {}
        
        result = {
            'context': context,
            'main_content': pdf_text[:5000],  # First part of content
            'sections': {},
            'lists': [],
            'tables': []
        }
        
        # Extract sections based on heading patterns
        section_pattern = re.compile(r'(?:\n|\r\n)([A-Z][A-Za-z0-9\s\-,]+)[\.\:]?(?:\n|\r\n)')
        sections = section_pattern.findall(pdf_text)
        
        for section in sections:
            section_title = section.strip()
            if not section_title or len(section_title) < 3 or len(section_title) > 100:
                continue
                
            # Find section content - from this section title to the next
            start_idx = pdf_text.find(section)
            if start_idx == -1:
                continue
                
            end_idx = pdf_text.find('\n', start_idx + len(section))
            if end_idx == -1:
                continue
                
            # Find the next section or the end of document
            next_section_idx = pdf_text.find('\n', end_idx + 1)
            if next_section_idx == -1:
                section_content = pdf_text[end_idx:].strip()
            else:
                section_content = pdf_text[end_idx:next_section_idx].strip()
            
            if section_content:
                result['sections'][section_title] = clean_text(section_content)
        
        # Extract lists (bullet points, numbered lists)
        list_patterns = [
            r'(?:\n|\r\n)(?:\s*[\•\-\*]\s*)([^\n]+)(?:\n|\r\n)(?:\s*[\•\-\*]\s*)([^\n]+)',  # Bullet lists
            r'(?:\n|\r\n)(?:\s*\d+[\.\)]\s*)([^\n]+)(?:\n|\r\n)(?:\s*\d+[\.\)]\s*)([^\n]+)'  # Numbered lists
        ]
        
        for pattern in list_patterns:
            list_matches = re.findall(pattern, pdf_text)
            if list_matches:
                items = [clean_text(item) for group in list_matches for item in group if clean_text(item)]
                if items:
                    result['lists'].append(items)
        
        # Extract table-like structures
        lines = pdf_text.split('\n')
        potential_table_rows = []
        
        # Look for repeated patterns of spaces or tabs that might indicate columns
        for i, line in enumerate(lines):
            if i > 0 and i < len(lines) - 1:
                if re.search(r'\s{2,}', line) and len(line.strip()) > 10:
                    potential_table_rows.append(line)
        
        if len(potential_table_rows) >= 3:  # At least 3 rows for a table
            result['tables'].append(potential_table_rows)
        
        # Extract information specifically related to grant requirements
        for term in config.SEARCH_TERMS:
            pattern = re.compile(r'(.{0,150}' + re.escape(term) + r'.{0,150})', re.IGNORECASE)
            matches = pattern.findall(pdf_text)
            
            if matches:
                term_key = term.capitalize()
                if term_key not in result:
                    result[term_key] = []
                
                for match in matches:
                    clean_match = clean_text(match)
                    if clean_match and clean_match not in result[term_key]:
                        result[term_key].append(clean_match)
        
        return result
    
    def process_pdf(self, pdf_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Downloads and processes a PDF to extract comprehensive information.
        
        Args:
            pdf_info (Dict[str, Any]): Information about the PDF to process including URL.
            
        Returns:
            Dict[str, Any]: Extracted information from the PDF.
        """
        url = pdf_info['url']
        context = pdf_info.get('context', '')
        is_priority = pdf_info.get('priority', False)
        
        try:
            logger.info(f"Processing {'PRIORITY ' if is_priority else ''}PDF: {url}")
            
            # Download the PDF
            pdf_path = self.download_pdf(url)
            if not pdf_path:
                return {}
                
            # Extract text from the PDF
            pdf_text = self.extract_text_from_pdf(pdf_path)
            if not pdf_text:
                return {}
            
            # Process the PDF content
            result = self.process_pdf_content(pdf_text, context)
            
            # Add metadata
            result['source'] = url
            result['filename'] = os.path.basename(pdf_path)
            result['is_priority'] = is_priority
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF from {url}: {e}")
            return {'source': url, 'error': str(e)}
    
    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("PDF processor session closed")