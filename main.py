"""
Main entry point for the grant documentation crawler.
Orchestrates the entire process of updating grant information in Supabase.
"""
import logging
import time
import argparse
import os
from typing import Dict, List, Any
import concurrent.futures
from tqdm import tqdm

import config
from db_manager import DatabaseManager
from web_scraper import WebScraper
from pdf_processor import PDFProcessor
from documentation_analyzer import DocumentationAnalyzer
from utils import setup_logging, is_valid_url

logger = logging.getLogger(__name__)

def process_grant(grant: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes a single grant to extract and update its documentation.
    Thoroughly analyzes all available information from websites and PDFs.
    
    Args:
        grant (Dict[str, Any]): The grant details from the database.
        
    Returns:
        Dict[str, Any]: The grant with updated documentation.
    """
    grant_id = grant.get('id')
    link_bando = grant.get('link_bando')
    link_sito_bando = grant.get('link_sito_bando')
    
    logger.info(f"Processing grant {grant_id}")
    
    # Initialize components
    web_scraper = WebScraper()
    pdf_processor = PDFProcessor()
    doc_analyzer = DocumentationAnalyzer()
    
    web_data = []
    pdf_data = []
    
    # Process main grant webpage
    if link_bando and is_valid_url(link_bando):
        html_content = web_scraper.get_page_content(link_bando)
        
        if html_content:
            # Extract comprehensive information from the webpage
            web_info = web_scraper.extract_grant_information(html_content, link_bando)
            if web_info:
                web_data.append(web_info)
            
            # Extract PDF links
            pdf_links = web_scraper.extract_pdf_links(html_content, link_bando)
            
            # Process priority PDFs first
            for pdf_info in pdf_links:
                if pdf_info.get('priority', False):
                    pdf_result = pdf_processor.process_pdf(pdf_info)
                    if pdf_result and not pdf_result.get('error'):
                        pdf_data.append(pdf_result)
            
            # Check if we need to process non-priority PDFs
            need_more_pdfs = len(pdf_data) == 0 or len(' '.join(str(d) for d in pdf_data)) < 5000
            
            if need_more_pdfs:
                # Process non-priority PDFs
                for pdf_info in pdf_links:
                    if not pdf_info.get('priority', False):
                        pdf_result = pdf_processor.process_pdf(pdf_info)
                        if pdf_result and not pdf_result.get('error'):
                            pdf_data.append(pdf_result)
                            
                            # Stop after processing a few non-priority PDFs
                            if len(pdf_data) >= 5:
                                break
    
    # Process supplementary site if different
    if link_sito_bando and is_valid_url(link_sito_bando) and link_sito_bando != link_bando:
        html_content = web_scraper.get_page_content(link_sito_bando)
        
        if html_content:
            # Extract comprehensive information from the webpage
            web_info = web_scraper.extract_grant_information(html_content, link_sito_bando)
            if web_info:
                web_data.append(web_info)
            
            # Extract PDF links
            pdf_links = web_scraper.extract_pdf_links(html_content, link_sito_bando)
            
            # Process priority PDFs first
            priority_pdfs_processed = 0
            for pdf_info in pdf_links:
                if pdf_info.get('priority', False):
                    pdf_result = pdf_processor.process_pdf(pdf_info)
                    if pdf_result and not pdf_result.get('error'):
                        pdf_data.append(pdf_result)
                        priority_pdfs_processed += 1
                        
                        # Limit priority PDFs to a reasonable number
                        if priority_pdfs_processed >= 3:
                            break
            
            # Check if we need to process non-priority PDFs
            need_more_pdfs = len(pdf_data) == 0 or len(' '.join(str(d) for d in pdf_data)) < 5000
            
            if need_more_pdfs:
                # Process non-priority PDFs
                non_priority_pdfs_processed = 0
                for pdf_info in pdf_links:
                    if not pdf_info.get('priority', False):
                        pdf_result = pdf_processor.process_pdf(pdf_info)
                        if pdf_result and not pdf_result.get('error'):
                            pdf_data.append(pdf_result)
                            non_priority_pdfs_processed += 1
                            
                            # Limit non-priority PDFs to a reasonable number
                            if non_priority_pdfs_processed >= 3:
                                break
    
    # Clean up resources
    web_scraper.close()
    pdf_processor.close()
    
    # Merge and analyze all data
    merged_data = doc_analyzer.merge_grant_data(web_data, pdf_data)
    
    # Generate comprehensive summary
    documentation_summary = doc_analyzer.generate_summary(merged_data)
    
    # Update the grant with the new documentation
    grant['documentation_summary'] = documentation_summary
    
    logger.info(f"Completed processing for grant {grant_id}: {len(web_data)} webpage sources, {len(pdf_data)} PDF sources")
    return grant

def main():
    """Main entry point for the crawler."""
    parser = argparse.ArgumentParser(description='Grant Documentation Crawler')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    parser.add_argument('--batch-size', type=int, default=0, help='Batch size (0 for all grants)')
    parser.add_argument('--verify-only', action='store_true', help='Only verify grant IDs exist without updating')
    parser.add_argument('--all-grants', action='store_true', help='Process all grants regardless of status')
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    logger.info("Starting grant documentation crawler")
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Get grants (either active only or all based on the flag)
        if args.all_grants:
            grants = db_manager.get_all_grants()
            if not grants:
                logger.info("No grants found in the database. Exiting.")
                return
            logger.info(f"Found {len(grants)} total grants to process")
        else:
            grants = db_manager.get_active_grants()
            if not grants:
                logger.info("No active grants found. Exiting.")
                return
            logger.info(f"Found {len(grants)} active grants to process")
        
        # Apply batch size if specified
        if args.batch_size > 0 and args.batch_size < len(grants):
            grants = grants[:args.batch_size]
            logger.info(f"Processing batch of {len(grants)} grants")
        
        # Verify grants exist first if requested
        if args.verify_only:
            existing_grants = 0
            for grant in tqdm(grants, desc="Verifying grants"):
                if db_manager.check_grant_exists(grant['id']):
                    existing_grants += 1
            
            logger.info(f"Verified {existing_grants}/{len(grants)} grants exist in the database")
            return

        # Process grants in parallel
        processed_grants = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all grants for processing
            future_to_grant = {executor.submit(process_grant, grant): grant for grant in grants}
            
            # Process results as they complete
            for future in tqdm(concurrent.futures.as_completed(future_to_grant), total=len(grants), desc="Processing grants"):
                grant = future_to_grant[future]
                try:
                    processed_grant = future.result()
                    processed_grants.append(processed_grant)
                except Exception as e:
                    logger.error(f"Error processing grant {grant.get('id')}: {str(e)}")
        
        logger.info(f"Successfully processed {len(processed_grants)} grants")
        
        # Update the database with the new documentation
        updated_count = 0
        update_errors = 0
        for grant in tqdm(processed_grants, desc="Updating database"):
            try:
                if db_manager.update_documentation(grant['id'], grant['documentation_summary']):
                    updated_count += 1
                else:
                    update_errors += 1
            except Exception as e:
                logger.error(f"Error updating grant {grant.get('id')}: {str(e)}")
                update_errors += 1
        
        logger.info(f"Updated documentation for {updated_count} grants in the database")
        if update_errors > 0:
            logger.warning(f"Failed to update {update_errors} grants")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        logger.info("Grant documentation crawler finished")

if __name__ == "__main__":
    main()