package storage

import (
	"context"
	"fmt"
	"net/url"
	"path"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// R2Config holds the configuration required to connect to R2 (S3-compatible).
type R2Config struct {
	Endpoint       string // e.g. "ACCOUNT_ID.r2.cloudflarestorage.com" or "https://ACCOUNT_ID.r2.cloudflarestorage.com"
	AccessKey      string
	SecretKey      string
	Bucket         string
	UseSSL         bool // typically true with R2
	UsePathStyle   bool // default true for best compatibility
	PublicBaseURL  string
	PresignExpires time.Duration
}

// NewR2Client initializes a MinIO (S3-compatible) client for Cloudflare R2.
func NewR2Client(cfg R2Config) (*minio.Client, error) {
	endpoint := strings.TrimSpace(cfg.Endpoint)
	endpoint = strings.TrimPrefix(endpoint, "https://")
	endpoint = strings.TrimPrefix(endpoint, "http://")
	if endpoint == "" {
		return nil, fmt.Errorf("R2 endpoint is required")
	}
	if cfg.AccessKey == "" || cfg.SecretKey == "" {
		return nil, fmt.Errorf("R2 access key and secret key are required")
	}

	opts := &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.UseSSL,
	}
	if cfg.UsePathStyle {
		opts.BucketLookup = minio.BucketLookupPath
	}

	client, err := minio.New(endpoint, opts)
	if err != nil {
		return nil, fmt.Errorf("failed to init R2 client: %w", err)
	}
	return client, nil
}

// UploadFile uploads a local file to the given bucket with the provided object key.
// Returns either a public URL (if PublicBaseURL is set) or a pre-signed URL.
func UploadFile(
	ctx context.Context,
	client *minio.Client,
	bucket string,
	localPath string,
	objectKey string,
	contentType string,
	publicBaseURL string,
	presignExpiry time.Duration,
) (string, error) {
	if bucket == "" {
		return "", fmt.Errorf("bucket is required")
	}
	if objectKey == "" {
		return "", fmt.Errorf("objectKey is required")
	}

	_, err := client.FPutObject(ctx, bucket, objectKey, localPath, minio.PutObjectOptions{
		ContentType: contentType,
	})
	if err != nil {
		return "", fmt.Errorf("upload to R2 failed: %w", err)
	}

	// If a public base URL is configured (e.g., R2 public bucket behind a CDN), construct a direct URL.
	if strings.TrimSpace(publicBaseURL) != "" {
		base := strings.TrimRight(publicBaseURL, "/")
		joined := base + "/" + strings.TrimLeft(objectKey, "/")
		if _, parseErr := url.Parse(joined); parseErr == nil {
			return joined, nil
		}
		// Fallback: escape just the last segment
		return base + "/" + path.Dir(objectKey) + "/" + url.PathEscape(path.Base(objectKey)), nil
	}

	// Otherwise generate a pre-signed URL (default 7 days if not provided).
	if presignExpiry <= 0 {
		presignExpiry = 7 * 24 * time.Hour
	}
	u, err := client.PresignedGetObject(ctx, bucket, objectKey, presignExpiry, nil)
	if err != nil {
		return "", fmt.Errorf("uploaded but failed to generate a pre-signed URL: %w", err)
	}
	return u.String(), nil
}
