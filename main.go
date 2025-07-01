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
	tx, err := s.DB.Begin(context.Background())
	if err != nil {
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}
	defer tx.Rollback(context.Background())
	_, err = tx.Exec(context.Background(), `
		CREATE TEMP TABLE sales_update (
			product_index INT NOT NULL,
			quantity_sold INT NOT NULL
		) ON COMMIT DROP;
	`)
	if err != nil {
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}
	rows := make([][]interface{}, len(sales))
	for i, sale := range sales {
		rows[i] = []interface{}{sale.Index, sale.QuantitySold}
	}
	_, err = tx.CopyFrom(context.Background(), pgx.Identifier{"sales_update"}, []string{"product_index", "quantity_sold"}, pgx.CopyFromRows(rows))
	if err != nil {
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}
	updateQuery := `
		UPDATE public.amazon_dataset AS ad
		SET stock = ad.stock - su.quantity_sold
		FROM sales_update AS su
		WHERE ad.index = su.product_index;
	`
	commandTag, err := tx.Exec(context.Background(), updateQuery)
	if err != nil {
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}
	if err := tx.Commit(context.Background()); err != nil {
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
	ProductID           int     `json:"product_id"`
	ProductName         string  `json:"product_name"`
	CurrentStock        int     `json:"current_stock"`
	AvgDailySales3Days  float64 `json:"average_daily_sales_last_3_days"`
	PredictedDemand3Day int     `json:"predicted_demand_next_3_days"`
	IsSufficient        bool    `json:"is_stock_sufficient"`
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

	// Launch the long-running task in a new Goroutine (background thread)
	go s.runPredictionTask(req)
}

// runPredictionTask contains the core logic for the prediction analysis.
func (s *Server) runPredictionTask(req PredictionRequest) {
	log.Printf("[Predictor] Starting background task. Task ID: %s, Prediction Date: %s", req.TaskID, req.PredictionDate)
	startTime := time.Now()

	insufficientStockProducts := []PredictionResult{}
	offset := 0

	// --- 1. Batch Processing ---
	for {
		log.Printf("[Predictor] Processing batch for Task ID %s, starting at offset %d...", req.TaskID, offset)

		products, err := s.fetchProductBatch(offset)
		if err != nil {
			log.Printf("[Predictor] ERROR for Task ID %s: Failed to fetch product batch: %v", req.TaskID, err)
			return
		}
		if len(products) == 0 {
			break
		}
		productMap := make(map[int]Product)
		productIDs := make([]int, len(products))
		for i, p := range products {
			productMap[p.Index] = p
			productIDs[i] = p.Index
		}
		salesData, err := s.fetchSalesDataForProducts(productIDs, req.PredictionDate)
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
		fileID, err := s.uploadToGoogleDrive(filePath, fileName)
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
		"file_location":           filePath,
		"drive_url":               driveURL,
		"insufficient_stock_list": insufficientStockProducts,
		"last_message":            "Prediksi Selesai, Silahkan cek Summary",
	}

	jsonData, err := s.Json.Marshal(finalPayload)
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: Failed to create final JSON payload: %v", req.TaskID, err)
		return
	}

	postReq, err := http.NewRequest("POST", s.CallbackURL, bytes.NewBuffer(jsonData))
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

// testGoogleDriveConnection tests if we can connect to Google Drive
func (s *Server) testGoogleDriveConnection() error {
	if s.DriveService == nil {
		return fmt.Errorf("Google Drive service not configured")
	}

	// Test by getting information about the folder
	if s.DriveFolderID != "" {
		_, err := s.DriveService.Files.Get(s.DriveFolderID).Do()
		if err != nil {
			return fmt.Errorf("failed to access Google Drive folder %s: %w", s.DriveFolderID, err)
		}
	}

	return nil
}

// uploadToGoogleDrive uploads a file to Google Drive folder
func (s *Server) uploadToGoogleDrive(filePath, fileName string) (string, error) {
	if s.DriveService == nil {
		return "", fmt.Errorf("Google Drive service not configured")
	}

	// Read the file
	file, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	// Create file metadata
	fileMetadata := &drive.File{
		Name: fileName,
	}

	// If folder ID is specified, set it as parent
	if s.DriveFolderID != "" {
		fileMetadata.Parents = []string{s.DriveFolderID}
	}

	// Upload the file
	driveFile, err := s.DriveService.Files.Create(fileMetadata).Media(file).Do()
	if err != nil {
		return "", fmt.Errorf("failed to upload file to Google Drive: %w", err)
	}

	// Make the file publicly readable (optional)
	permission := &drive.Permission{
		Type: "anyone",
		Role: "reader",
	}
	_, err = s.DriveService.Permissions.Create(driveFile.Id, permission).Do()
	if err != nil {
		log.Printf("Warning: Failed to make file public: %v", err)
	}

	return driveFile.Id, nil
}

// fetchProductBatch and fetchSalesDataForProducts remain unchanged
func (s *Server) fetchProductBatch(offset int) ([]Product, error) {
	query := `SELECT "index", "name", "stock" FROM public.amazon_dataset ORDER BY "index" LIMIT $1 OFFSET $2;`
	rows, err := s.DB.Query(context.Background(), query, s.BatchSize, offset)
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
	return products, nil
}
func (s *Server) fetchSalesDataForProducts(productIDs []int, predictionDate string) (map[int][]int, error) {
	query := `
		SELECT "index", "quantity_sold"
		FROM public.daily_sales
		WHERE "index" = ANY($1) 
		  AND "date" >= (CAST($2 AS DATE) - interval '3 days')
		  AND "date" < CAST($2 AS DATE);
	`
	rows, err := s.DB.Query(context.Background(), query, productIDs, predictionDate)
	if err != nil {
		return nil, fmt.Errorf("database query for sales failed: %w", err)
	}
	defer rows.Close()
	salesByProduct := make(map[int][]int)
	for _, id := range productIDs {
		salesByProduct[id] = []int{}
	}
	for rows.Next() {
		var productID, quantitySold int
		if err := rows.Scan(&productID, &quantitySold); err != nil {
			return nil, fmt.Errorf("failed to scan sales row: %w", err)
		}
		salesByProduct[productID] = append(salesByProduct[productID], quantitySold)
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
	batchSize, _ := strconv.Atoi(batchSizeStr)

	// Get the callback URL from the environment file.
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

		// Read the credentials file
		credentialsData, err := os.ReadFile(credentialsPath)
		if err != nil {
			log.Printf("WARNING: Failed to read Google credentials file: %v. Google Drive upload will be disabled.", err)
		} else {
			// Create Drive service
			driveService, err = drive.NewService(ctx, option.WithCredentialsJSON(credentialsData), option.WithScopes(drive.DriveFileScope))
			if err != nil {
				log.Printf("WARNING: Failed to create Google Drive service: %v. Google Drive upload will be disabled.", err)
				driveService = nil
			} else {
				log.Printf("Successfully initialized Google Drive service")

				// Test the connection
				if driveFolderID != "" {
					if err := func() error {
						_, err := driveService.Files.Get(driveFolderID).Do()
						return err
					}(); err != nil {
						log.Printf("WARNING: Cannot access Google Drive folder '%s': %v. Please check folder ID and permissions.", driveFolderID, err)
					} else {
						log.Printf("Successfully verified access to Google Drive folder: %s", driveFolderID)
					}
				} else {
					log.Println("GOOGLE_DRIVE_FOLDER_ID not set. Files will be uploaded to root folder.")
				}
			}
		}
	} else {
		log.Println("GOOGLE_CREDENTIALS_PATH not set. Google Drive upload will be disabled.")
	}

	server := &Server{
		DB:            dbpool,
		Json:          jsoniter.ConfigCompatibleWithStandardLibrary,
		BatchSize:     batchSize,
		CallbackURL:   callbackURL,
		DriveService:  driveService,
		DriveFolderID: driveFolderID,
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
