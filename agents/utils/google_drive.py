"""
Google Drive integration utilities for the AI agents system.

This module provides functionality for uploading files to Google Drive,
maintaining compatibility with the existing Go backend integration.
"""

import os
import logging
from typing import Optional, Tuple
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from agents.config.settings import settings

logger = logging.getLogger(__name__)


class GoogleDriveManager:
    """Manages Google Drive operations for file uploads."""
    
    def __init__(self):
        self.service = None
        self.folder_id = settings.google_drive.folder_id
        self.credentials_path = settings.google_drive.credentials_path
    
    async def initialize(self) -> bool:
        """
        Initialize Google Drive service.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if not self.credentials_path:
            logger.warning("Google Drive credentials path not set. Upload functionality disabled.")
            return False
        
        if not os.path.exists(self.credentials_path):
            logger.warning(f"Google Drive credentials file not found at {self.credentials_path}")
            return False
        
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            
            # Test connection
            if await self.test_connection():
                logger.info("Google Drive service initialized successfully")
                return True
            else:
                logger.error("Google Drive connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test Google Drive connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.service:
            return False
        
        try:
            if self.folder_id:
                # Test by getting folder information
                folder = self.service.files().get(
                    fileId=self.folder_id,
                    fields='id,name'
                ).execute()
                logger.info(f"Successfully verified access to Google Drive folder: {folder.get('name')}")
            else:
                # Test by listing files (limited to verify access)
                self.service.files().list(pageSize=1).execute()
                logger.info("Successfully verified Google Drive access (using root folder)")
            
            return True
            
        except HttpError as e:
            logger.error(f"Google Drive connection test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Google Drive connection test: {e}")
            return False
    
    async def upload_file(self, file_path: str, file_name: str) -> Tuple[bool, Optional[str]]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Local path to the file to upload
            file_name: Name to give the file in Google Drive
            
        Returns:
            Tuple of (success: bool, public_url: Optional[str])
        """
        if not self.service:
            logger.error("Google Drive service not initialized")
            return False, None
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False, None
        
        try:
            # Create file metadata
            file_metadata = {
                'name': file_name
            }
            
            # Add parent folder if specified
            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]
            
            # Create media upload object
            media = MediaFileUpload(file_path, resumable=True)
            
            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"Successfully uploaded file {file_name} with ID: {file_id}")
            
            # Make file publicly readable
            public_url = await self.make_file_public(file_id)
            
            return True, public_url
            
        except HttpError as e:
            logger.error(f"HTTP error during file upload: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {e}")
            return False, None
    
    async def make_file_public(self, file_id: str) -> Optional[str]:
        """
        Make a file publicly readable and return its public URL.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Public URL if successful, None otherwise
        """
        try:
            # Create permission for public access
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            
            # Generate public URL
            public_url = f"https://drive.google.com/file/d/{file_id}/view"
            logger.info(f"File made public with URL: {public_url}")
            
            return public_url
            
        except HttpError as e:
            logger.error(f"Failed to make file public: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error making file public: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Google Drive service is available."""
        return self.service is not None


# Global Google Drive manager instance
drive_manager = GoogleDriveManager()