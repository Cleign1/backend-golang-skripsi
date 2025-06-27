# GCP Setup Guide

## Prerequisites
1. Google Cloud Platform account
2. A GCP project with Cloud Storage API enabled
3. A Cloud Storage bucket created

## Step-by-Step Setup

### 1. Enable Cloud Storage API
```bash
gcloud services enable storage.googleapis.com
```

### 2. Create a Service Account
```bash
# Create service account
gcloud iam service-accounts create golang-storage-service \
    --description="Service account for Go app to access Cloud Storage" \
    --display-name="Golang Storage Service"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:golang-storage-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:golang-storage-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.bucketReader"
```

### 3. Create and Download Service Account Key
```bash
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=golang-storage-service@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 4. Create a Cloud Storage Bucket
```bash
gsutil mb gs://your-bucket-name
```

### 5. Configure Environment Variables
Update your `.env` file:
```
GCP_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/your/service-account-key.json
```

### 6. Test the Setup
Run your Go application and check the logs for GCP connection verification.

## Security Best Practices
1. Keep your service account key file secure
2. Never commit the key file to version control
3. Use IAM roles with minimal required permissions
4. Rotate service account keys regularly
5. Consider using Workload Identity if running on GKE

## Troubleshooting
- Ensure the bucket name is globally unique
- Check that the service account has the correct permissions
- Verify the GOOGLE_APPLICATION_CREDENTIALS path is correct
- Make sure the Cloud Storage API is enabled for your project
