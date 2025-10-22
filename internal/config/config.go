package config

import (
	"log"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

// Config holds all the configuration for our application.
type Config struct {
	DatabaseURL           string
	BatchSize             int
	CallbackURL           string // URL for Go -> Flask final result (Optional)
	Port                  string
	GoogleDriveFolderID   string
	GoogleCredentialsPath string
	FlaskWebhookURL       string // URL for n8n -> Flask status updates
	N8nPredictionTriggerURL string // New: URL to trigger n8n prediction workflow
}

// Load loads the configuration from environment variables.
func Load() (*Config, error) {
	// Attempt to load .env file, but don't fail if it doesn't exist
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found or error loading it, using OS environment variables.")
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("FATAL: DATABASE_URL environment variable is not set.")
	}

	batchSizeStr := os.Getenv("BATCH_SIZE")
	if batchSizeStr == "" {
		batchSizeStr = "500" // Default batch size
	}
	batchSize, err := strconv.Atoi(batchSizeStr)
	if err != nil {
		log.Fatalf("FATAL: Invalid BATCH_SIZE '%s'. Must be an integer.", batchSizeStr)
	}

	// Optional URL for Go app to send final result directly to Flask
	callbackURL := os.Getenv("CALLBACK_URL")
	if callbackURL != "" {
		log.Printf("INFO: Final Go result callback URL set to: %s", callbackURL)
	} else {
		log.Println("INFO: CALLBACK_URL not set. Go backend will not send a final result directly to Flask.")
	}


	port := os.Getenv("PORT")
	if port == "" {
		port = "8080" // Default port
	}

	// URL for n8n to send status updates back to Flask
	flaskWebhookURL := os.Getenv("FLASK_WEBHOOK_URL")
	if flaskWebhookURL == "" {
		log.Fatal("FATAL: FLASK_WEBHOOK_URL environment variable is not set (needed for n8n).")
	}

	// URL to trigger the n8n prediction workflow
	n8nPredictionTriggerURL := os.Getenv("N8N_PREDICTION_TRIGGER_URL")
	if n8nPredictionTriggerURL == "" {
		log.Fatal("FATAL: N8N_PREDICTION_TRIGGER_URL environment variable is not set.")
	}

	googleDriveFolderID := os.Getenv("GOOGLE_DRIVE_FOLDER_ID")
	googleCredentialsPath := os.Getenv("GOOGLE_CREDENTIALS_PATH")


	return &Config{
		DatabaseURL:           dbURL,
		BatchSize:             batchSize,
		CallbackURL:           callbackURL,
		Port:                  port,
		GoogleDriveFolderID:   googleDriveFolderID,
		GoogleCredentialsPath: googleCredentialsPath,
		FlaskWebhookURL:       flaskWebhookURL,       // Keep for n8n
		N8nPredictionTriggerURL: n8nPredictionTriggerURL, // New URL to trigger n8n
	}, nil
}