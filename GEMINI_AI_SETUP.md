# Google Gemini AI Integration Setup Guide

## Overview
This application now includes AI-enhanced capabilities powered by Google Gemini 2.5 Flash model. The AI features provide intelligent insights for both stock updates and stock predictions.

## Prerequisites
1. Google AI Studio account
2. Google AI Studio API key
3. Internet connectivity for API calls

## Step-by-Step Setup

### 1. Create Google AI Studio Account
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Accept the terms of service if prompted

### 2. Generate API Key
1. In Google AI Studio, click on "Get API key" or go to the API keys section
2. Click "Create API key"
3. Choose an existing Google Cloud project or create a new one
4. Copy the generated API key (keep it secure!)

### 3. Configure Environment Variables
Add the following variables to your `.env` file:

```env
# Google AI Studio Configuration
GOOGLE_API_KEY=your_actual_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 4. Test the Setup
Run the application and check the logs for:
```
Successfully initialized Gemini AI service with model: gemini-2.5-flash
Successfully connected to Gemini AI service
```

## Features

### AI-Enhanced Stock Update Agent
When you call `/update-stock`, the system now provides:
- Sales pattern analysis
- Customer behavior insights
- Inventory optimization recommendations
- Anomaly detection in sales data

**Example Response:**
```json
{
  "status": "Process completed successfully",
  "message": "Stok telah berhasil diperbarui.",
  "ai_insights": "Based on the sales data analysis, I notice that Product ID 123 shows unusually high sales volume..."
}
```

### AI-Enhanced Stock Prediction Agent
When you call `/predict-stock`, the system now provides:
- Advanced trend analysis
- Market risk assessments
- Business recommendations
- Intelligent insights for decision making

**Example Response:**
```json
{
  "task_id": "task_123",
  "status": "Done",
  "products_flagged": 15,
  "ai_analysis": "Market trend analysis indicates seasonal demand patterns...",
  "last_message": "Prediksi Selesai dengan AI Analysis, Silahkan cek Summary"
}
```

## Rate Limiting and Best Practices

### Rate Limits
- Google AI Studio has generous rate limits for the free tier
- For production use, consider upgrading to a paid plan
- The application handles rate limiting gracefully

### Best Practices
1. **API Key Security**: Never commit your API key to version control
2. **Error Handling**: The application continues to work even if AI services are unavailable
3. **Monitoring**: Check logs for AI service connectivity issues
4. **Costs**: Monitor your API usage in Google AI Studio console

### Cost Optimization
- AI analysis is performed on samples (first 100 products for predictions)
- API calls are made efficiently to minimize costs
- Consider disabling AI features for development/testing environments

## Troubleshooting

### Common Issues

#### "Gemini client not initialized"
- Check that `GOOGLE_API_KEY` is set in your environment
- Verify the API key is valid and active
- Ensure you have internet connectivity

#### "Failed to connect to Gemini AI"
- Verify your API key is correct
- Check Google AI Studio service status
- Ensure your firewall allows outbound HTTPS connections

#### "AI analysis unavailable"
- This is a non-fatal error - the application continues without AI features
- Check the logs for specific error details
- Verify your API quota hasn't been exceeded

### Testing AI Integration
Run the test suite to verify integration:
```bash
GOOGLE_API_KEY=your_key_here go test -v
```

## Fallback Behavior
If AI services are unavailable:
- Stock updates continue to work normally
- Stock predictions continue with mathematical analysis
- Error messages are logged but don't break functionality
- Responses include "AI analysis unavailable" messages

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | No | - | Google AI Studio API key |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model to use |

## Security Considerations
1. Keep your API key confidential
2. Use environment variables for configuration
3. Regularly rotate API keys
4. Monitor API usage for unexpected activity
5. Consider using Google Cloud IAM for advanced security

## Support
For issues related to:
- **Google AI Studio**: Check [Google AI Studio documentation](https://ai.google.dev/)
- **API Keys**: Visit [Google AI Studio API management](https://aistudio.google.com/)
- **Rate Limits**: See Google AI Studio usage dashboard