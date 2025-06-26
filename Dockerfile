FROM golang:alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod ./

# Initialize and download dependencies (regenerate go.sum)
RUN go mod tidy && go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o main .

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

# Copy the binary from builder stage
COPY --from=builder /app/main .

# Create directory for prediction results
RUN mkdir -p prediction_results

EXPOSE 8080

CMD ["./main"]