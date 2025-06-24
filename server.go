package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	// Replaced the standard json library with a high-performance alternative
	jsoniter "github.com/json-iterator/go"
)

// SaleData defines the structure for a single item in the incoming JSON array.
// The `json:"...,string"` tag allows the JSON decoder to automatically convert
// a number formatted as a string (e.g., "22") into an integer.
type SaleData struct {
	Index        int `json:"index,string"`
	QuantitySold int `json:"quantity_sold,string"`
}

// UpdateHandler now holds references to both the database pool and the
// fast JSON library instance for maximum efficiency.
type UpdateHandler struct {
	DB   *pgxpool.Pool
	json jsoniter.API
}

// ServeHTTP is the main handler function for the /update_stock endpoint.
// It orchestrates the entire process from receiving the request to updating the database.
func (h *UpdateHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// 1. --- VALIDATE INCOMING REQUEST ---
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed. Please use POST.", http.StatusMethodNotAllowed)
		return
	}

	// 2. --- DECODE JSON PAYLOAD USING HIGH-PERFORMANCE LIBRARY ---
	// The fields `name` and `date` from your test data will be safely ignored
	// because they are not defined in the SaleData struct.
	var sales []SaleData
	err := h.json.NewDecoder(r.Body).Decode(&sales)
	if err != nil {
		http.Error(w, "Invalid JSON payload: "+err.Error(), http.StatusBadRequest)
		return
	}

	if len(sales) == 0 {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		h.json.NewEncoder(w).Encode(map[string]string{"message": "No data provided for update."})
		return
	}

	log.Printf("Received request to update stock for %d items.", len(sales))
	startTime := time.Now()

	// 3. --- PERFORM BULK DATABASE UPDATE ---
	tx, err := h.DB.Begin(context.Background())
	if err != nil {
		log.Printf("Error starting transaction: %v", err)
		http.Error(w, "Failed to start database transaction.", http.StatusInternalServerError)
		return
	}
	defer tx.Rollback(context.Background())

	tempTableQuery := `
		CREATE TEMP TABLE sales_update (
			product_index INT NOT NULL,
			quantity_sold INT NOT NULL
		) ON COMMIT DROP;
	`
	_, err = tx.Exec(context.Background(), tempTableQuery)
	if err != nil {
		log.Printf("Error creating temp table: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	rows := make([][]interface{}, len(sales))
	for i, sale := range sales {
		rows[i] = []interface{}{sale.Index, sale.QuantitySold}
	}

	copyCount, err := tx.CopyFrom(
		context.Background(),
		pgx.Identifier{"sales_update"},
		[]string{"product_index", "quantity_sold"},
		pgx.CopyFromRows(rows),
	)

	if err != nil {
		log.Printf("Error with CopyFrom: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	if copyCount != int64(len(sales)) {
		log.Printf("CopyFrom: expected to copy %d rows, but copied %d", len(sales), copyCount)
		http.Error(w, "Failed to copy all data to temp table.", http.StatusInternalServerError)
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
		log.Printf("Error executing bulk update: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	err = tx.Commit(context.Background())
	if err != nil {
		log.Printf("Error committing transaction: %v", err)
		http.Error(w, "Database operation failed.", http.StatusInternalServerError)
		return
	}

	duration := time.Since(startTime)
	log.Printf("Successfully updated %d rows in %v.", commandTag.RowsAffected(), duration)

	// 4. --- SEND SUCCESS RESPONSE ---
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	h.json.NewEncoder(w).Encode(map[string]string{
		"status":  "Process completed successfully",
		"message": "Stok telah berhasil diperbarui.",
	})
}

func main() {
	// --- LOAD ENVIRONMENT VARIABLES FROM .env FILE ---
	err := godotenv.Load()
	if err != nil {
		log.Println("No .env file found, will use environment variables from OS")
	}

	// --- DATABASE CONNECTION ---
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("FATAL: DATABASE_URL environment variable not set.")
	}

	dbpool, err := pgxpool.New(context.Background(), dbURL)
	if err != nil {
		log.Fatalf("Unable to create connection pool: %v\n", err)
	}
	defer dbpool.Close()

	log.Println("Successfully connected to PostgreSQL database.")

	// --- HTTP SERVER SETUP ---
	// Instantiate the fast JSON library. Using ConfigCompatibleWithStandardLibrary
	// ensures it behaves as a drop-in replacement.
	var json = jsoniter.ConfigCompatibleWithStandardLibrary
	
	// Inject dependencies (DB pool and JSON library) into the handler.
	updateHandler := &UpdateHandler{DB: dbpool, json: json}

	mux := http.NewServeMux()
	mux.Handle("/update_stock", updateHandler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting server on port %s...", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
