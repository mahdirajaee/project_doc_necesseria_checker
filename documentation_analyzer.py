"""
Analyzes and summarizes grant information extracted from websites and PDFs.
"""
import logging
import re
from typing import Dict, List, Any, Set, Optional
from datetime import datetime

import nltk
from nltk.tokenize import sent_tokenize

from utils import clean_text, truncate_text

logger = logging.getLogger(__name__)

class DocumentationAnalyzer:
    """Analyzes and summarizes extracted grant information."""
    
    def __init__(self):
        """Initialize the documentation analyzer."""
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        logger.info("Documentation analyzer initialized")
    
    def merge_grant_data(self, web_data: List[Dict[str, Any]], pdf_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merges data from web pages and PDFs into a comprehensive grant overview.
        
        Args:
            web_data (List[Dict[str, Any]]): Information extracted from web pages.
            pdf_data (List[Dict[str, Any]]): Information extracted from PDFs.
            
        Returns:
            Dict[str, Any]: Merged grant information.
        """
        if not web_data and not pdf_data:
            return {}
        
        # Start with basic structure
        merged_data = {
            'title': "",
            'overview': "",
            'sections': {},
            'lists': {},
            'requirements': [],
            'documentation': [],
            'deadlines': [],
            'eligibility': [],
            'funding': [],
            'pdf_sources': []
        }
        
        # Set title from web data if available
        if web_data:
            for data in web_data:
                if data.get('title') and (not merged_data['title'] or 
                                         len(data['title']) > len(merged_data['title'])):
                    merged_data['title'] = data['title']
        
        # If no title from web, try to get from PDFs
        if not merged_data['title'] and pdf_data:
            for data in pdf_data:
                if data.get('context') and len(data['context']) < 100:
                    merged_data['title'] = data['context']
                    break
        
        # Gather all sections into categories
        all_sections = {}
        
        # Process web data
        for data in web_data:
            # Extract overview from main content
            if data.get('main_content') and len(data['main_content']) > len(merged_data['overview']):
                merged_data['overview'] = data['main_content']
            
            # Merge structured info
            if 'structured_info' in data:
                for key, value in data['structured_info'].items():
                    all_sections[key] = value
            
            # Merge lists
            if 'lists' in data:
                for key, value in data['lists'].items():
                    if key not in merged_data['lists']:
                        merged_data['lists'][key] = value
                    else:
                        # Combine lists, removing duplicates
                        existing_items = set(str(item) for item in merged_data['lists'][key])
                        for item in value:
                            if str(item) not in existing_items:
                                merged_data['lists'][key].append(item)
                                existing_items.add(str(item))
            
            # Merge tables - just add them, as tables are harder to merge
            if 'tables' in data and data['tables']:
                table_count = len(merged_data.get('tables', []))
                if 'tables' not in merged_data:
                    merged_data['tables'] = []
                
                for table_key, table_data in data['tables'].items():
                    merged_data['tables'].append({
                        'title': table_key,
                        'data': table_data
                    })
        
        # Process PDF data
        for data in pdf_data:
            # Keep track of PDF sources
            if data.get('source'):
                pdf_info = {
                    'url': data['source'],
                    'filename': data.get('filename', ''),
                    'context': data.get('context', '')
                }
                merged_data['pdf_sources'].append(pdf_info)
            
            # Merge sections
            if 'sections' in data:
                for key, value in data['sections'].items():
                    all_sections[key] = value
            
            # Merge lists
            if 'lists' in data and data['lists']:
                for items in data['lists']:
                    list_title = "Informazioni dal PDF"
                    if data.get('context'):
                        list_title = data['context']
                    
                    if list_title not in merged_data['lists']:
                        merged_data['lists'][list_title] = items
                    else:
                        existing_items = set(str(item) for item in merged_data['lists'][list_title])
                        for item in items:
                            if str(item) not in existing_items:
                                merged_data['lists'][list_title].append(item)
                                existing_items.add(str(item))
            
            # Extract topic-specific information from PDFs
            for key in data.keys():
                search_terms = ['document', 'allegat', 'modulistic', 'certificaz', 'requisit', 'necessari', 'obblig', 'scadenz', 'termin', 'tempistic', 'deadline', 'beneficiari', 'destinatari', 'ammissibil', 'eligibil', 'contribut', 'finanz', 'budget', 'fond', 'spese']
                if key in search_terms and isinstance(data[key], list):
                    category = self._categorize_information(key, data[key])
                    if category:
                        merged_data[category].extend(data[key])
        
        # Categorize all the sections
        for key, value in all_sections.items():
            # Handle sections as either text or lists
            if isinstance(value, list):
                category = self._categorize_information(key, value)
                if category:
                    merged_data[category].extend(value)
            else:
                category = self._categorize_information(key, [value])
                if category:
                    merged_data[category].append(value)
                else:
                    merged_data['sections'][key] = value
        
        # Remove duplicate information in each category
        for category in ['requirements', 'documentation', 'deadlines', 'eligibility', 'funding']:
            if merged_data[category]:
                merged_data[category] = list(dict.fromkeys(merged_data[category]))
        
        return merged_data
    
    def _categorize_information(self, key: str, values: List[str]) -> Optional[str]:
        """
        Categorizes information based on key and content.
        
        Args:
            key (str): The section title or key.
            values (List[str]): The content.
            
        Returns:
            Optional[str]: Category name or None if no specific category.
        """
        key_lower = key.lower()
        
        # Document/requirements related
        if any(term in key_lower for term in ['document', 'allegat', 'modulistic', 'certificaz']):
            return 'documentation'
        
        # Requirements related
        elif any(term in key_lower for term in ['requisit', 'necessari', 'obblig']):
            return 'requirements'
        
        # Deadline related
        elif any(term in key_lower for term in ['scadenz', 'termin', 'tempistic', 'deadline']):
            return 'deadlines'
        
        # Eligibility related
        elif any(term in key_lower for term in ['beneficiari', 'destinatari', 'ammissibil', 'eligibil']):
            return 'eligibility'
        
        # Funding related
        elif any(term in key_lower for term in ['contribut', 'finanz', 'budget', 'fond', 'spese']):
            return 'funding'
        
        # Content-based categorization for values
        if values:
            text = ' '.join(values)
            text_lower = text.lower()
            
            if re.search(r'document|allegat|modulistic|certificaz', text_lower):
                return 'documentation'
            elif re.search(r'scadenz|termin|entro il|deadline', text_lower):
                return 'deadlines'
            elif re.search(r'requisit|necessari|obblig|richiesto', text_lower):
                return 'requirements'
            elif re.search(r'beneficiari|destinatari|ammissibil|eligible', text_lower):
                return 'eligibility'
            elif re.search(r'contribut|finanz|budget|fond|euro|€', text_lower):
                return 'funding'
        
        return None
    
    def _select_most_informative_items(self, items: List[str], max_items: int = 10) -> List[str]:
        """
        Selects the most informative items from a list.
        
        Args:
            items (List[str]): List of text items.
            max_items (int): Maximum number of items to return.
            
        Returns:
            List[str]: List of most informative items.
        """
        if not items:
            return []
            
        if len(items) <= max_items:
            return items
        
        # Score items based on information density
        scored_items = []
        for item in items:
            # Skip very short items
            if len(item) < 15:
                continue
                
            # Score longer items higher
            length_score = min(5, len(item) / 50)
            
            # Score items with specific keywords higher
            keyword_score = 0
            important_keywords = [
                'document', 'allegat', 'modulistic', 'requisit',
                'scadenz', 'termin', 'entro il', 'deadline',
                'beneficiari', 'destinatari', 'ammissibil',
                'contribut', 'finanz', 'budget', 'fond', 'euro', '€',
                'visura', 'camerale', 'bilanci', 'ula', 'dipendenti',
                'brevetto', 'patent', 'concessione', 'identità', 'digitale'
            ]
            
            for keyword in important_keywords:
                if keyword in item.lower():
                    keyword_score += 1
            
            # Score items with numbers and dates higher
            if re.search(r'\d+', item):
                keyword_score += 1
            
            # Final score
            score = length_score + keyword_score
            scored_items.append((item, score))
        
        # Sort by score (highest first) and take top items
        sorted_items = sorted(scored_items, key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_items[:max_items]]
    
    def generate_summary(self, grant_data: Dict[str, Any]) -> str:
        """
        Generates a comprehensive, well-structured summary of the grant information.
        
        Args:
            grant_data (Dict[str, Any]): The merged grant data.
            
        Returns:
            str: A formatted summary of the grant information.
        """
        if not grant_data:
            return "Nessuna documentazione necessaria specificata."
        
        summary_parts = []
        
        # Title
        if grant_data.get('title'):
            summary_parts.append(f"# {grant_data['title']}")
        else:
            summary_parts.append("# Documentazione Necessaria")
        
        # Overview section - a brief introduction
        if grant_data.get('overview'):
            overview = truncate_text(grant_data['overview'], 500)
            summary_parts.append(f"\n## Panoramica\n{overview}")
        
        # Required Documentation section
        if grant_data.get('documentation'):
            summary_parts.append("\n## Documentazione Richiesta")
            docs = self._select_most_informative_items(grant_data['documentation'])
            for doc in docs:
                summary_parts.append(f"- {doc}")
        
        # Requirements section
        if grant_data.get('requirements'):
            summary_parts.append("\n## Requisiti")
            reqs = self._select_most_informative_items(grant_data['requirements'])
            for req in reqs:
                summary_parts.append(f"- {req}")
        
        # Eligibility section
        if grant_data.get('eligibility'):
            summary_parts.append("\n## Beneficiari Ammissibili")
            eligs = self._select_most_informative_items(grant_data['eligibility'])
            for elig in eligs:
                summary_parts.append(f"- {elig}")
        
        # Funding section
        if grant_data.get('funding'):
            summary_parts.append("\n## Finanziamento")
            funds = self._select_most_informative_items(grant_data['funding'])
            for fund in funds:
                summary_parts.append(f"- {fund}")
        
        # Deadlines section
        if grant_data.get('deadlines'):
            summary_parts.append("\n## Scadenze")
            deadlines = self._select_most_informative_items(grant_data['deadlines'])
            for deadline in deadlines:
                summary_parts.append(f"- {deadline}")
        
        # Important lists section
        if grant_data.get('lists'):
            for title, items in grant_data['lists'].items():
                if len(items) > 1:  # Only include non-trivial lists
                    summary_parts.append(f"\n## {title}")
                    selected_items = self._select_most_informative_items(items, 5)
                    for item in selected_items:
                        summary_parts.append(f"- {item}")
        
        # Other important sections
        if grant_data.get('sections'):
            for title, content in grant_data['sections'].items():
                # Only include non-trivial sections with relevant keywords
                if len(content) > 100 and any(keyword in (title + content).lower() for keyword in 
                                             ['document', 'allegat', 'requisi', 'benefi', 'scad', 'finanz']):
                    summary_parts.append(f"\n## {title}")
                    summary_parts.append(truncate_text(content, 300))
        
        # Sources section
        if grant_data.get('pdf_sources'):
            summary_parts.append("\n## Fonti PDF")
            for pdf in grant_data['pdf_sources']:
                filename = pdf.get('filename', 'PDF')
                context = pdf.get('context', '')
                if context:
                    summary_parts.append(f"- {context} [{filename}]")
                else:
                    summary_parts.append(f"- {filename}")
        
        # Add a timestamp to indicate when the documentation was last updated
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        summary_parts.append(f"\n\n_Ultimo aggiornamento: {timestamp}_")
        
        return "\n".join(summary_parts)