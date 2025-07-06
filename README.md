# backend-golang-skripsi

## Overview
This project is a Go-based server application designed for managing stock updates and predictions. It provides two main endpoints: one for updating stock based on sales data and another for predicting future stock needs based on historical sales data.

## Project Structure
```
backend-golang-skripsi
├── src
│   └── main.go          # Entry point of the Go application
├── Dockerfile           # Dockerfile for building the application image
├── .dockerignore        # Files to ignore when building the Docker image
├── go.mod               # Module dependencies
├── go.sum               # Checksums for module dependencies
├── .env.example         # Example environment variables
└── README.md            # Project documentation
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

#### Locally
1. Install dependencies:
   ```
   go mod tidy
   ```
2. Run the application:
   ```
   go run main.go
   ```

#### Using Docker
1. Build the Docker image:
   ```
   docker build -t stock-management-app .
   ```
2. Run the Docker container:
   ```
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

## License
This project is licensed under the MIT License. See the LICENSE file for details.