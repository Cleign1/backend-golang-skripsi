# backend-golang-skripsi

## Overview
This project provides a comprehensive stock management system with two implementations:

1. **Go Backend** - Original high-performance server with stock update and prediction endpoints
2. **AI Agents** - Intelligent LangChain/LangGraph-based agents that transform the functionality into AI-powered operations

The system manages stock updates and predictions with support for batch processing, asynchronous operations, and Google Drive integration.

## Project Structure
```
backend-golang-skripsi
├── main.go              # Go server entry point
├── main_agents.py       # AI agents server entry point
├── agents/              # AI Agents implementation
│   ├── config/          # Configuration management
│   ├── database/        # Database models and utilities
│   ├── stock_update/    # Stock Update AI Agent
│   ├── stock_prediction/# Stock Prediction AI Agent
│   ├── orchestrator/    # Agent coordinator
│   ├── api/             # FastAPI endpoints
│   ├── utils/           # Utilities (logging, Google Drive)
│   ├── tests/           # Test suite
│   └── README.md        # AI agents documentation
├── examples/            # Usage examples
├── requirements.txt     # Python dependencies for AI agents
├── .env.example         # Go backend environment variables
├── .env.agents.example  # AI agents environment variables
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker compose configuration
├── go.mod               # Go module dependencies
└── README.md            # This file
```

## Setup Instructions

### Prerequisites
- Go (version 1.16 or later)
- Docker (for containerization)
- PostgreSQL (for database)

### Environment Variables
Create a `.env` file in the root directory based on the `.env.example` file. Ensure to set the following variables:
- `DATABASE_URL`: Connection string for the PostgreSQL database.
- `BATCH_SIZE`: Number of products to process in each batch (default is 500).
- `CALLBACK_URL`: URL for the callback after prediction is completed.
- `PORT`: Port on which the server will run (default is 8080).

#### Google AI Studio Configuration (for AI-enhanced features)
- `GOOGLE_API_KEY`: Your Google AI Studio API key for Gemini 2.5 Flash model.
- `GEMINI_MODEL`: The Gemini model to use (default: gemini-2.5-flash).

#### Google Drive Configuration (optional)
- `GOOGLE_DRIVE_FOLDER_ID`: Google Drive folder ID for uploading prediction results.
- `GOOGLE_CREDENTIALS_PATH`: Path to Google Drive service account credentials JSON file.

### Setting up Google AI Studio API Key
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Create a new project or select an existing one
3. Generate an API key
4. Add the API key to your `.env` file as `GOOGLE_API_KEY`

**Note**: The AI features are optional. If `GOOGLE_API_KEY` is not provided, the application will run without AI-enhanced analysis.

### Running the Application
=======
### Running the Go Backend

#### Locally
1. Install dependencies:
   ```bash
   go mod tidy
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```
=======
3. Run the application:
   ```bash
   go run main.go
   ```

#### Using Docker
1. Build the Docker image:
   ```bash
   docker build -t stock-management-app .
   ```
2. Run the Docker container:
   ```bash
   docker run -p 8080:8080 --env-file .env stock-management-app
   ```

## Endpoints
- **POST /update-stock**: Updates stock based on the provided sales data. Now includes AI-powered insights about sales patterns and inventory optimization recommendations.
- **POST /predict-stock**: Initiates a background task to predict stock needs based on historical sales data. Enhanced with AI analysis using Google Gemini 2.5 Flash for improved prediction accuracy and business insights.

## AI Features
This application now includes AI-enhanced capabilities powered by Google Gemini 2.5 Flash:

### Stock Update Agent (AI-Enhanced)
- Analyzes sales patterns in real-time
- Provides insights about customer behavior
- Recommends inventory optimization strategies
- Detects anomalies in sales data

### Stock Prediction Agent (AI-Enhanced)
- Advanced analysis of historical sales trends
- Market trend predictions and risk assessments
- Intelligent recommendations for inventory management
- Actionable business insights for decision making

### Response Format
Both endpoints now return additional `ai_insights` or `ai_analysis` fields containing AI-generated recommendations and analysis.
=======
### Running the AI Agents

#### Prerequisites
- Python 3.8+
- PostgreSQL database
- Optional: OpenAI API key for intelligent features
- Optional: Google Drive credentials for file uploads

#### Installation
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment:
   ```bash
   cp .env.agents.example .env
   # Edit .env with your configuration
   ```

#### Running the AI Agents Server
```bash
# Using the main script
python main_agents.py

# Or directly with uvicorn
uvicorn agents.api.main:app --host 0.0.0.0 --port 8080
```

#### Example Usage
```bash
# Run the comprehensive example
python examples/usage_example.py
```

## Implementations

### 1. Go Backend (Original)
High-performance server with direct database operations:
- **POST /update-stock**: Updates stock based on sales data
- **POST /predict-stock**: Initiates background prediction tasks

### 2. AI Agents (New)
Intelligent agents using LangChain/LangGraph framework:
- **POST /agents/update-stock**: AI-powered stock updates with intelligent validation
- **POST /agents/predict-stock**: AI-powered predictions with advanced forecasting
- **GET /health**: Comprehensive health monitoring
- **GET /agents/status**: Agent status and performance metrics
- **GET /tasks/{task_id}**: Task result tracking

## AI Agents Features

### Stock Update Agent
- **Intelligent Validation**: LLM-powered data validation and anomaly detection
- **Smart Error Handling**: Context-aware error messages and recovery strategies
- **Business Rules**: Configurable validation rules with reasoning
- **Batch Processing**: Efficient handling of large datasets

### Stock Prediction Agent
- **Advanced Forecasting**: LLM-enhanced prediction algorithms
- **Trend Analysis**: Intelligent pattern recognition in sales data
- **Risk Assessment**: AI-powered inventory risk evaluation
- **Asynchronous Processing**: Background task execution with progress tracking

### Agent Orchestrator
- **Unified Management**: Single interface for all agents
- **Health Monitoring**: Comprehensive system health checks
- **Task Tracking**: Complete audit trail of operations
- **Performance Metrics**: Agent performance and error monitoring

## Configuration

### Environment Variables

#### Go Backend (.env)
```env
DATABASE_URL=postgresql://user:password@host:port/database
BATCH_SIZE=500
PORT=8080
CALLBACK_URL=http://your-callback-url
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
GOOGLE_CREDENTIALS_PATH=credentials.json
```

#### AI Agents (.env for agents)
```env
# Database (required)
DATABASE_URL=postgresql://user:password@host:port/database

# Server settings
PORT=8080
BATCH_SIZE=500
CALLBACK_URL=http://your-callback-url

# AI/LLM settings (optional)
OPENAI_API_KEY=your_openai_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
LANGCHAIN_TRACING_V2=true

# Google Drive (optional)
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
GOOGLE_CREDENTIALS_PATH=credentials.json
```

## Testing

### Go Backend
```bash
go test ./...
```

### AI Agents
```bash
pytest agents/tests/
```

## Production Deployment

Both implementations can be deployed using:
- Docker containers
- Kubernetes
- Cloud platforms (AWS, GCP, Azure)

For AI agents, ensure:
- Sufficient memory for LLM operations
- Proper API key management
- Database connection pooling
- Monitoring and logging setup

## Documentation

- [AI Agents Documentation](agents/README.md) - Detailed AI agents documentation
- [GCP Setup Guide](GCP_SETUP.md) - Google Drive integration setup
- [API Examples](examples/) - Usage examples and client code

## License
This project is licensed under the MIT License. See the LICENSE file for details.