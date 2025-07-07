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
	CallbackURL   string
	DriveService  *drive.Service
	DriveFolderID string
}

// RunTask contains the core logic for the prediction analysis.
func (p *Predictor) RunTask(ctx context.Context, req models.PredictionRequest) {
	log.Printf("[Predictor] Starting background task. Task ID: %s, Prediction Date: %s", req.TaskID, req.PredictionDate)
	startTime := time.Now()

	insufficientStockProducts, err := p.analyzeStock(ctx, req)
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: %v", req.TaskID, err)
		return
	}

	duration := time.Since(startTime)
	log.Printf("[Predictor] Analysis for Task ID %s completed in %v. Found %d products with insufficient stock.", req.TaskID, duration, len(insufficientStockProducts))

	filePath, err := p.saveResultsToCSV(req.TaskID, insufficientStockProducts)
	if err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: %v", req.TaskID, err)
		return
	}
	log.Printf("[Predictor] Results for Task ID %s saved to %s", req.TaskID, filePath)

	var driveURL string
	if p.DriveService != nil && p.DriveFolderID != "" {
		fileID, err := gdrive.UploadFile(ctx, p.DriveService, filePath, filepath.Base(filePath), p.DriveFolderID)
		if err != nil {
			log.Printf("[Predictor] WARNING for Task ID %s: Failed to upload results to Google Drive: %v", req.TaskID, err)
		} else {
			driveURL = fmt.Sprintf("https://drive.google.com/file/d/%s/view", fileID)
			log.Printf("[Predictor] Results for Task ID %s uploaded to Google Drive: %s", req.TaskID, driveURL)
		}
	} else {
		log.Printf("[Predictor] WARNING for Task ID %s: Google Drive upload skipped - not configured", req.TaskID)
	}

	if err := p.sendCallback(ctx, req.TaskID, filePath, driveURL, insufficientStockProducts); err != nil {
		log.Printf("[Predictor] ERROR for Task ID %s: %v", req.TaskID, err)
	}
}

func (p *Predictor) analyzeStock(ctx context.Context, req models.PredictionRequest) ([]models.PredictionResult, error) {
	insufficientStockProducts := []models.PredictionResult{}
	offset := 0

	for {
		log.Printf("[Predictor] Processing batch for Task ID %s, starting at offset %d...", req.TaskID, offset)

		products, err := p.fetchProductBatch(ctx, offset)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch product batch: %w", err)
		}
		if len(products) == 0 {
			break
		}

		productMap := make(map[int]models.Product)
		productIDs := make([]int, len(products))
		for i, prod := range products {
			productMap[prod.Index] = prod
			productIDs[i] = prod.Index
		}

		salesData, err := p.fetchSalesDataForProducts(ctx, productIDs, req.PredictionDate)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch sales data: %w", err)
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
				insufficientStockProducts = append(insufficientStockProducts, models.PredictionResult{
					ProductID:           product.Index,
					ProductName:         product.Name,
					CurrentStock:        product.CurrentStock,
					AvgDailySales3Days:  avgSales,
					PredictedDemand3Day: predictedDemand,
					IsSufficient:        isSufficient,
				})
			}
		}
		offset += p.BatchSize
	}
	return insufficientStockProducts, nil
}

func (p *Predictor) fetchProductBatch(ctx context.Context, offset int) ([]models.Product, error) {
	query := `SELECT "index", "name", "stock" FROM public.amazon_dataset ORDER BY "index" LIMIT $1 OFFSET $2;`
	rows, err := p.DB.Query(ctx, query, p.BatchSize, offset)
	if err != nil {
		return nil, fmt.Errorf("database query failed: %w", err)
	}
	defer rows.Close()

	var products []models.Product
	for rows.Next() {
		var prod models.Product
		if err := rows.Scan(&prod.Index, &prod.Name, &prod.CurrentStock); err != nil {
			return nil, fmt.Errorf("failed to scan product row: %w", err)
		}
		products = append(products, prod)
	}
	if rows.Err() != nil {
		return nil, fmt.Errorf("error iterating over product rows: %w", rows.Err())
	}
	return products, nil
}

func (p *Predictor) fetchSalesDataForProducts(ctx context.Context, productIDs []int, predictionDate string) (map[int][]int, error) {
	query := `
        SELECT "index", "quantity_sold"
        FROM public.daily_sales
        WHERE "index" = ANY($1) 
          AND "date" >= (CAST($2 AS DATE) - interval '3 days')
          AND "date" < CAST($2 AS DATE);
    `
	rows, err := p.DB.Query(ctx, query, productIDs, predictionDate)
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
	if rows.Err() != nil {
		return nil, fmt.Errorf("error iterating over sales rows: %w", rows.Err())
	}
	return salesByProduct, nil
}

func (p *Predictor) saveResultsToCSV(taskID string, results []models.PredictionResult) (string, error) {
	resultsDir := "./prediction_results"
	if err := os.MkdirAll(resultsDir, 0755); err != nil {
		return "", fmt.Errorf("could not create results directory: %w", err)
	}

	fileName := fmt.Sprintf("prediction_result_%s.csv", taskID)
	filePath := filepath.Join(resultsDir, fileName)

	file, err := os.Create(filePath)
	if err != nil {
		return "", fmt.Errorf("could not create CSV file: %w", err)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	header := []string{
		"Product ID", "Product Name", "Current Stock",
		"Average Daily Sales (Last 3 Days)", "Predicted Demand (Next 3 Days)", "Is Stock Sufficient",
	}
	if err := writer.Write(header); err != nil {
		return "", fmt.Errorf("could not write CSV header: %w", err)
	}

	for _, result := range results {
		record := []string{
			strconv.Itoa(result.ProductID),
			result.ProductName,
			strconv.Itoa(result.CurrentStock),
			fmt.Sprintf("%.2f", result.AvgDailySales3Days),
			strconv.Itoa(result.PredictedDemand3Day),
			strconv.FormatBool(result.IsSufficient),
		}
		if err := writer.Write(record); err != nil {
			return "", fmt.Errorf("could not write CSV record: %w", err)
		}
	}
	return filePath, nil
}

func (p *Predictor) sendCallback(ctx context.Context, taskID, filePath, driveURL string, results []models.PredictionResult) error {
	finalPayload := map[string]interface{}{
		"task_id":                 taskID,
		"status":                  "Done",
		"products_flagged":        len(results),
		"file_location":           filePath,
		"drive_url":               driveURL,
		"insufficient_stock_list": results,
		"last_message":            "Prediksi Selesai, Silahkan cek Summary",
	}

	jsonData, err := p.Json.Marshal(finalPayload)
	if err != nil {
		return fmt.Errorf("failed to create final JSON payload: %w", err)
	}

	postReq, err := http.NewRequestWithContext(ctx, "POST", p.CallbackURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create callback request: %w", err)
	}
	postReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(postReq)
	if err != nil {
		return fmt.Errorf("failed to send callback to %s: %w", p.CallbackURL, err)
	}
	defer resp.Body.Close()

	log.Printf("[Predictor] Callback sent for Task ID %s. Response from Flask app: %s", taskID, resp.Status)
	return nil
}
