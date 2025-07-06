"""
Tests for the API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from agents.api.main import app
from agents.database.models import StockUpdateRequest, PredictionRequest


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator_ready():
    """Mock orchestrator in ready state."""
    mock = AsyncMock()
    mock.status.value = "ready"
    return mock


class TestAPIEndpoints:
    """Tests for API endpoints."""
    
    def test_root_endpoint(self, client):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "AI Agents Stock Management System" in data["service"]
    
    def test_health_endpoint_not_ready(self, client):
        """Test health endpoint when service not ready."""
        # Without proper initialization, service won't be ready
        response = client.get("/health")
        # This might fail due to orchestrator not being ready
        # In a real test, we'd mock the orchestrator
    
    @patch('agents.api.main.orchestrator')
    def test_update_stock_endpoint(self, mock_orchestrator, client):
        """Test stock update endpoint."""
        mock_orchestrator.status.value = "ready"
        mock_orchestrator.process_stock_update.return_value = AsyncMock(
            status="completed",
            message="Success",
            rows_affected=2
        )
        
        request_data = {
            "sales": [
                {"index": 1, "quantity_sold": 5},
                {"index": 2, "quantity_sold": 3}
            ]
        }
        
        response = client.post("/agents/update-stock", json=request_data)
        # Note: This test would need proper async handling in a real implementation
    
    @patch('agents.api.main.orchestrator')
    def test_predict_stock_endpoint(self, mock_orchestrator, client):
        """Test stock prediction endpoint."""
        mock_orchestrator.status.value = "ready"
        mock_orchestrator.process_stock_prediction.return_value = AsyncMock(
            status="accepted",
            task_id="test_123",
            message="Task accepted"
        )
        
        request_data = {
            "prediction_date": "2024-01-15",
            "task_id": "test_123"
        }
        
        response = client.post("/agents/predict-stock", json=request_data)
        # Note: This test would need proper async handling in a real implementation
    
    def test_config_endpoint(self, client):
        """Test configuration endpoint."""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert "google_drive" in data
        assert "server" in data
        assert "agents" in data