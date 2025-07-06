"""
Tests for the Stock Update Agent.
"""

import pytest
from unittest.mock import AsyncMock, patch

from agents.stock_update.agent import StockUpdateAgent, ValidateSalesDataTool
from agents.database.models import StockUpdateRequest, SaleData


class TestValidateSalesDataTool:
    """Tests for the sales data validation tool."""
    
    def test_valid_sales_data(self):
        """Test validation of valid sales data."""
        tool = ValidateSalesDataTool()
        sales_data = [
            {"index": 1, "quantity_sold": 5},
            {"index": 2, "quantity_sold": 3}
        ]
        
        result = tool._run(sales_data)
        
        assert result["validation_passed"] is True
        assert len(result["valid_sales"]) == 2
        assert len(result["errors"]) == 0
    
    def test_invalid_sales_data(self):
        """Test validation of invalid sales data."""
        tool = ValidateSalesDataTool()
        sales_data = [
            {"index": 0, "quantity_sold": 5},  # Invalid index
            {"index": 2, "quantity_sold": -3},  # Invalid quantity
            {"index": "invalid", "quantity_sold": 3}  # Invalid type
        ]
        
        result = tool._run(sales_data)
        
        assert result["validation_passed"] is False
        assert len(result["valid_sales"]) == 0
        assert len(result["errors"]) == 3


class TestStockUpdateAgent:
    """Tests for the Stock Update Agent."""
    
    @pytest.fixture
    async def agent(self):
        """Create a test agent instance."""
        agent = StockUpdateAgent()
        await agent.initialize()
        return agent
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization."""
        agent = StockUpdateAgent()
        await agent.initialize()
        
        assert agent.graph is not None
        assert agent.validate_tool is not None
        assert agent.update_tool is not None
    
    @pytest.mark.asyncio
    async def test_process_valid_request(self, agent, sample_sales_data, mock_db_manager):
        """Test processing a valid stock update request."""
        with patch('agents.database.manager.db_manager', mock_db_manager):
            mock_db_manager.update_stock_batch.return_value = 3
            
            request = StockUpdateRequest(sales=sample_sales_data)
            response = await agent.process_stock_update(request)
            
            assert response.status == "completed"
            assert response.rows_affected == 3
            assert "Successfully" in response.message
    
    @pytest.mark.asyncio
    async def test_process_invalid_request(self, agent):
        """Test processing an invalid stock update request."""
        invalid_sales = [
            SaleData(index=0, quantity_sold=5),  # This should fail validation
        ]
        
        request = StockUpdateRequest(sales=invalid_sales)
        response = await agent.process_stock_update(request)
        
        assert response.status == "validation_failed"
        assert "Validation failed" in response.message