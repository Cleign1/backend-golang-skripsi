package config

import (
	"log"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Config holds all the configuration for our application.
type Config struct {
	DatabaseURL             string
	BatchSize               int
	CallbackURL             string // URL for Go -> Flask final result (Optional)
	Port                    string
	FlaskWebhookURL         string // URL for n8n -> Flask status updates
	N8nPredictionTriggerURL string // URL to trigger n8n prediction workflow

	// Cloudflare R2 / S3-compatible storage
	R2Endpoint        string
	R2AccessKeyID     string
	R2SecretAccessKey string
	R2Bucket          string
	R2PublicBaseURL   string
	R2UsePathStyle    bool
	R2ObjectPrefix    string // e.g., "prediction" so objects go to skripsi/prediction/<file>
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

	// R2 / S3-compatible storage configuration
	r2Endpoint := strings.TrimSpace(os.Getenv("R2_ENDPOINT"))
	r2AK := strings.TrimSpace(os.Getenv("R2_ACCESS_KEY_ID"))
	r2SK := strings.TrimSpace(os.Getenv("R2_SECRET_ACCESS_KEY"))
	r2Bucket := strings.TrimSpace(os.Getenv("R2_BUCKET"))
	r2PublicBaseURL := strings.TrimSpace(os.Getenv("R2_PUBLIC_BASE_URL"))
	r2ObjectPrefix := strings.Trim(strings.TrimSpace(os.Getenv("R2_OBJECT_PREFIX")), "/") // e.g., "prediction"

	usePathStyle := true
	if v := strings.ToLower(strings.TrimSpace(os.Getenv("R2_USE_PATH_STYLE"))); v != "" {
		usePathStyle = v == "1" || v == "true" || v == "yes"
	}

	// Not fatal: allow app to run without uploads if R2 not configured
	if r2Endpoint == "" || r2AK == "" || r2SK == "" || r2Bucket == "" {
		log.Println("WARNING: R2 storage is not fully configured. File uploads will be disabled.")
	} else {
		if r2ObjectPrefix != "" {
			log.Printf("INFO: R2 storage configured for bucket '%s' with prefix '%s' at endpoint '%s'.", r2Bucket, r2ObjectPrefix, r2Endpoint)
		} else {
			log.Printf("INFO: R2 storage configured for bucket '%s' at endpoint '%s'.", r2Bucket, r2Endpoint)
		}
	}

	return &Config{
		DatabaseURL:             dbURL,
		BatchSize:               batchSize,
		CallbackURL:             callbackURL,
		Port:                    port,
		FlaskWebhookURL:         flaskWebhookURL,
		N8nPredictionTriggerURL: n8nPredictionTriggerURL,

		R2Endpoint:        r2Endpoint,
		R2AccessKeyID:     r2AK,
		R2SecretAccessKey: r2SK,
		R2Bucket:          r2Bucket,
		R2PublicBaseURL:   r2PublicBaseURL,
		R2UsePathStyle:    usePathStyle,
		R2ObjectPrefix:    r2ObjectPrefix,
	}, nil
}
