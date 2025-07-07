package main

import (
	"context"
	"log"
	"net/http"

	"backend-golang-skripsi/internal/config"
	"backend-golang-skripsi/internal/database"
	"backend-golang-skripsi/internal/gdrive"
	"backend-golang-skripsi/internal/handler"
	"backend-golang-skripsi/internal/predictor"

	jsoniter "github.com/json-iterator/go"
)

func main() {
	ctx := context.Background()

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("FATAL: Failed to load configuration: %v", err)
	}

	// Initialize database connection
	dbpool, err := database.NewDBPool(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("FATAL: Failed to connect to database: %v", err)
	}
	defer dbpool.Close()

	// Initialize Google Drive service
	driveService, err := gdrive.NewService(ctx, cfg.GoogleCredentialsPath)
	if err != nil {
		log.Printf("WARNING: Failed to create Google Drive service: %v. Google Drive upload will be disabled.", err)
	}

	// Test Google Drive connection
	if driveService != nil {
		if err := gdrive.TestConnection(ctx, driveService, cfg.GoogleDriveFolderID); err != nil {
			log.Fatalf("FATAL: Google Drive connection test failed: %v", err)
		}
	}

	// Create the predictor
	p := &predictor.Predictor{
		DB:            dbpool,
		Json:          jsoniter.ConfigCompatibleWithStandardLibrary,
		BatchSize:     cfg.BatchSize,
		CallbackURL:   cfg.CallbackURL,
		DriveService:  driveService,
		DriveFolderID: cfg.GoogleDriveFolderID,
	}

	// Create the HTTP handler
	predictHandler := &handler.PredictHandler{
		Json:      jsoniter.ConfigCompatibleWithStandardLibrary,
		Predictor: p,
	}

	// Register handlers and start server
	mux := http.NewServeMux()
	mux.Handle("/predict-stock", predictHandler)

	log.Printf("Starting server on port %s", cfg.Port)
	log.Println("Available endpoints: POST /predict-stock")
	if err := http.ListenAndServe(":"+cfg.Port, mux); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
