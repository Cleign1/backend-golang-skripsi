package models

// PredictionRequest defines the structure for the /predict-stock endpoint payload.
type PredictionRequest struct {
	PredictionDate string `json:"prediction_date"`
	TaskID         string `json:"task_id"`
}

// Product holds information about a product's current stock level.
type Product struct {
	ProductID    int    `json:"product_id"`
	Name         string `json:"name"`
	CurrentStock int    `json:"stock"`
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
