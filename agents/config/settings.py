"""
Configuration settings for the AI agents system.

This module handles all configuration management including database connections,
external services, and agent-specific settings.
"""

import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(..., env="DATABASE_URL", description="PostgreSQL connection URL")
    
    class Config:
        env_prefix = "DATABASE_"


class GoogleDriveSettings(BaseSettings):
    """Google Drive integration settings."""
    
    folder_id: Optional[str] = Field(None, env="GOOGLE_DRIVE_FOLDER_ID", description="Google Drive folder ID")
    credentials_path: Optional[str] = Field(None, env="GOOGLE_CREDENTIALS_PATH", description="Path to Google credentials JSON file")
    
    class Config:
        env_prefix = "GOOGLE_"


class ServerSettings(BaseSettings):
    """Server configuration settings."""
    
    port: int = Field(8080, env="PORT", description="Server port")
    batch_size: int = Field(500, env="BATCH_SIZE", description="Batch size for processing")
    callback_url: Optional[str] = Field(None, env="CALLBACK_URL", description="Callback URL for async results")
    
    class Config:
        env_prefix = "SERVER_"


class AgentSettings(BaseSettings):
    """AI Agent specific settings."""
    
    # LangChain/LangGraph settings
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY", description="OpenAI API key for LLM")
    langchain_api_key: Optional[str] = Field(None, env="LANGCHAIN_API_KEY", description="LangChain API key")
    langchain_tracing_v2: bool = Field(False, env="LANGCHAIN_TRACING_V2", description="Enable LangChain tracing")
    
    # Agent behavior settings
    max_retries: int = Field(3, env="AGENT_MAX_RETRIES", description="Maximum retries for agent operations")
    timeout: int = Field(300, env="AGENT_TIMEOUT", description="Timeout in seconds for agent operations")
    
    class Config:
        env_prefix = "AGENT_"


class Settings:
    """Main settings class that combines all configuration sections."""
    
    def __init__(self):
        self.database = DatabaseSettings()
        self.google_drive = GoogleDriveSettings()
        self.server = ServerSettings()
        self.agents = AgentSettings()
    
    def validate(self) -> bool:
        """Validate all required settings are present."""
        if not self.database.url:
            raise ValueError("DATABASE_URL is required")
        
        return True


# Global settings instance
settings = Settings()