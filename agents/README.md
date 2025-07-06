# AI Agents Stock Management System

This directory contains the AI agents implementation using LangChain/LangGraph framework, transforming the existing Go backend functionality into intelligent agents.

## Architecture

The system consists of:

### 1. **Stock Update Agent** (`agents/stock_update/`)
- Transforms the `/update-stock` endpoint into an intelligent AI agent
- Processes sales data with intelligent validation and error handling
- Uses LangGraph workflow for decision making
- Supports batch processing and real-time updates
- Includes LLM-powered analysis when configured

### 2. **Stock Prediction Agent** (`agents/stock_prediction/`)
- Transforms the `/predict-stock` endpoint into an AI agent
- Analyzes historical sales data for future stock predictions
- Uses intelligent forecasting algorithms with LLM insights
- Supports asynchronous processing and batch analysis
- Generates CSV reports and uploads to Google Drive
- Sends results to callback URLs

### 3. **Agent Orchestrator** (`agents/orchestrator/`)
- Unified coordinator managing both agents
- Handles initialization, health checks, and monitoring
- Provides task history and status tracking
- Manages database connections and external services

### 4. **API Layer** (`agents/api/`)
- FastAPI-based RESTful endpoints
- Compatible with existing Go backend endpoints
- Comprehensive health checking and status monitoring
- Error handling and validation

### 5. **Configuration Management** (`agents/config/`)
- Environment-based configuration using Pydantic
- Database connection settings
- Google Drive integration settings
- Agent behavior configuration
- LangChain/LangGraph settings

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   Create a `.env` file with the following variables:
   ```env
   # Database (required)
   DATABASE_URL=postgresql://user:password@host:port/database
   
   # Server settings
   PORT=8080
   BATCH_SIZE=500
   CALLBACK_URL=http://your-callback-url/endpoint
   
   # Google Drive (optional)
   GOOGLE_DRIVE_FOLDER_ID=your_folder_id
   GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
   
   # AI/LLM settings (optional)
   OPENAI_API_KEY=your_openai_api_key
   LANGCHAIN_API_KEY=your_langchain_api_key
   LANGCHAIN_TRACING_V2=true
   
   # Agent behavior
   AGENT_MAX_RETRIES=3
   AGENT_TIMEOUT=300
   ```

## Usage

### Starting the AI Agents Server

```bash
# Using the main script
python main_agents.py

# Or directly with uvicorn
uvicorn agents.api.main:app --host 0.0.0.0 --port 8080
```

### API Endpoints

The AI agents provide the same endpoints as the original Go backend:

#### Stock Update Agent
```bash
POST /agents/update-stock
Content-Type: application/json

{
  "sales": [
    {"index": 1, "quantity_sold": 5},
    {"index": 2, "quantity_sold": 3}
  ]
}
```

#### Stock Prediction Agent
```bash
POST /agents/predict-stock
Content-Type: application/json

{
  "prediction_date": "2024-01-15",
  "task_id": "pred_123"
}
```

#### Additional Endpoints
- `GET /health` - Comprehensive health check
- `GET /status` - Service status
- `GET /agents/status` - All agents status
- `GET /tasks` - Task history
- `GET /tasks/{task_id}` - Specific task result

## Features

### Intelligent Decision Making
- **LLM-powered analysis** when OpenAI API key is configured
- **Validation with business rules** for data integrity
- **Pattern recognition** for anomaly detection
- **Risk assessment** for inventory management

### Compatibility
- **Database schema** - Uses existing PostgreSQL tables
- **Google Drive integration** - Maintains file upload functionality
- **Callback system** - Sends results to configured URLs
- **Batch processing** - Handles large datasets efficiently

### Monitoring and Observability
- **Comprehensive logging** with task tracking
- **Health checks** for all components
- **Task history** and status monitoring
- **Agent performance metrics**
- **LangChain tracing** support (optional)

### Error Handling
- **Graceful degradation** when LLM services are unavailable
- **Automatic retries** with exponential backoff
- **Detailed error reporting** and logging
- **Transaction rollback** for database operations

## Architecture Benefits

1. **Intelligent Processing**: AI agents can make smart decisions about data validation, anomaly detection, and prediction accuracy
2. **Scalability**: Asynchronous processing and batch operations handle large datasets
3. **Observability**: Comprehensive monitoring and logging for production environments
4. **Flexibility**: Configuration-driven behavior allows adaptation to different environments
5. **Compatibility**: Maintains full compatibility with existing database schema and integrations

## Development

### Running Tests
```bash
# Install development dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest agents/tests/
```

### Adding New Agents
1. Create agent directory under `agents/`
2. Implement agent using LangGraph workflows
3. Register agent in orchestrator
4. Add API endpoints
5. Update documentation

## Production Deployment

1. **Environment Setup**: Configure all required environment variables
2. **Database**: Ensure PostgreSQL is accessible and properly configured
3. **Google Drive**: Set up service account and folder permissions (optional)
4. **LLM Services**: Configure OpenAI API key for intelligent features (optional)
5. **Monitoring**: Set up logging aggregation and monitoring
6. **Load Balancing**: Use reverse proxy for production traffic

## Troubleshooting

### Common Issues

1. **Database Connection**: Verify DATABASE_URL and network connectivity
2. **Google Drive**: Check credentials file path and folder permissions
3. **LLM Services**: Verify API keys and service availability
4. **Memory Usage**: Monitor memory usage for large batch operations

### Logs

All agents use structured logging with task IDs for traceability:
```
2024-01-15 10:30:15 - agents.StockUpdateAgent - INFO - [StockUpdateAgent] Task update_20240115_103015: Validation completed: 100 valid records, 0 errors
```

## Contributing

1. Follow the existing code structure and patterns
2. Add comprehensive tests for new functionality
3. Update documentation for new features
4. Ensure compatibility with existing database schema
5. Maintain error handling and logging standards