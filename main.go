package main

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	jsoniter "github.com/json-iterator/go"
	"google.golang.org/api/drive/v3"
	"google.golang.org/api/option"
)

// --- SHARED SERVER STRUCTURE ---

// Server holds all the shared dependencies for our application.
type Server struct {
	DB            *pgxpool.Pool
	Json          jsoniter.API
	BatchSize     int
	CallbackURL   string
	DriveService  *drive.Service
	DriveFolderID string
}

// --- AGENT 1: STOCK UPDATER ---

// SaleData defines the structure for the /update-stock endpoint payload.
type SaleData struct {
	Index        int `json:"index,string"`
	QuantitySold int `json:"quantity_sold,string"`
}

// updateStockHandler handles the real-time updating of stock based on a POST request.
func (s *Server) updateStockHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed. Please use POST.", http.StatusMethodNotAllowed)
		return
	}
	var sales []SaleData
	if err := s.Json.NewDecoder(r.Body).Decode(&sales); err != nil {
		http.Error(w, "Invalid JSON payload: "+err.Error(), http.StatusBadRequest)
		return
	}
	if len(sales) == 0 {
		w.Header().Set("Content-Type", "application/json")
		s.Json.NewEncoder(w).Encode(map[string]string{"message": "No data provided for update."})
		return
	}
	log.Printf("[Updater] Received request to update stock for %d items.", len(sales))

	// IMPROVEMENT: Use the request's context for database operations.
	ctx := r.Context()

	tx, err := s.DB.Begin(ctx)
	if err != nil {
		log.Printf("ERROR: Failed to begin transaction: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}
	defer tx.Rollback(ctx) // Rollback is a no-op if the transaction is already committed.

	_, err = tx.Exec(ctx, `
        CREATE TEMP TABLE sales_update (
            product_index INT NOT NULL,
            quantity_sold INT NOT NULL
        ) ON COMMIT DROP;
    `)
	if err != nil {
		log.Printf("ERROR: Failed to create temp table: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	rows := make([][]interface{}, len(sales))
	for i, sale := range sales {
		rows[i] = []interface{}{sale.Index, sale.QuantitySold}
	}

	_, err = tx.CopyFrom(ctx, pgx.Identifier{"sales_update"}, []string{"product_index", "quantity_sold"}, pgx.CopyFromRows(rows))
	if err != nil {
		log.Printf("ERROR: Failed to copy data to temp table: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}
	updateQuery := `
        UPDATE public.amazon_dataset AS ad
        SET stock = ad.stock - su.quantity_sold
        FROM sales_update AS su
        WHERE ad.index = su.product_index;
    `
	commandTag, err := tx.Exec(ctx, updateQuery)
	if err != nil {
		log.Printf("ERROR: Failed to execute update query: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	if err := tx.Commit(ctx); err != nil {
		log.Printf("ERROR: Failed to commit transaction: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	log.Printf("[Updater] Successfully updated %d rows.", commandTag.RowsAffected())
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	s.Json.NewEncoder(w).Encode(map[string]string{
		"status":  "Process completed successfully",
		"message": "Stok telah berhasil diperbarui.",
	})
}

// --- AGENT 2: STOCK PREDICTOR (ASYNCHRONOUS) ---

// PredictionRequest defines the structure for the /predict-stock endpoint payload.
type PredictionRequest struct {
	PredictionDate string `json:"prediction_date"`
	TaskID         string `json:"task_id"`
}

// Product holds information about a product's current stock level.
type Product struct {
	Index        int
	Name         string
	CurrentStock int
}

// PredictionResult holds the final analysis for a single product.
type PredictionResult struct {
	ProductID          int     `json:"product_id"`
	ProductName        string  `json:"product_name"`
	CurrentStock       int     `json:"current_stock"`
	AvgDailySales3Days float64 `json:"average_daily_sales_last_3_days"`
	PredictedDemand3Day int     `json:"predicted_demand_next_3_days"`
	IsSufficient       bool    `json:"is_stock_sufficient"`
}

// predictStockHandler now immediately accepts the task and starts it in the background.
func (s *Server) predictStockHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed. Please use POST.", http.StatusMethodNotAllowed)
		return
	}

	var req PredictionRequest
	if err := s.Json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON payload: "+err.Error(), http.StatusBadRequest)
		return
	}

	if req.PredictionDate == "" || req.TaskID == "" {
		http.Error(w, "Missing 'prediction_date' or 'task_id' in request body.", http.StatusBadRequest)
		return
	}

	// Immediately respond to the caller to prevent timeouts
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	s.Json.NewEncoder(w).Encode(map[string]string{
		"status":  "Prediction task accepted and is running in the background.",
		"task_id": req.TaskID,
	})

	// Launch the long-running task in a new Goroutine
	// IMPROVEMENT: Use a detached context for the background task.
	go s.runPredictionTask(context.Background(), req)
}

// runPredictionTask contains the core logic for the prediction analysis.
func (s *Server) runPredictionTask(ctx context.Context, req PredictionRequest) {
	log.Printf("[Predictor] Starting background task. Task ID: %s, Prediction Date: %s", req.TaskID, req.PredictionDate)
	startTime := time.Now()

	insufficientStockProducts := []PredictionResult{}
	offset := 0

	// --- 1. Batch Processing ---
	for {
		log.Printf("[Predictor] Processing batch for Task ID %s, starting at offset %d...", req.TaskID, offset)

		products, err := s.fetchProductBatch(ctx, offset)
		if err != nil {
			log.Printf("[Predictor] ERROR for Task ID %s: Failed to fetch product batch: %v", req.TaskID, err)
			// Optional: send a failure callback here
			return
		}
		if len(products) == 0 {
			break // All products processed
		}
		productMap := make(map[int]Product)
		productIDs := make([]int, len(products))
		for i, p := range products {
			productMap[p.Index] = p
			productIDs[i] = p.Index
		}
		salesData, err := s.fetchSalesDataForProducts(ctx, productIDs, req.PredictionDate)
		if err != nil {
			log.Printf("[Predictor] ERROR for Task ID %s: Failed to fetch sales data: %v", req.TaskID, err)
			return
		}
		for productID, sales := range salesData {
			product := productMap[productID]
			var totalSales int
			for _, saleQty := range sales {
				totalSales += saleQty
			}
			avgSales := float64(totalSales) / 3.0
			predictedDemand := int(avgSales * 3)
			isSufficient := product.CurrentStock > predictedDemand
			if !isSufficient {
				insufficientStockProducts = append(insufficientStockProducts, PredictionResult{
					ProductID: product.Index, ProductName: product.Name, CurrentStock: product.CurrentStock,
					AvgDailySales3Days: avgSales, PredictedDemand3Day: predictedDemand, IsSufficient: isSufficient,
				})
			}
		}
		offset += s.BatchSize
	}

	duration := time.Since(startTime)
	log.Printf("[Predictor] Analysis for Task ID %s completed in %v. Found %d products with insufficient stock.", req.TaskID, duration, len(insufficientStockProducts))

	// --- 2. Save Results to File ---
	resultsDir := "./prediction_results"
	if err := os.MkdirAll(resultsDir, 0755); err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Could not create results directory: %v", req.TaskID, err)
		return
	}

	fileName := fmt.Sprintf("prediction_result_%s.json", req.TaskID)
	filePath := filepath.Join(resultsDir, fileName)

	fileData, err := s.Json.MarshalIndent(insufficientStockProducts, "", "  ")
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Could not marshal results to JSON: %v", req.TaskID, err)
		return
	}

	if err := os.WriteFile(filePath, fileData, 0644); err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Could not write results file: %v", req.TaskID, err)
		return
	}
	log.Printf("[Predictor] Results for Task ID %s saved to %s", req.TaskID, filePath)

	// --- 3. Upload Results to Google Drive ---
	var driveURL string
	if s.DriveService != nil && s.DriveFolderID != "" {
		fileID, err := s.uploadToGoogleDrive(ctx, filePath, fileName)
		if err != nil {
			log.Printf("[Predictor] WARNING for Task ID %s: Failed to upload results to Google Drive: %v", req.TaskID, err)
			// Continue without failing the entire process
		} else {
			driveURL = fmt.Sprintf("https://drive.google.com/file/d/%s/view", fileID)
			log.Printf("[Predictor] Results for Task ID %s uploaded to Google Drive: %s", req.TaskID, driveURL)
		}
	} else {
		log.Printf("[Predictor] WARNING for Task ID %s: Google Drive upload skipped - not configured", req.TaskID)
	}

	// --- 4. Send POST request back to Flask App ---
	finalPayload := map[string]interface{}{
		"task_id":                 req.TaskID,
		"status":                  "Done",
		"products_flagged":        len(insufficientStockProducts),
		"file_location":           filePath, // Local file path
		"drive_url":               driveURL, // Public Google Drive URL
		"insufficient_stock_list": insufficientStockProducts,
		"last_message":            "Prediksi Selesai, Silahkan cek Summary",
	}

	jsonData, err := s.Json.Marshal(finalPayload)
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Failed to create final JSON payload: %v", req.TaskID, err)
		return
	}

	postReq, err := http.NewRequestWithContext(ctx, "POST", s.CallbackURL, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Failed to create callback request: %v", req.TaskID, err)
		return
	}
	postReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(postReq)
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Failed to send callback to %s: %v", req.TaskID, s.CallbackURL, err)
		return
	}
	defer resp.Body.Close()

	log.Printf("[Predictor] Callback sent for Task ID %s. Response from Flask app: %s", req.TaskID, resp.Status)
}

// testGoogleDriveConnection tests if we can connect to Google Drive and access the folder.
func (s *Server) testGoogleDriveConnection(ctx context.Context) error {
	if s.DriveService == nil {
		return fmt.Errorf("Google Drive service not initialized")
	}

	// Test by getting information about the folder
	if s.DriveFolderID == "" {
		log.Println("WARNING: GOOGLE_DRIVE_FOLDER_ID not set. Files will be uploaded to root 'My Drive' folder.")
		return nil
	}

	_, err := s.DriveService.Files.Get(s.DriveFolderID).Fields("id", "name").Do()
	if err != nil {
		return fmt.Errorf("failed to access Google Drive folder %s. Please ensure the folder ID is correct and you have shared the folder with the service account email: %w", s.DriveFolderID, err)
	}

	log.Printf("Successfully verified access to Google Drive folder: %s", s.DriveFolderID)
	return nil
}

// uploadToGoogleDrive uploads a file to the configured Google Drive folder.
func (s *Server) uploadToGoogleDrive(ctx context.Context, filePath, fileName string) (string, error) {
	if s.DriveService == nil {
		return "", fmt.Errorf("Google Drive service not configured")
	}

	file, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to open file '%s': %w", filePath, err)
	}
	defer file.Close()

	// Create file metadata
	fileMetadata := &drive.File{
		Name:    fileName,
		Parents: []string{s.DriveFolderID}, // Specify the folder
	}

	driveFile, err := s.DriveService.Files.Create(fileMetadata).Media(file).Context(ctx).Do()
	if err != nil {
		return "", fmt.Errorf("failed to create file in Google Drive: %w", err)
	}

	// Make the file publicly readable
	permission := &drive.Permission{
		Type: "anyone",
		Role: "reader",
	}
	// We use a new background context here because we want this permission change to succeed
	// even if the original request that triggered this upload has been cancelled.
	_, err = s.DriveService.Permissions.Create(driveFile.Id, permission).Context(context.Background()).Do()
	if err != nil {
		// This is not a fatal error, the file is uploaded but just not public.
		log.Printf("Warning: Failed to make file '%s' public: %v", driveFile.Id, err)
	}

	return driveFile.Id, nil
}

// fetchProductBatch fetches a batch of products from the database.
func (s *Server) fetchProductBatch(ctx context.Context, offset int) ([]Product, error) {
	query := `SELECT "index", "name", "stock" FROM public.amazon_dataset ORDER BY "index" LIMIT $1 OFFSET $2;`
	rows, err := s.DB.Query(ctx, query, s.BatchSize, offset)
	if err != nil {
		return nil, fmt.Errorf("database query failed: %w", err)
	}
	defer rows.Close()

	var products []Product
	for rows.Next() {
		var p Product
		if err := rows.Scan(&p.Index, &p.Name, &p.CurrentStock); err != nil {
			return nil, fmt.Errorf("failed to scan product row: %w", err)
		}
		products = append(products, p)
	}
	if rows.Err() != nil {
		return nil, fmt.Errorf("error iterating over product rows: %w", rows.Err())
	}
	return products, nil
}

// fetchSalesDataForProducts fetches recent sales data for a given list of product IDs.
func (s *Server) fetchSalesDataForProducts(ctx context.Context, productIDs []int, predictionDate string) (map[int][]int, error) {
	query := `
        SELECT "index", "quantity_sold"
        FROM public.daily_sales
        WHERE "index" = ANY($1) 
          AND "date" >= (CAST($2 AS DATE) - interval '3 days')
          AND "date" < CAST($2 AS DATE);
    `
	rows, err := s.DB.Query(ctx, query, productIDs, predictionDate)
	if err != nil {
		return nil, fmt.Errorf("database query for sales failed: %w", err)
	}
	defer rows.Close()

	salesByProduct := make(map[int][]int)
	for _, id := range productIDs {
		salesByProduct[id] = []int{} // Pre-populate to handle products with no sales
	}

	for rows.Next() {
		var productID, quantitySold int
		if err := rows.Scan(&productID, &quantitySold); err != nil {
			return nil, fmt.Errorf("failed to scan sales row: %w", err)
		}
		salesByProduct[productID] = append(salesByProduct[productID], quantitySold)
	}
	if rows.Err() != nil {
		return nil, fmt.Errorf("error iterating over sales rows: %w", rows.Err())
	}
	return salesByProduct, nil
}

// --- MAIN APPLICATION SETUP ---

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using OS environment variables.")
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("FATAL: DATABASE_URL environment variable is not set.")
	}
	dbpool, err := pgxpool.New(context.Background(), dbURL)
	if err != nil {
		log.Fatalf("Unable to create connection pool: %v\n", err)
	}
	defer dbpool.Close()
	log.Println("Successfully connected to PostgreSQL database.")

	batchSizeStr := os.Getenv("BATCH_SIZE")
	if batchSizeStr == "" {
		batchSizeStr = "500"
	}
	// FIX: Properly handle the error from Atoi
	batchSize, err := strconv.Atoi(batchSizeStr)
	if err != nil {
		log.Fatalf("FATAL: Invalid BATCH_SIZE '%s'. Must be an integer.", batchSizeStr)
	}

	callbackURL := os.Getenv("CALLBACK_URL")
	if callbackURL == "" {
		log.Fatal("FATAL: CALLBACK_URL environment variable is not set.")
	}

	// Initialize Google Drive service (optional)
	var driveService *drive.Service
	driveFolderID := os.Getenv("GOOGLE_DRIVE_FOLDER_ID")
	credentialsPath := os.Getenv("GOOGLE_CREDENTIALS_PATH")

	if credentialsPath != "" {
		ctx := context.Background()
		credentialsData, err := os.ReadFile(credentialsPath)
		if err != nil {
			log.Printf("WARNING: Failed to read Google credentials file at '%s': %v. Google Drive upload will be disabled.", credentialsPath, err)
		} else {
			// FIX: Use drive.DriveScope for broader permissions
			driveService, err = drive.NewService(ctx, option.WithCredentialsJSON(credentialsData), option.WithScopes(drive.DriveScope))
			if err != nil {
				log.Printf("WARNING: Failed to create Google Drive service: %v. Google Drive upload will be disabled.", err)
				driveService = nil // Ensure it's nil on failure
			} else {
				log.Println("Successfully initialized Google Drive service.")
			}
		}
	} else {
		log.Println("WARNING: GOOGLE_CREDENTIALS_PATH not set. Google Drive upload will be disabled.")
	}

	server := &Server{
		DB:            dbpool,
		Json:          jsoniter.ConfigCompatibleWithStandardLibrary,
		BatchSize:     batchSize,
		CallbackURL:   callbackURL,
		DriveService:  driveService,
		DriveFolderID: driveFolderID,
	}

	// IMPROVEMENT: Test Drive connection on startup
	if server.DriveService != nil {
		if err := server.testGoogleDriveConnection(context.Background()); err != nil {
			// Log as a fatal error because the user expects uploads to work.
			log.Fatalf("FATAL: Google Drive connection test failed: %v", err)
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/update-stock", server.updateStockHandler)
	mux.HandleFunc("/predict-stock", server.predictStockHandler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting unified stock management server on port %s", port)
	log.Println("Available endpoints: POST /update-stock, POST /predict-stock")
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}