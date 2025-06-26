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

### Running the Application

#### Locally
1. Install dependencies:
   ```
   go mod tidy
   ```
2. Run the application:
   ```
   go run src/main.go
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
- **POST /update-stock**: Updates stock based on the provided sales data.
- **POST /predict-stock**: Initiates a background task to predict stock needs based on historical sales data.

## License
This project is licensed under the MIT License. See the LICENSE file for details.