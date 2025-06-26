FROM golang:1.20 AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY src/ ./
RUN go build -o main .

FROM gcr.io/distroless/base

WORKDIR /app
COPY --from=builder /app/main .

EXPOSE 8080

CMD ["./main"]