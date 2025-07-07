package handler

import (
	"context"
	"net/http"

	"backend-golang-skripsi/internal/models"
	"backend-golang-skripsi/internal/predictor"

	jsoniter "github.com/json-iterator/go"
)

// PredictHandler handles the /predict-stock endpoint.
type PredictHandler struct {
	Json      jsoniter.API
	Predictor *predictor.Predictor
}

// ServeHTTP now immediately accepts the task and starts it in the background.
func (h *PredictHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed. Please use POST.", http.StatusMethodNotAllowed)
		return
	}

	var req models.PredictionRequest
	if err := h.Json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON payload: "+err.Error(), http.StatusBadRequest)
		return
	}

	if req.PredictionDate == "" || req.TaskID == "" {
		http.Error(w, "Missing 'prediction_date' or 'task_id' in request body.", http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	h.Json.NewEncoder(w).Encode(map[string]string{
		"status":  "Prediction task accepted and is running in the background.",
		"task_id": req.TaskID,
	})

	go h.Predictor.RunTask(context.Background(), req)
}
