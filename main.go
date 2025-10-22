package main

import (
	"context"
	"log"
	"net/http"
	"os"        // Import os package
	"os/signal" // Import signal package
	"syscall"   // Import syscall package
	"time"      // Import time package

	"backend-golang-skripsi/internal/config"
	"backend-golang-skripsi/internal/database"
	"backend-golang-skripsi/internal/gdrive"
	"backend-golang-skripsi/internal/handler"
	"backend-golang-skripsi/internal/predictor"

	jsoniter "github.com/json-iterator/go"
)

func main() {
	// Use context with background as the base
	// We'll derive a cancellable context later for graceful shutdown
	baseCtx := context.Background()

	// --- Configuration Loading ---
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("FATAL: Failed to load configuration: %v", err)
	}
	log.Println("INFO: Configuration loaded successfully.")

	// --- Database Connection ---
	dbpool, err := database.NewDBPool(baseCtx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("FATAL: Failed to connect to database: %v", err)
	}
	// Defer closing the pool until main function exits
	defer func() {
		log.Println("INFO: Closing database connection pool...")
		dbpool.Close()
		log.Println("INFO: Database connection pool closed.")
	}()
	log.Println("INFO: Database connection established.")

	// --- Google Drive Service Initialization ---
	driveService, err := gdrive.NewService(baseCtx, cfg.GoogleCredentialsPath)
	if err != nil {
		// Log as warning, allows app to run without Drive features
		log.Printf("WARNING: Failed to create Google Drive service: %v. Google Drive features will be disabled.", err)
	} else if driveService != nil {
		// Test connection only if service was initialized successfully
		if err := gdrive.TestConnection(baseCtx, driveService, cfg.GoogleDriveFolderID); err != nil {
			// Log as warning, allows app to run but Drive uploads might fail
			log.Printf("WARNING: Google Drive connection test failed: %v. File uploads may not work.", err)
			// Optionally set driveService to nil if test must pass:
			// driveService = nil
			// log.Println("INFO: Google Drive service disabled due to connection test failure.")
		} else {
			log.Println("INFO: Google Drive service initialized and connection tested successfully.")
		}
	}

	// --- Predictor Initialization ---
	// Create the predictor instance, passing dependencies including the config
	p := &predictor.Predictor{
		DB:            dbpool,
		Json:          jsoniter.ConfigCompatibleWithStandardLibrary, // Use efficient JSON library
		BatchSize:     cfg.BatchSize,
		DriveService:  driveService,            // May be nil if initialization/test failed
		DriveFolderID: cfg.GoogleDriveFolderID, // Will be empty if not set
		Cfg:           cfg,                     // Pass the full config reference
	}
	log.Println("INFO: Predictor initialized.")

	// --- HTTP Handler Setup ---
	// Create the handler for prediction requests, injecting the predictor
	predictHandler := &handler.PredictHandler{
		Json:      jsoniter.ConfigCompatibleWithStandardLibrary,
		Predictor: p,
	}

	// Create a new ServeMux for routing
	mux := http.NewServeMux()
	// Root handler for basic health check/info
	mux.HandleFunc("/", handler.RootHandler)
	// Prediction endpoint handler
	mux.Handle("/predict-stock", predictHandler) // This now accepts immediately and runs in background
	log.Println("INFO: HTTP handlers registered.")

	// --- Server Setup and Graceful Shutdown ---
	server := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: mux,
	}

	// Channel to listen for OS signals (like SIGINT, SIGTERM)
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, syscall.SIGINT, syscall.SIGTERM)

	// Goroutine to start the server
	go func() {
		log.Printf("INFO: Starting server on port %s", cfg.Port)
		log.Println("INFO: Available endpoints: GET /, POST /predict-stock")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("FATAL: Could not listen on %s: %v", server.Addr, err)
		}
		log.Println("INFO: Server finished listening.")
	}()

	// Block until a shutdown signal is received
	sig := <-stopChan
	log.Printf("INFO: Received signal: %v. Starting graceful shutdown...", sig)

	// Create a context with a timeout for shutdown
	shutdownCtx, cancel := context.WithTimeout(baseCtx, 30*time.Second) // 30-second timeout
	defer cancel()

	// Attempt graceful shutdown
	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("ERROR: Server graceful shutdown failed: %v", err)
	} else {
		log.Println("INFO: Server gracefully stopped.")
	}

	// Database pool closure is handled by the deferred function call
}
