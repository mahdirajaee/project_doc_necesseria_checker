"""
Utility script to update only the update_in_db timestamp for all or specific grants.
"""
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any
from tqdm import tqdm

import config
from db_manager import DatabaseManager
from utils import setup_logging

logger = logging.getLogger(__name__)

def update_timestamps():
    """Updates update_in_db timestamps for grants."""
    parser = argparse.ArgumentParser(description='Grant Timestamp Updater')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--batch-size', type=int, default=0, help='Batch size (0 for all grants)')
    parser.add_argument('--all-grants', action='store_true', help='Update timestamps for all grants')
    parser.add_argument('--grant-id', help='Update timestamp for a specific grant ID')
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    logger.info("Starting timestamp updater")
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        grants_to_update = []
        
        # Get specific grant if ID provided
        if args.grant_id:
            if db_manager.check_grant_exists(args.grant_id):
                grants_to_update = [{"id": args.grant_id}]
                logger.info(f"Will update timestamp for grant {args.grant_id}")
            else:
                logger.error(f"Grant {args.grant_id} does not exist")
                return
        
        # Otherwise get grants based on flag
        elif args.all_grants:
            grants = db_manager.get_all_grants()
            if not grants:
                logger.info("No grants found in the database. Exiting.")
                return
            grants_to_update = grants
            logger.info(f"Found {len(grants_to_update)} total grants to update")
        else:
            grants = db_manager.get_active_grants()
            if not grants:
                logger.info("No active grants found. Exiting.")
                return
            grants_to_update = grants
            logger.info(f"Found {len(grants_to_update)} active grants to update")
        
        # Apply batch size if specified
        if args.batch_size > 0 and args.batch_size < len(grants_to_update):
            grants_to_update = grants_to_update[:args.batch_size]
            logger.info(f"Processing batch of {len(grants_to_update)} grants")
        
        # Get current timestamp in ISO format
        current_time = datetime.now().isoformat()
        
        # Update timestamps directly
        updated_count = 0
        update_errors = 0
        
        for grant in tqdm(grants_to_update, desc="Updating timestamps"):
            try:
                response = db_manager.supabase.table(config.BANDI_TABLE) \
                    .update({
                        "update_in_db": current_time  # Update just the timestamp
                    }) \
                    .eq("id", grant["id"]) \
                    .execute()
                
                if hasattr(response, 'data') and len(response.data) > 0:
                    updated_count += 1
                else:
                    update_errors += 1
                    logger.warning(f"Failed to update timestamp for grant {grant['id']}")
            except Exception as e:
                update_errors += 1
                logger.error(f"Error updating timestamp for grant {grant['id']}: {str(e)}")
        
        logger.info(f"Updated timestamps for {updated_count}/{len(grants_to_update)} grants")
        if update_errors > 0:
            logger.warning(f"Failed to update {update_errors} grants")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        logger.info("Timestamp updater finished")

if __name__ == "__main__":
    update_timestamps()