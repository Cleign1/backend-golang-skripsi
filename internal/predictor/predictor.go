package predictor

import (
	"bytes"
	"context"
	"encoding/csv"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"backend-golang-skripsi/internal/config" // Import config
	"backend-golang-skripsi/internal/gdrive"
	"backend-golang-skripsi/internal/models"

	"github.com/jackc/pgx/v5/pgxpool"
	jsoniter "github.com/json-iterator/go"
	"google.golang.org/api/drive/v3"
)

// Predictor holds all the dependencies for the prediction task.
type Predictor struct {
	DB            *pgxpool.Pool
	Json          jsoniter.API
	BatchSize     int
	DriveService  *drive.Service
	DriveFolderID string
	Cfg           *config.Config // Reference to the application configuration
}

// triggerN8nPredictionWorkflow sends a request to start the n8n prediction workflow.
func (p *Predictor) triggerN8nPredictionWorkflow(ctx context.Context, taskID, predictionDate string) error {
	payload := map[string]string{
		"task_id":           taskID,
		"prediction_date":   predictionDate,
		"flask_webhook_url": p.Cfg.FlaskWebhookURL, // Pass Flask's update URL to n8n
		"workflow_type":     "prediction",          // Identify the workflow type for Flask/n8n
	}

	jsonData, err := p.Json.Marshal(payload)
	if err != nil {
		log.Printf("[Predictor][n8nTrigger] ERROR Task ID %s: Failed to marshal n8n trigger payload: %v", taskID, err)
		// Don't return error here, log and maybe proceed, or handle upstream
		return fmt.Errorf("failed to marshal n8n trigger payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", p.Cfg.N8nPredictionTriggerURL, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("[Predictor][n8nTrigger] ERROR Task ID %s: Failed to create n8n trigger request: %v", taskID, err)
		return fmt.Errorf("failed to create n8n trigger request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second} // Sensible timeout for triggering
	resp, err := client.Do(req)
	if err != nil {
		// Log as error because triggering is critical for the timeline display
		log.Printf("[Predictor][n8nTrigger] ERROR Task ID %s: Failed to trigger n8n workflow at %s: %v", taskID, p.Cfg.N8nPredictionTriggerURL, err)
		return fmt.Errorf("failed to trigger n8n workflow: %w", err) // Return error to stop RunTask
	}
	defer resp.Body.Close()

	// Log based on n8n's response status
	if resp.StatusCode >= 300 {
		// Log as warning or error, depending on how critical n8n's confirmation is
		log.Printf("[Predictor][n8nTrigger] WARNING Task ID %s: n8n trigger returned non-OK status: %s", taskID, resp.Status)
		// Optionally return an error if a 2xx response is mandatory
		// return fmt.Errorf("n8n trigger failed with status: %s", resp.Status)
	} else {
		log.Printf("[Predictor][n8nTrigger] Successfully triggered n8n prediction workflow for Task ID %s.", taskID)
	}

	return nil // Trigger request sent successfully (even if n8n returned non-2xx)
}

// RunTask contains the core logic for the prediction analysis. It now triggers n8n first.
func (p *Predictor) RunTask(ctx context.Context, req models.PredictionRequest) {
	log.Printf("[Predictor] Starting background task. Task ID: %s, Prediction Date: %s", req.TaskID, req.PredictionDate)
	startTime := time.Now()

	// --- Trigger n8n Workflow First ---
	err := p.triggerN8nPredictionWorkflow(ctx, req.TaskID, req.PredictionDate)
	if err != nil {
		// If triggering n8n fails, log the error and stop the Go process.
		// Optionally, send a failure callback directly to Flask if configured.
		errMsg := fmt.Sprintf("Gagal memicu workflow n8n: %v", err)
		log.Printf("[Predictor] FATAL ERROR for Task ID %s: %s. Aborting Go processing.", req.TaskID, errMsg)
		if p.Cfg.CallbackURL != "" {
			// Try sending a final failure status directly to Flask
			_ = p.sendFinalCallback(ctx, req.TaskID, "", "", nil, fmt.Errorf(errMsg))
		}
		return // Stop execution here
	}
	// --- n8n Trigger Sent ---

	// --- Continue with Go Backend Processing ---
	// (Analysis, CSV generation, Drive upload - without sending intermediate updates)

	insufficientStockProducts, err := p.analyzeStock(ctx, req)
	if err != nil {
		errMsg := fmt.Sprintf("Gagal menganalisis stok: %v", err)
		log.Printf("[Predictor] ERROR for Task ID %s: %s", req.TaskID, errMsg)
		// Send final failure callback if configured
		if p.Cfg.CallbackURL != "" {
			_ = p.sendFinalCallback(ctx, req.TaskID, "", "", nil, fmt.Errorf(errMsg))
		}
		// n8n should ideally also report failure based on its own steps or timeout
		return
	}

	duration := time.Since(startTime) // Calculate duration after analysis
	log.Printf("[Predictor] Go Analysis for Task ID %s completed in %v. Found %d products with insufficient stock.", req.TaskID, duration, len(insufficientStockProducts))

	filePath, err := p.saveResultsToCSV(req.TaskID, insufficientStockProducts)
	if err != nil {
		errMsg := fmt.Sprintf("Gagal menyimpan hasil CSV: %v", err)
		log.Printf("[Predictor] ERROR for Task ID %s: %s", req.TaskID, errMsg)
		// Send final failure callback if configured
		if p.Cfg.CallbackURL != "" {
			_ = p.sendFinalCallback(ctx, req.TaskID, "", "", nil, fmt.Errorf(errMsg))
		}
		return
	}
	log.Printf("[Predictor] Results for Task ID %s saved locally to %s", req.TaskID, filePath)

	// --- Google Drive Upload ---
	var driveURL string
	var uploadErr error // To capture upload specific error
	if p.DriveService != nil && p.DriveFolderID != "" {
		log.Printf("[Predictor] Task ID %s: Attempting Google Drive upload...", req.TaskID)
		fileID, err := gdrive.UploadFile(ctx, p.DriveService, filePath, filepath.Base(filePath), p.DriveFolderID)
		if err != nil {
			uploadErr = fmt.Errorf("failed to upload results to Google Drive: %w", err)
			log.Printf("[Predictor] WARNING for Task ID %s: %v", req.TaskID, uploadErr)
			// Don't return yet, send final callback indicating upload failure if possible
		} else {
			driveURL = fmt.Sprintf("https://drive.google.com/file/d/%s/view", fileID)
			log.Printf("[Predictor] Results for Task ID %s uploaded to Google Drive: %s", req.TaskID, driveURL)
		}
	} else {
		log.Printf("[Predictor] WARNING for Task ID %s: Google Drive upload skipped - service or folder ID not configured", req.TaskID)
	}
	// --- End Google Drive Upload ---

	// --- Send Final Callback Directly to Flask (Optional) ---
	if p.Cfg.CallbackURL != "" {
		// Use uploadErr if it occurred, otherwise the main process error (which is nil here if we reached this point)
		finalProcessErr := uploadErr // If uploadErr is nil, this is nil
		if err := p.sendFinalCallback(ctx, req.TaskID, filePath, driveURL, insufficientStockProducts, finalProcessErr); err != nil {
			// Log error if sending the final callback fails
			log.Printf("[Predictor] ERROR for Task ID %s sending final callback: %v", req.TaskID, err)
		}
	} else {
		// Log completion even if callback is disabled
		if uploadErr != nil {
			log.Printf("[Predictor] Task ID %s finished processing with Google Drive upload error.", req.TaskID)
		} else {
			log.Printf("[Predictor] Task ID %s finished processing successfully (final callback disabled).", req.TaskID)
		}
	}
	// --- End Final Callback ---
}

// sendFinalCallback sends the final result/status directly to Flask if CallbackURL is configured.
func (p *Predictor) sendFinalCallback(ctx context.Context, taskID, localFilePath, driveURL string, results []models.PredictionResult, processErr error) error {
	// Only proceed if CallbackURL is actually set in the config
	if p.Cfg.CallbackURL == "" {
		log.Printf("[Predictor][FinalCallback] Task ID %s: CallbackURL not configured. Skipping final direct callback.", taskID)
		// Log the outcome clearly
		if processErr != nil {
			log.Printf("[Predictor][FinalCallback] Task ID %s finished with error: %v (Callback skipped)", taskID, processErr)
		} else {
			log.Printf("[Predictor][FinalCallback] Task ID %s finished successfully (Callback skipped)", taskID)
		}
		return nil // Not an error if it's intentionally disabled
	}

	// Determine final status and message for Flask/Celery compatibility
	finalFlaskStatus := "SUCCESS"
	finalMessage := "Prediksi Selesai. Laporan dihasilkan."
	if processErr != nil {
		finalFlaskStatus = "FAILURE"
		finalMessage = fmt.Sprintf("Prediksi Gagal: %v", processErr)
	}

	// Refine message based on Drive upload status
	if driveURL != "" && processErr == nil {
		finalMessage = "Prediksi Selesai. Laporan dihasilkan dan diunggah ke Google Drive."
	} else if driveURL == "" && processErr != nil && p.DriveService != nil && p.DriveFolderID != "" {
		// Error occurred, likely during upload if drive was configured
		finalMessage = fmt.Sprintf("Prediksi Gagal: %v", processErr) // Error message already includes upload failure info
	} else if driveURL == "" && processErr == nil && (p.DriveService == nil || p.DriveFolderID == "") {
		// No error, but Drive was skipped due to config
		finalMessage = "Prediksi Selesai. Laporan dihasilkan (Upload GDrive dilewati)."
	} else if driveURL == "" && processErr == nil && p.DriveService != nil && p.DriveFolderID != "" {
		// THIS CASE indicates an unexpected issue - upload configured but failed silently?
		log.Printf("[Predictor][FinalCallback] WARNING Task ID %s: Drive upload configured but no URL and no error reported. Marking as failure.", taskID)
		finalFlaskStatus = "FAILURE"
		finalMessage = "Prediksi Selesai. Laporan dihasilkan (Namun gagal mengunggah ke Google Drive)."
	}

	// Construct the payload for the direct Flask callback
	finalPayload := map[string]interface{}{
		"task_id":                 taskID,
		"status":                  finalFlaskStatus, // "SUCCESS" or "FAILURE"
		"products_flagged":        len(results),
		"file_location":           localFilePath, // Local path for reference, might be removed if not needed by Flask
		"drive_url":               driveURL,
		"insufficient_stock_list": results, // Include detailed results if Flask needs them
		"last_message":            finalMessage,
	}

	jsonData, err := p.Json.Marshal(finalPayload)
	if err != nil {
		// Log error and potentially return, as Flask won't get the final status
		log.Printf("[Predictor][FinalCallback] ERROR Task ID %s: Failed to marshal final payload: %v", taskID, err)
		return fmt.Errorf("failed to marshal final callback payload: %w", err)
	}

	// Send the final result to the configured Flask Callback URL
	postReq, err := http.NewRequestWithContext(ctx, "POST", p.Cfg.CallbackURL, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("[Predictor][FinalCallback] ERROR Task ID %s: Failed to create final callback request: %v", taskID, err)
		return fmt.Errorf("failed to create final callback request: %w", err)
	}
	postReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second} // Allow slightly longer for final result processing
	resp, err := client.Do(postReq)
	if err != nil {
		log.Printf("[Predictor][FinalCallback] ERROR Task ID %s: Failed to send final callback to %s: %v", taskID, p.Cfg.CallbackURL, err)
		return fmt.Errorf("failed to send final callback: %w", err)
	}
	defer resp.Body.Close()

	// Log Flask's response to the final callback
	log.Printf("[Predictor][FinalCallback] Final callback sent for Task ID %s. Response from %s: %s", taskID, p.Cfg.CallbackURL, resp.Status)
	if resp.StatusCode >= 300 {
		// Log a warning if Flask didn't return a 2xx status
		log.Printf("[Predictor][FinalCallback] WARNING Task ID %s: Final callback received non-OK status %s from Flask.", taskID, resp.Status)
		// Optionally return an error if Flask confirmation is critical
		// return fmt.Errorf("final callback to Flask failed with status %s", resp.Status)
	}

	return nil // Callback HTTP request was made
}

// --- analyzeStock, fetchProductBatch, fetchSalesDataForProducts, saveResultsToCSV ---
// These core logic functions remain unchanged. Ensure they are present below.

func (p *Predictor) analyzeStock(ctx context.Context, req models.PredictionRequest) ([]models.PredictionResult, error) {
	insufficientStockProducts := []models.PredictionResult{}
	offset := 0

	for {
		// log.Printf("[Predictor] Processing batch for Task ID %s, starting at offset %d...", req.TaskID, offset) // Reduce logging noise maybe

		products, err := p.fetchProductBatch(ctx, offset)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch product batch at offset %d: %w", offset, err)
		}
		if len(products) == 0 {
			break // No more products left
		}

		// Prepare for fetching sales data for the current batch
		productMap := make(map[int]models.Product)
		productIDs := make([]int, 0, len(products)) // Pre-allocate slice capacity
		for _, prod := range products {
			if _, exists := productMap[prod.Index]; !exists { // Avoid duplicates if any
				productMap[prod.Index] = prod
				productIDs = append(productIDs, prod.Index)
			}
		}

		// Fetch sales data for the unique product IDs in this batch
		salesData, err := p.fetchSalesDataForProducts(ctx, productIDs, req.PredictionDate)
		if err != nil {
			// More specific error logging
			return nil, fmt.Errorf("failed to fetch sales data for products (offset %d): %w", offset, err)
		}

		// Perform analysis for each product in the batch
		for productID := range productMap { // Iterate using the map keys (unique IDs)
			product := productMap[productID]
			sales, salesExist := salesData[productID]

			var totalSales int = 0
			// var daysWithSales int = 0 // <--- THIS LINE IS REMOVED
			if salesExist {
				// Calculate total sales for the available days (up to 3)
				limit := len(sales)
				if limit > 3 {
					limit = 3 // Consider only the last 3 days if more are returned
				}
				for i := 0; i < limit; i++ {
					totalSales += sales[i]
				}
				// daysWithSales = limit // <--- THIS LINE IS REMOVED
			}

			// Calculate average based on 3 days, even if fewer days had sales
			avgSales := float64(totalSales) / 3.0
			// Simple prediction: next 3 days demand = average * 3
			// Use math.Ceil to round up demand, ensuring buffer
			// predictedDemand := int(math.Ceil(avgSales * 3))
			predictedDemand := int(avgSales * 3) // Stick to simple integer conversion for now

			// Determine if stock is sufficient (stock >= predicted demand)
			isSufficient := product.CurrentStock >= predictedDemand

			// Only add to the result list if stock is deemed insufficient
			if !isSufficient {
				insufficientStockProducts = append(insufficientStockProducts, models.PredictionResult{
					ProductID:           product.Index,
					ProductName:         product.Name,
					CurrentStock:        product.CurrentStock,
					AvgDailySales3Days:  avgSales,
					PredictedDemand3Day: predictedDemand,
					IsSufficient:        isSufficient, // Will be false here
				})
			}
		}

		// Move to the next batch
		offset += p.BatchSize
	} // End of batch processing loop

	return insufficientStockProducts, nil
}

func (p *Predictor) fetchProductBatch(ctx context.Context, offset int) ([]models.Product, error) {
	// Query to fetch products, ordered by index for consistency
	query := `SELECT "index", "name", "stock" FROM public.amazon_dataset ORDER BY "index" LIMIT $1 OFFSET $2;`
	rows, err := p.DB.Query(ctx, query, p.BatchSize, offset)
	if err != nil {
		// Add context to the error message
		return nil, fmt.Errorf("database query failed for product batch (offset %d): %w", offset, err)
	}
	defer rows.Close()

	var products []models.Product
	// Iterate through the returned rows
	for rows.Next() {
		var prod models.Product
		// Scan row data into the Product struct fields
		if err := rows.Scan(&prod.Index, &prod.Name, &prod.CurrentStock); err != nil {
			// Log the specific error but continue if possible, or return error immediately
			log.Printf("Warning: Failed to scan product row at offset %d: %v. Skipping row.", offset, err)
			continue // Skip this row and try the next one
			// Alternatively, to stop on first error:
			// return nil, fmt.Errorf("failed to scan product row (offset %d): %w", offset, err)
		}
		// Append successfully scanned product to the slice
		products = append(products, prod)
	}

	// Check for errors encountered during iteration (like connection issues)
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating over product rows (offset %d): %w", offset, err)
	}

	// Return the slice of products for this batch
	return products, nil
}

func (p *Predictor) fetchSalesDataForProducts(ctx context.Context, productIDs []int, predictionDate string) (map[int][]int, error) {
	// Validate the predictionDate format first
	predDate, err := time.Parse("2006-01-02", predictionDate)
	if err != nil {
		return nil, fmt.Errorf("invalid predictionDate format '%s', expected 'YYYY-MM-DD': %w", predictionDate, err)
	}
	// Calculate the start date (3 days before predictionDate)
	startDate := predDate.AddDate(0, 0, -3).Format("2006-01-02")

	// Query to get sales quantities for the specified product IDs within the date range
	// Orders by date descending to easily get the last 3 days if needed
	query := `
        SELECT "index", "quantity_sold"
        FROM public.daily_sales
        WHERE "index" = ANY($1)   -- Use ANY for efficient querying with an array
          AND "date" >= $2::date  -- Start date (inclusive)
          AND "date" < $3::date   -- End date (exclusive, up to prediction date)
		ORDER BY "index", "date" DESC; -- Order by product and then date (most recent first)
    `
	// Execute the query
	rows, err := p.DB.Query(ctx, query, productIDs, startDate, predictionDate)
	if err != nil {
		return nil, fmt.Errorf("database query for sales failed: %w", err)
	}
	defer rows.Close()

	// Initialize the map to store sales data per product ID
	salesByProduct := make(map[int][]int)
	// Pre-populate keys for all requested product IDs to ensure they exist,
	// even if no sales data is found for some.
	for _, id := range productIDs {
		salesByProduct[id] = make([]int, 0, 3) // Initialize with empty slice, capacity 3
	}

	// Iterate through the query results
	for rows.Next() {
		var productID, quantitySold int
		// Scan the product ID and quantity sold from the current row
		if err := rows.Scan(&productID, &quantitySold); err != nil {
			log.Printf("Warning: Failed to scan sales row: %v. Skipping row.", err)
			continue // Skip problematic rows
		}
		// Append the quantity sold to the corresponding product ID's slice in the map
		// Only add up to 3 sales figures per product (most recent due to ORDER BY)
		if len(salesByProduct[productID]) < 3 {
			salesByProduct[productID] = append(salesByProduct[productID], quantitySold)
		}
	}

	// Check for errors during row iteration
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating over sales rows: %w", err)
	}

	// Optional: Reverse the slices so they are in chronological order if needed elsewhere
	// (Not strictly necessary for the current averaging logic)
	// for id := range salesByProduct {
	// 	s := salesByProduct[id]
	// 	for i, j := 0, len(s)-1; i < j; i, j = i+1, j-1 {
	// 		s[i], s[j] = s[j], s[i]
	// 	}
	// }

	// Return the map containing sales data for each product
	return salesByProduct, nil
}

func (p *Predictor) saveResultsToCSV(taskID string, results []models.PredictionResult) (string, error) {
	// Define the directory for saving results
	resultsDir := "./prediction_results"
	// Create the directory if it doesn't exist
	if err := os.MkdirAll(resultsDir, 0755); err != nil {
		return "", fmt.Errorf("could not create results directory '%s': %w", resultsDir, err)
	}

	// Create a unique and informative filename using the task ID
	// Sanitize taskID if it might contain invalid characters for filenames (e.g., replace '/', ':')
	safeTaskID := taskID // Basic example; consider more robust sanitization if needed
	fileName := fmt.Sprintf("prediction_result_%s.csv", safeTaskID)
	filePath := filepath.Join(resultsDir, fileName)

	// Create the CSV file
	file, err := os.Create(filePath)
	if err != nil {
		return "", fmt.Errorf("could not create CSV file at '%s': %w", filePath, err)
	}
	defer file.Close() // Ensure file is closed even on errors

	// Create a CSV writer
	writer := csv.NewWriter(file)
	// Ensure all buffered data is written to the file upon function exit
	defer writer.Flush()

	// Define CSV Header
	header := []string{
		"Product ID", "Product Name", "Current Stock",
		"Average Daily Sales (Last 3 Days)", "Predicted Demand (Next 3 Days)", "Is Stock Sufficient",
	}
	// Write the header row
	if err := writer.Write(header); err != nil {
		return "", fmt.Errorf("could not write CSV header to '%s': %w", filePath, err)
	}

	// Write Data Rows for each prediction result
	for _, result := range results {
		// Convert numerical and boolean fields to strings
		record := []string{
			strconv.Itoa(result.ProductID),
			result.ProductName, // Assuming product name doesn't contain commas or quotes needing special handling
			strconv.Itoa(result.CurrentStock),
			fmt.Sprintf("%.2f", result.AvgDailySales3Days), // Format float to 2 decimal places
			strconv.Itoa(result.PredictedDemand3Day),
			strconv.FormatBool(result.IsSufficient),
		}
		// Write the record to the CSV file
		if err := writer.Write(record); err != nil {
			// Log error for the specific row but attempt to continue writing others
			log.Printf("Warning: Could not write CSV record for Product ID %d to '%s': %v", result.ProductID, filePath, err)
			// Optionally, uncomment the line below to stop and return error on the first failure:
			// return "", fmt.Errorf("could not write CSV record for Product ID %d: %w", result.ProductID, err)
		}
	}

	// Check for any errors that occurred during the writing process (including flushing)
	if err := writer.Error(); err != nil {
		return "", fmt.Errorf("error occurred while writing or flushing CSV for '%s': %w", filePath, err)
	}

	// Return the full path to the created CSV file
	return filePath, nil
}
