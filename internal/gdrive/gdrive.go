package gdrive

import (
	"context"
	"fmt"
	"log"
	"os"

	"google.golang.org/api/drive/v3"
	"google.golang.org/api/option"
)

// NewService creates a new Google Drive service.
func NewService(ctx context.Context, credentialsPath string) (*drive.Service, error) {
	if credentialsPath == "" {
		log.Println("WARNING: GOOGLE_CREDENTIALS_PATH not set. Google Drive upload will be disabled.")
		return nil, nil
	}

	credentialsData, err := os.ReadFile(credentialsPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read Google credentials file at '%s': %w", credentialsPath, err)
	}

	driveService, err := drive.NewService(ctx, option.WithCredentialsJSON(credentialsData), option.WithScopes(drive.DriveScope))
	if err != nil {
		return nil, fmt.Errorf("failed to create Google Drive service: %w", err)
	}

	log.Println("Successfully initialized Google Drive service.")
	return driveService, nil
}

// TestConnection tests if we can connect to Google Drive and access the folder.
func TestConnection(ctx context.Context, service *drive.Service, folderID string) error {
	if service == nil {
		return fmt.Errorf("Google Drive service not initialized")
	}

	if folderID == "" {
		log.Println("WARNING: GOOGLE_DRIVE_FOLDER_ID not set. Files will be uploaded to root 'My Drive' folder.")
		return nil
	}

	_, err := service.Files.Get(folderID).Fields("id", "name").Do()
	if err != nil {
		return fmt.Errorf("failed to access Google Drive folder %s. Please ensure the folder ID is correct and you have shared the folder with the service account email: %w", folderID, err)
	}

	log.Printf("Successfully verified access to Google Drive folder: %s", folderID)
	return nil
}

// UploadFile uploads a file to the configured Google Drive folder.
func UploadFile(ctx context.Context, service *drive.Service, filePath, fileName, folderID string) (string, error) {
	if service == nil {
		return "", fmt.Errorf("Google Drive service not configured")
	}

	file, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to open file '%s': %w", filePath, err)
	}
	defer file.Close()

	fileMetadata := &drive.File{
		Name:    fileName,
		Parents: []string{folderID},
	}

	driveFile, err := service.Files.Create(fileMetadata).Media(file).Context(ctx).Do()
	if err != nil {
		return "", fmt.Errorf("failed to create file in Google Drive: %w", err)
	}

	permission := &drive.Permission{
		Type: "anyone",
		Role: "reader",
	}
	_, err = service.Permissions.Create(driveFile.Id, permission).Context(context.Background()).Do()
	if err != nil {
		log.Printf("Warning: Failed to make file '%s' public: %v", driveFile.Id, err)
	}

	return driveFile.Id, nil
}
