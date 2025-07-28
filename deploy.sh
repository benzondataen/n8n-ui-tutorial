gcloud builds submit --tag gcr.io/$YOUR_PROJECT_ID/n8n-ui

gcloud run deploy n8n-ui \
  --image gcr.io/$YOUR_PROJECT_ID/n8n-ui \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars WEBHOOK_URL="$WEBHOOK_URL"