# Stock Management AI Agents

## Overview
This project features intelligent AI agents built with **LangChain** and **LangGraph** using **Google Gemini LLM** for advanced stock management. The system provides two main AI-powered functionalities: intelligent stock updates and predictive stock analysis.

## 🤖 AI Agents

### 1. Stock Update Agent (LangChain)
- **Technology**: LangChain with Google Gemini Pro
- **Purpose**: Intelligently processes sales data and updates inventory levels
- **Features**:
  - AI-powered data validation and error detection
  - Smart duplicate detection and data quality checks
  - Intelligent error handling with detailed feedback
  - Batch processing with transaction safety

### 2. Stock Prediction Agent (LangGraph)
- **Technology**: LangGraph workflow with Google Gemini Pro  
- **Purpose**: Predicts future stock needs using advanced AI analysis
- **Features**:
  - AI-driven sales pattern analysis
  - Intelligent batch processing with state management
  - Automated report generation and file uploads
  - Smart callback notifications
  - Google Drive integration for report sharing

## 🏗️ Architecture

```
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── src/
│   ├── agents/
│   │   ├── stock_update_agent.py      # LangChain-based stock update agent
│   │   └── stock_prediction_agent.py  # LangGraph-based prediction agent
│   ├── tools/                 # AI agent tools and utilities
│   ├── database/              # Database management utilities
│   └── models/                # Pydantic data models
├── .env.example              # Environment configuration template
└── README.md                 # This file
```

## 🚀 Setup Instructions

### Prerequisites
- Python 3.8 or later
- PostgreSQL database
- Google API key for Gemini LLM
- (Optional) Google Drive service account for file uploads

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd backend-golang-skripsi
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**:
   Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```
   
   Update the following variables:
   ```env
   DATABASE_URL=postgresql://username:password@host:port/database_name
   GOOGLE_API_KEY=your_google_gemini_api_key_here
   BATCH_SIZE=500
   PORT=8080
   CALLBACK_URL=http://your-flask-app.com/callback
   
   # Optional Google Drive integration
   GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
   GOOGLE_CREDENTIALS_PATH=path/to/service-account-key.json
   ```

4. **Database Setup**:
   Ensure your PostgreSQL database has the required tables:
   - `amazon_dataset` - Product catalog with stock levels
   - `daily_sales` - Historical sales data

### Running the Application

**Development Mode**:
```bash
python main.py
```

**Production Mode**:
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

The API will be available at `http://localhost:8080`

## 📡 API Endpoints

### Core Endpoints

#### `POST /update-stock`
Updates stock levels using the AI agent for intelligent processing.

**Request Body**:
```json
[
    {
        "index": 1,
        "quantity_sold": 5
    },
    {
        "index": 2,
        "quantity_sold": 3
    }
]
```

**Response**:
```json
{
    "status": "Process completed successfully",
    "message": "Stok telah berhasil diperbarui."
}
```

#### `POST /predict-stock`
Initiates AI-powered stock prediction analysis with LangGraph workflow.

**Request Body**:
```json
{
    "prediction_date": "2024-01-15",
    "task_id": "task_123"
}
```

**Response**:
```json
{
    "status": "Prediction task accepted and is running in the background with AI workflow.",
    "task_id": "task_123"
}
```

### Utility Endpoints

#### `GET /`
API information and capabilities

#### `GET /health`
Health check for database and AI agents

#### `GET /agents/status`
Status of AI agents and their capabilities

#### `POST /validate-sales-data`
Validate sales data using AI without processing

## 🧠 AI Capabilities

### Stock Update Agent Intelligence
- **Data Validation**: AI automatically detects missing fields, invalid data types, and business rule violations
- **Smart Error Handling**: Provides intelligent, contextual error messages
- **Duplicate Detection**: Identifies and handles duplicate entries intelligently
- **Quality Assurance**: Ensures data integrity before database operations

### Stock Prediction Agent Intelligence  
- **Pattern Recognition**: AI analyzes historical sales patterns to identify trends
- **Demand Forecasting**: Uses machine learning insights to predict future stock needs
- **Risk Assessment**: Identifies products at risk of stockouts
- **Automated Reporting**: Generates comprehensive analysis reports with actionable insights

## 🔧 AI Agent Workflows

### Stock Update Workflow
1. **AI Validation**: Gemini LLM validates incoming sales data
2. **Smart Processing**: AI determines optimal processing strategy
3. **Database Update**: Secure transaction with rollback capability
4. **Intelligent Feedback**: AI-generated status and recommendations

### Stock Prediction Workflow (LangGraph)
1. **Initialization**: Set up prediction parameters and state
2. **Batch Processing**: AI-managed batch fetching with state tracking
3. **AI Analysis**: Gemini LLM analyzes sales patterns for each batch
4. **Pattern Recognition**: Identify trends and predict future demand
5. **Report Generation**: Create comprehensive CSV reports
6. **File Management**: Upload to Google Drive with public sharing
7. **Notification**: Send intelligent callback with results summary

## 🔒 Security & Best Practices

- **Environment Variables**: All sensitive data stored in environment variables
- **Database Transactions**: All updates use transactions with rollback capability
- **API Validation**: Pydantic models ensure data integrity
- **Error Handling**: Comprehensive error handling with logging
- **Rate Limiting**: Built-in protection against abuse

## 🌟 Key Features

- **AI-Powered**: Google Gemini LLM provides intelligent decision making
- **Workflow Automation**: LangGraph manages complex multi-step processes
- **Real-time Processing**: FastAPI provides high-performance async operations
- **Comprehensive Logging**: Detailed logs for monitoring and debugging
- **Scalable Architecture**: Modular design supports easy extension
- **Google Drive Integration**: Automated report sharing and storage
- **Flexible Configuration**: Environment-based configuration management

## 🚀 Advanced Usage

### Custom AI Prompts
The AI agents use sophisticated prompts for:
- Data validation and quality assessment
- Sales pattern analysis and trend detection
- Risk assessment and recommendation generation
- Error analysis and resolution suggestions

### Workflow Customization
The LangGraph prediction workflow can be extended with additional nodes for:
- Custom business rules
- Additional data sources
- Advanced analytics
- Custom notification systems

## 📊 Monitoring & Analytics

### Health Monitoring
- Database connection status
- AI agent initialization status
- Real-time performance metrics

### Logging
- Detailed operation logs
- AI decision tracking
- Performance metrics
- Error analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests and documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.

---

**Powered by LangChain 🦜🔗 + LangGraph 🕸️ + Google Gemini 🤖**