# Go Backend for Stock Prediction

This project is a Go-based backend service that provides stock prediction capabilities. It's designed with a modular architecture to ensure a clean separation of concerns, making it easy to maintain, test, and scale.

## Project Structure

The project follows a modular structure, with each package responsible for a specific part of the application's functionality.

```
.
├── internal/
│   ├── config/
│   │   └── config.go       # Application configuration
│   ├── database/
│   │   └── database.go     # Database connection handling
│   ├── gdrive/
│   │   └── gdrive.go       # Google Drive integration
│   ├── handler/
│   │   └── http.go         # HTTP request handlers
│   ├── models/
│   │   └── models.go       # Data models and structures
│   └── predictor/
│       └── predictor.go    # Core prediction logic
├── .env.example            # Example environment variables
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Dockerfile for the application
├── go.mod                  # Go module definition
├── go.sum                  # Go module checksums
└── main.go                 # Main application entry point
```

### `internal/config`

This package is responsible for loading and managing the application's configuration. It reads environment variables from a `.env` file or the operating system and populates a `Config` struct. This keeps all configuration-related code in one place, making it easy to manage.

### `internal/database`

This package handles the database connection. It provides a function to create a new database connection pool, abstracting the database connection logic from the rest of the application.

### `internal/gdrive`

This package encapsulates all interactions with the Google Drive API. It provides functions for creating a new Google Drive service, testing the connection, and uploading files.

### `internal/handler`

This package contains the HTTP request handlers. It's responsible for parsing incoming requests, calling the appropriate services, and sending responses. This separates the API layer from the business logic.

### `internal/models`

This package defines the data structures used throughout the application. This includes request payloads, database models, and API responses.

### `internal/predictor`

This package contains the core business logic for the stock prediction feature. It's responsible for fetching data, performing calculations, and generating prediction results.

### `main.go`

This is the main entry point of the application. It's responsible for initializing all the components (config, database, etc.), wiring them together, and starting the HTTP server.

## Getting Started

### Prerequisites

- [Go](https://golang.org/)
- [Docker](https://www.docker.com/) (optional)

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/cleign1/backend-golang-skripsi
    cd backend-golang-skripsi
    ```

2.  **Create a `.env` file:**

    Copy the `.env.example` file to a new file named `.env` and fill in the required environment variables.

    ```bash
    cp .env.example .env
    ```

3.  **Run the application:**

    You can run the application using either Go or Docker.

    **Using Go:**

    ```bash
    go run main.go
    ```

    **Using Docker:**

    ```bash
    docker-compose up --build
    ```

## Learning from the Changes

This refactoring to a modular architecture provides several learning opportunities:

-   **Separation of Concerns:** Notice how each package has a single, well-defined responsibility. This is a fundamental principle of good software design that makes code easier to understand and maintain.
-   **Dependency Injection:** The `main.go` file now injects dependencies (like the database connection and Google Drive service) into the components that need them. This makes the components more testable and reusable.
-   **Clearer Code:** By breaking the application into smaller, more focused packages, the code becomes easier to read and reason about.
-   **Scalability:** This modular structure makes it easier to add new features or modify existing ones without affecting other parts of the application.

Feel free to explore the code in each package to see how it all fits together. This is a great way to learn best practices for building robust and maintainable Go applications.
