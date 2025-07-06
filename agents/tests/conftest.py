"""
Test configuration and fixtures for AI agents tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from agents.database.manager import DatabaseManager
from agents.database.models import SaleData, Product, PredictionRequest
from agents.orchestrator.coordinator import AgentOrchestrator


@pytest.fixture
def sample_sales_data():
    """Sample sales data for testing."""
    return [
        SaleData(index=1, quantity_sold=5),
        SaleData(index=2, quantity_sold=3),
        SaleData(index=3, quantity_sold=10)
    ]


@pytest.fixture
def sample_products():
    """Sample products for testing."""
    return [
        Product(index=1, name="Product A", current_stock=100),
        Product(index=2, name="Product B", current_stock=50),
        Product(index=3, name="Product C", current_stock=25)
    ]


@pytest.fixture
def sample_prediction_request():
    """Sample prediction request for testing."""
    return PredictionRequest(
        prediction_date="2024-01-15",
        task_id="test_task_123"
    )


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing."""
    mock = AsyncMock(spec=DatabaseManager)
    mock.initialize.return_value = True
    mock.health_check.return_value = True
    mock.fetch_products_batch.return_value = []
    mock.fetch_sales_data_for_products.return_value = {}
    mock.update_stock_batch.return_value = 3
    return mock


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for testing."""
    mock = AsyncMock(spec=AgentOrchestrator)
    mock.initialize.return_value = True
    mock.status.value = "ready"
    return mock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()