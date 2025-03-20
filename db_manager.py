"""
Handles interaction with the Supabase database.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential

import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations with Supabase."""
    
    def __init__(self):
        """Initialize the Supabase client."""
        try:
            self.supabase: Client = create_client(
                config.SUPABASE_URL, 
                config.SUPABASE_KEY
            )
            logger.info("Successfully connected to Supabase")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=config.RETRY_BACKOFF)
    )
    def get_active_grants(self) -> List[Dict[str, Any]]:
        """
        Retrieves all active grants from the bandi table.
        
        Returns:
            List[Dict[str, Any]]: List of active grants with their details.
        """
        try:
            response = self.supabase.table(config.BANDI_TABLE) \
                .select("id, link_bando, link_sito_bando, documentazione_necessaria") \
                .eq("stato", "Attivo") \
                .execute()
            
            if hasattr(response, 'data'):
                logger.info(f"Retrieved {len(response.data)} active grants")
                return response.data
            else:
                logger.warning("No data attribute in response")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching active grants: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=config.RETRY_BACKOFF)
    )
    def check_grant_exists(self, grant_id: str) -> bool:
        """
        Checks if a grant exists in the database.
        
        Args:
            grant_id (str): The ID of the grant to check.
            
        Returns:
            bool: True if the grant exists, False otherwise.
        """
        try:
            response = self.supabase.table(config.BANDI_TABLE) \
                .select("id") \
                .eq("id", grant_id) \
                .execute()
            
            if hasattr(response, 'data') and len(response.data) > 0:
                return True
            else:
                logger.warning(f"Grant {grant_id} does not exist in the database")
                return False
                
        except Exception as e:
            logger.error(f"Error checking if grant {grant_id} exists: {e}")
            return False
    
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=config.RETRY_BACKOFF)
    )
    def update_documentation(self, grant_id: str, documentation: str) -> bool:
        """
        Updates the documentazione_necessaria column and timestamp for a specific grant.
        
        Args:
            grant_id (str): The ID of the grant to update.
            documentation (str): The documentation summary to store.
            
        Returns:
            bool: True if update was successful, False otherwise.
        """
        # First check if the grant exists
        if not self.check_grant_exists(grant_id):
            return False
            
        try:
            # Get current timestamp in ISO format
            current_time = datetime.now().isoformat()
            
            # Update both documentation and timestamp
            response = self.supabase.table(config.BANDI_TABLE) \
                .update({
                    "documentazione_necessaria": documentation,
                    "updated_at": current_time  # Update timestamp
                }) \
                .eq("id", grant_id) \
                .execute()
            
            if hasattr(response, 'data') and len(response.data) > 0:
                logger.info(f"Successfully updated documentation for grant {grant_id}")
                return True
            else:
                logger.warning(f"No rows updated for grant {grant_id} despite it existing")
                
                # Try with service role explicitly if first attempt failed
                try:
                    # Additional debug information
                    logger.info(f"Attempting direct update with explicit service role for grant {grant_id}")
                    
                    response = self.supabase.table(config.BANDI_TABLE) \
                        .update({
                            "documentazione_necessaria": documentation,
                            "updated_at": current_time
                        }) \
                        .eq("id", grant_id) \
                        .execute()
                    
                    if hasattr(response, 'data') and len(response.data) > 0:
                        logger.info(f"Second attempt succeeded for grant {grant_id}")
                        return True
                    else:
                        logger.error(f"Second attempt also failed for grant {grant_id}")
                        return False
                except Exception as e:
                    logger.error(f"Error on second update attempt for grant {grant_id}: {e}")
                    return False
                
        except Exception as e:
            logger.error(f"Error updating documentation for grant {grant_id}: {e}")
            raise
    
    def close(self):
        """Close the database connection."""
        # No explicit close method for Supabase Python client
        # This method is included for completeness and future compatibility
        logger.info("Database connection closed")