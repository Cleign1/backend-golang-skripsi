package config

import (
	"log"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

// Config holds all the configuration for our application.
type Config struct {
	DatabaseURL         string
	BatchSize           int
	CallbackURL         string
	Port                string
	GoogleDriveFolderID string
	GoogleCredentialsPath string
}

// Load loads the configuration from environment variables.
func Load() (*Config, error) {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using OS environment variables.")
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("FATAL: DATABASE_URL environment variable is not set.")
	}

	batchSizeStr := os.Getenv("BATCH_SIZE")
	if batchSizeStr == "" {
		batchSizeStr = "500"
	}
	batchSize, err := strconv.Atoi(batchSizeStr)
	if err != nil {
		log.Fatalf("FATAL: Invalid BATCH_SIZE '%s'. Must be an integer.", batchSizeStr)
	}

	callbackURL := os.Getenv("CALLBACK_URL")
	if callbackURL == "" {
		log.Fatal("FATAL: CALLBACK_URL environment variable is not set.")
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	return &Config{
		DatabaseURL:         dbURL,
		BatchSize:           batchSize,
		CallbackURL:         callbackURL,
		Port:                port,
		GoogleDriveFolderID: os.Getenv("GOOGLE_DRIVE_FOLDER_ID"),
		GoogleCredentialsPath: os.Getenv("GOOGLE_CREDENTIALS_PATH"),
	}, nil
}
