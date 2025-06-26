FROM golang:1.20 AS builder

WORKDIR /app

RUN go clean -modcache && go mod tidy
RUN go mod download

COPY go.mod go.sum ./
RUN go mod download

COPY src/ ./
RUN go build -o main .

FROM gcr.io/distroless/base

WORKDIR /app
COPY --from=builder /app/main .

EXPOSE 8080

CMD ["./main"]