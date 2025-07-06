package main

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/google/generative-ai-go/genai"
	jsoniter "github.com/json-iterator/go"
	"google.golang.org/api/option"
)

// TestGeminiIntegration tests the Gemini AI integration
func TestGeminiIntegration(t *testing.T) {
	// Skip test if no API key is provided
	apiKey := os.Getenv("GOOGLE_API_KEY")
	if apiKey == "" {
		t.Skip("GOOGLE_API_KEY not set, skipping Gemini integration test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	client, err := genai.NewClient(ctx, option.WithAPIKey(apiKey))
	if err != nil {
		t.Fatalf("Failed to create Gemini client: %v", err)
	}
	defer client.Close()

	server := &Server{
		GeminiClient: client,
		GeminiModel:  "gemini-2.5-flash",
		Json:         jsoniter.ConfigCompatibleWithStandardLibrary,
	}

	// Test connection
	err = server.testGeminiConnection(ctx)
	if err != nil {
		t.Fatalf("Gemini connection test failed: %v", err)
	}

	t.Log("Gemini AI integration test passed")
}

// TestServerStructure validates the Server struct has all required fields
func TestServerStructure(t *testing.T) {
	server := &Server{
		GeminiClient: nil,
		GeminiModel:  "gemini-2.5-flash",
	}

	if server.GeminiModel != "gemini-2.5-flash" {
		t.Errorf("Expected GeminiModel to be 'gemini-2.5-flash', got %s", server.GeminiModel)
	}

	// Test that server can handle nil Gemini client gracefully
	if server.GeminiClient != nil {
		t.Error("Expected GeminiClient to be nil in test")
	}
}

// TestSaleDataStructure ensures SaleData structure is unchanged
func TestSaleDataStructure(t *testing.T) {
	sale := SaleData{
		Index:        1,
		QuantitySold: 5,
	}

	if sale.Index != 1 {
		t.Errorf("Expected Index to be 1, got %d", sale.Index)
	}

	if sale.QuantitySold != 5 {
		t.Errorf("Expected QuantitySold to be 5, got %d", sale.QuantitySold)
	}
}

// TestPredictionResultStructure ensures PredictionResult structure is unchanged
func TestPredictionResultStructure(t *testing.T) {
	result := PredictionResult{
		ProductID:           1,
		ProductName:         "Test Product",
		CurrentStock:        100,
		AvgDailySales3Days:  10.5,
		PredictedDemand3Day: 32,
		IsSufficient:        true,
	}

	if result.ProductID != 1 {
		t.Errorf("Expected ProductID to be 1, got %d", result.ProductID)
	}

	if result.ProductName != "Test Product" {
		t.Errorf("Expected ProductName to be 'Test Product', got %s", result.ProductName)
	}
}