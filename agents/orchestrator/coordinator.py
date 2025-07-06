"""
Agent Orchestrator for managing Stock Update and Stock Prediction agents.

This module provides a unified coordinator that manages both agents,
handles initialization, health checks, and provides a single interface
for agent operations.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from agents.database.models import (
    StockUpdateRequest, StockUpdateResponse,
    PredictionRequest, PredictionResponse,
    AgentStatus, TaskResult
)
from agents.database.manager import db_manager
from agents.utils.google_drive import drive_manager
from agents.utils.logging import AgentLogger, setup_logging
from agents.stock_update.agent import stock_update_agent
from agents.stock_prediction.agent import stock_prediction_agent
from agents.config.settings import settings


class AgentType(Enum):
    """Enumeration of available agent types."""
    STOCK_UPDATE = "stock_update"
    STOCK_PREDICTION = "stock_prediction"


class OrchestatorStatus(Enum):
    """Enumeration of orchestrator status."""
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


class AgentOrchestrator:
    """
    Unified Agent Orchestrator for Stock Management System.
    
    This orchestrator manages both Stock Update and Stock Prediction agents,
    providing a single interface for agent operations, initialization,
    health checks, and monitoring.
    """
    
    def __init__(self):
        self.logger = AgentLogger("AgentOrchestrator")
        self.status = OrchestatorStatus.INITIALIZING
        self.initialized_at: Optional[datetime] = None
        self.agents_status: Dict[str, AgentStatus] = {}
        self.task_history: Dict[str, TaskResult] = {}
        
    async def initialize(self) -> bool:
        """
        Initialize the orchestrator and all managed agents.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing Agent Orchestrator")
            
            # Setup logging
            setup_logging(level="INFO")
            
            # Validate settings
            settings.validate()
            self.logger.info("Configuration validated successfully")
            
            # Initialize database connection
            await db_manager.initialize()
            self.logger.info("Database connection initialized")
            
            # Test database health
            if not await db_manager.health_check():
                raise Exception("Database health check failed")
            
            # Initialize Google Drive (optional)
            drive_available = await drive_manager.initialize()
            if drive_available:
                self.logger.info("Google Drive integration enabled")
            else:
                self.logger.warning("Google Drive integration disabled")
            
            # Initialize Stock Update Agent
            await stock_update_agent.initialize()
            self._update_agent_status(AgentType.STOCK_UPDATE, "ready")
            self.logger.info("Stock Update Agent initialized")
            
            # Initialize Stock Prediction Agent
            await stock_prediction_agent.initialize()
            self._update_agent_status(AgentType.STOCK_PREDICTION, "ready")
            self.logger.info("Stock Prediction Agent initialized")
            
            # Mark orchestrator as ready
            self.status = OrchestatorStatus.READY
            self.initialized_at = datetime.now()
            self.logger.info("Agent Orchestrator initialization completed successfully")
            
            return True
            
        except Exception as e:
            self.status = OrchestatorStatus.ERROR
            self.logger.error(f"Agent Orchestrator initialization failed: {e}", exc_info=True)
            return False
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator and all agents."""
        try:
            self.logger.info("Shutting down Agent Orchestrator")
            self.status = OrchestatorStatus.SHUTTING_DOWN
            
            # Close database connections
            await db_manager.close()
            self.logger.info("Database connections closed")
            
            # Update agent statuses
            for agent_type in AgentType:
                self._update_agent_status(agent_type, "shutdown")
            
            self.logger.info("Agent Orchestrator shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    async def process_stock_update(self, request: StockUpdateRequest) -> StockUpdateResponse:
        """
        Process a stock update request through the Stock Update Agent.
        
        Args:
            request: Stock update request
            
        Returns:
            Stock update response
        """
        if self.status != OrchestatorStatus.READY:
            return StockUpdateResponse(
                status="error",
                message="Orchestrator not ready"
            )
        
        task_id = f"update_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        try:
            self.logger.info(f"Processing stock update request: {task_id}")
            
            # Record task start
            task_result = TaskResult(
                task_id=task_id,
                agent_name=AgentType.STOCK_UPDATE.value,
                status="running",
                started_at=datetime.now()
            )
            self.task_history[task_id] = task_result
            
            # Process through Stock Update Agent
            response = await stock_update_agent.process_stock_update(request)
            
            # Update task result
            task_result.status = response.status
            task_result.completed_at = datetime.now()
            task_result.duration_seconds = (task_result.completed_at - task_result.started_at).total_seconds()
            task_result.result = {
                "rows_affected": response.rows_affected,
                "message": response.message
            }
            
            # Update agent statistics
            agent_status = self.agents_status[AgentType.STOCK_UPDATE.value]
            agent_status.tasks_processed += 1
            agent_status.last_activity = datetime.now()
            
            if response.status == "error":
                agent_status.errors_count += 1
                task_result.error = response.message
            
            self.logger.info(f"Stock update completed: {response.status}")
            return response
            
        except Exception as e:
            self.logger.error(f"Stock update processing failed: {e}", exc_info=True)
            
            # Update error statistics
            if AgentType.STOCK_UPDATE.value in self.agents_status:
                self.agents_status[AgentType.STOCK_UPDATE.value].errors_count += 1
            
            # Update task result
            if task_id in self.task_history:
                self.task_history[task_id].status = "error"
                self.task_history[task_id].error = str(e)
                self.task_history[task_id].completed_at = datetime.now()
            
            return StockUpdateResponse(
                status="error",
                message=f"Processing failed: {str(e)}"
            )
    
    async def process_stock_prediction(self, request: PredictionRequest) -> PredictionResponse:
        """
        Process a stock prediction request through the Stock Prediction Agent.
        
        Args:
            request: Stock prediction request
            
        Returns:
            Prediction response
        """
        if self.status != OrchestatorStatus.READY:
            return PredictionResponse(
                status="error",
                task_id=request.task_id,
                message="Orchestrator not ready"
            )
        
        try:
            self.logger.info(f"Processing stock prediction request: {request.task_id}")
            
            # Record task start
            task_result = TaskResult(
                task_id=request.task_id,
                agent_name=AgentType.STOCK_PREDICTION.value,
                status="running",
                started_at=datetime.now()
            )
            self.task_history[request.task_id] = task_result
            
            # Process through Stock Prediction Agent
            response = await stock_prediction_agent.process_prediction_request(request)
            
            # Update agent statistics
            agent_status = self.agents_status[AgentType.STOCK_PREDICTION.value]
            agent_status.tasks_processed += 1
            agent_status.last_activity = datetime.now()
            
            # Note: For async prediction tasks, the task result will be updated
            # when the background workflow completes
            
            self.logger.info(f"Stock prediction accepted: {request.task_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Stock prediction processing failed: {e}", exc_info=True)
            
            # Update error statistics
            if AgentType.STOCK_PREDICTION.value in self.agents_status:
                self.agents_status[AgentType.STOCK_PREDICTION.value].errors_count += 1
            
            # Update task result
            if request.task_id in self.task_history:
                self.task_history[request.task_id].status = "error"
                self.task_history[request.task_id].error = str(e)
                self.task_history[request.task_id].completed_at = datetime.now()
            
            return PredictionResponse(
                status="error",
                task_id=request.task_id,
                message=f"Processing failed: {str(e)}"
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of the orchestrator and all agents.
        
        Returns:
            Health check results
        """
        health_status = {
            "orchestrator": {
                "status": self.status.value,
                "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
                "uptime_seconds": (datetime.now() - self.initialized_at).total_seconds() if self.initialized_at else 0
            },
            "database": {
                "healthy": await db_manager.health_check()
            },
            "google_drive": {
                "available": drive_manager.is_available()
            },
            "agents": dict(self.agents_status),
            "tasks": {
                "total_processed": len(self.task_history),
                "recent_tasks": list(self.task_history.keys())[-10:]  # Last 10 tasks
            }
        }
        
        return health_status
    
    def get_agent_status(self, agent_type: AgentType) -> Optional[AgentStatus]:
        """
        Get status of a specific agent.
        
        Args:
            agent_type: Type of agent to check
            
        Returns:
            Agent status or None if agent not found
        """
        return self.agents_status.get(agent_type.value)
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get result of a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task result or None if task not found
        """
        return self.task_history.get(task_id)
    
    def get_task_history(self, limit: int = 100) -> Dict[str, TaskResult]:
        """
        Get recent task history.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            Dictionary of recent tasks
        """
        tasks = list(self.task_history.items())
        recent_tasks = tasks[-limit:] if len(tasks) > limit else tasks
        return dict(recent_tasks)
    
    def _update_agent_status(self, agent_type: AgentType, status: str) -> None:
        """Update the status of an agent."""
        agent_name = agent_type.value
        
        if agent_name not in self.agents_status:
            self.agents_status[agent_name] = AgentStatus(
                agent_name=agent_name,
                status=status,
                last_activity=datetime.now(),
                tasks_processed=0,
                errors_count=0
            )
        else:
            self.agents_status[agent_name].status = status
            self.agents_status[agent_name].last_activity = datetime.now()


# Global orchestrator instance
orchestrator = AgentOrchestrator()