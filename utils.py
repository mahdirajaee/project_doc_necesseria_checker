"""
Utility functions for the grant documentation crawler.
"""
import logging
import os
import re
import string
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def setup_logging(log_level: str = "INFO") -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

def clean_text(text: Optional[str]) -> str:
    """
    Cleans and normalizes text for documentation extraction.
    
    Args:
        text (Optional[str]): The text to clean.
        
    Returns:
        str: The cleaned text.
    """
    if text is None:
        return ""
    
    text = normalize_whitespace(text)
    
    # Normalize unicode characters
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u00A0", " ")  # Non-breaking space
    text = text.replace("\u2022", "•")  # Bullet point
    
    # Clean up bullet points for better readability
    text = re.sub(r'•\s*([•\-*])\s*', '• ', text)  # Remove double bullets
    text = re.sub(r'([.!?])\s+([A-Z])', r'\1 \2', text)  # Fix sentence spacing
    
    # Remove excessive punctuation
    text = re.sub(r'([.!?,:;]){2,}', r'\1', text)
    
    # Normalize Italian definite articles
    text = re.sub(r'\b(l)\s+([aeiouAEIOU])', r"l'\2", text)
    
    # Fix spacing around punctuation
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    
    # Remove any bullet-points or numbering at the beginning of the text
    text = re.sub(r'^[•\-*\d]+[\.\)]*\s*', '', text)
    
    return text

def normalize_whitespace(text: Optional[str]) -> str:
    """
    Normalizes whitespace in text.
    
    Args:
        text (Optional[str]): The text to normalize.
        
    Returns:
        str: The text with normalized whitespace.
    """
    if text is None:
        return ""
    
    # Replace multiple whitespace with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    return text.strip()

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to ensure it's valid across operating systems.
    
    Args:
        filename (str): The filename to sanitize.
        
    Returns:
        str: A sanitized filename.
    """
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    sanitized = ''.join(c for c in filename if c in valid_chars)
    
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    
    # Limit length
    if len(sanitized) > 255:
        base, ext = os.path.splitext(sanitized)
        sanitized = base[:255 - len(ext)] + ext
    
    # Ensure we have something
    if not sanitized:
        sanitized = "unnamed_file"
    
    return sanitized

def is_valid_url(url: str) -> bool:
    """
    Checks if a URL is valid.
    
    Args:
        url (str): The URL to check.
        
    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Truncates text to a maximum length while preserving complete sentences.
    
    Args:
        text (str): The text to truncate.
        max_length (int): Maximum length of the truncated text.
        
    Returns:
        str: The truncated text.
    """
    if not text or len(text) <= max_length:
        return text
    
    # Find the last period before max_length
    last_period = text[:max_length].rfind('.')
    
    # If no period found, truncate at max_length
    if last_period == -1:
        return text[:max_length] + "..."
    
    # Truncate at the last period before max_length
    return text[:last_period + 1]