import os
import json
import requests
from flask import Flask, render_template, jsonify, request

# Google Sheets API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import secretmanager

app = Flask(__name__)

# --- Environment Variables (fetched from Cloud Run or .env) ---
# n8n Webhook URLs from your Postman Collection
N8N_WEBHOOKS = {
    "create_idea": os.getenv("N8N_WEBHOOK_CREATE_IDEA_URL"),
    "create_image_prompt": os.getenv("N8N_WEBHOOK_CREATE_IMAGE_PROMPT_URL"),
    "create_image": os.getenv("N8N_WEBHOOK_CREATE_IMAGE_URL"),
    "post_fb": os.getenv("N8N_WEBHOOK_POST_FB_URL"),
}

# n8n Workflow Page URLs (for linking in case of errors, allowing users to view the workflow)
# You need to set these URLs in your Environment Variables as well.
N8N_WORKFLOW_PAGES = {
    "create_idea": os.getenv("N8N_WORKFLOW_CREATE_IDEA_PAGE_URL"),
    "create_image_prompt": os.getenv("N8N_WORKFLOW_CREATE_IMAGE_PROMPT_PAGE_URL"),
    "create_image": os.getenv("N8N_WORKFLOW_CREATE_IMAGE_PAGE_URL"),
    "post_fb": os.getenv("N8N_WORKFLOW_POST_FB_PAGE_URL"),
}

# Google Sheets and Secret Manager configuration
GOOGLE_SHEET_ID = "10YZyFoqNMsA8CayIhJipLl_i431QqzXaN0tcCmZMiVo" # This is the Spreadsheet ID
SECRET_MANAGER_PROJECT_ID = os.getenv("SECRET_MANAGER_PROJECT_ID")
SECRET_MANAGER_SECRET_ID = os.getenv("SECRET_MANAGER_SECRET_ID")

# Range for categories (sheet "product", column C)
GOOGLE_CATEGORIES_RANGE = "product!C:C"

# Range for content status (sheet "content", column J)
GOOGLE_CONTENT_STATUS_RANGE = "content!J:J"

# --- Global variables for fetched data ---
UNIQUE_CATEGORIES = []
STATUS_COUNTS = {
    "ready_prompt": 0,
    "ready_image": 0,
    "ready_post": 0,
    "done": 0 # Include done status for completeness, though not explicitly requested for display next to buttons
}

# --- Helper function: Fetch Secret from Google Secret Manager ---
def get_secret(project_id, secret_id):
    """
    Fetches the secret (Service Account Key JSON) from Google Secret Manager.
    """
    try:
        # Secret Manager Client will use Application Default Credentials (ADC).
        # For Cloud Run, this will be the Cloud Run Service Account.
        # For local development, this will use credentials set by `gcloud auth application-default login`
        # or `GOOGLE_APPLICATION_CREDENTIALS` environment variable.
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret '{secret_id}' from Secret Manager: {e}")
        return None

# --- Function: Fetch Unique Categories from Google Sheet ---
def get_unique_categories_from_sheet():
    """
    Fetches unique category list from the specified Google Sheet
    and stores it in the UNIQUE_CATEGORIES global variable.
    """
    global UNIQUE_CATEGORIES
    
    # Check if necessary Environment Variables are set
    if not GOOGLE_SHEET_ID or not SECRET_MANAGER_PROJECT_ID or not SECRET_MANAGER_SECRET_ID:
        print("Google Sheet ID or Secret Manager credentials are not set. Skipping category fetch.")
        UNIQUE_CATEGORIES = []
        return

    try:
        # Fetch Service Account Key from Secret Manager
        service_account_info_json = get_secret(SECRET_MANAGER_PROJECT_ID, SECRET_MANAGER_SECRET_ID)
        if not service_account_info_json:
            UNIQUE_CATEGORIES = []
            return
        
        service_account_info = json.loads(service_account_info_json)

        # Authenticate with Google Sheets API using the Service Account
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"] # Read-only permission
        )
        service = build("sheets", "v4", credentials=credentials)

        # Read data from the Sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=GOOGLE_CATEGORIES_RANGE # Use the new range variable
        ).execute()
        values = result.get("values", [])

        if not values:
            print("No data found in Google Sheet for categories.")
            UNIQUE_CATEGORIES = []
            return

        # Extract categories from the first column (index 0) of the specified range
        # Skip the first row (assuming it's a header)
        categories = [row[0] for row in values[1:] if row and row[0]] # Skip header, check if row is not empty and first column is not empty
        UNIQUE_CATEGORIES = sorted(list(set(categories))) # Make unique and sort
        print(f"Fetched {len(UNIQUE_CATEGORIES)} unique categories.")

    except Exception as e:
        print(f"Error fetching categories from Google Sheet: {e}")
        UNIQUE_CATEGORIES = [] # Clear categories if an error occurs

# --- Function: Fetch Status Counts from Google Sheet ---
def get_status_counts_from_sheet():
    """
    Fetches status counts from the specified Google Sheet (content!J:J)
    and updates the STATUS_COUNTS global variable.
    """
    global STATUS_COUNTS

    if not GOOGLE_SHEET_ID or not SECRET_MANAGER_PROJECT_ID or not SECRET_MANAGER_SECRET_ID:
        print("Google Sheet ID or Secret Manager credentials are not set. Skipping status count fetch.")
        STATUS_COUNTS = {k: 0 for k in STATUS_COUNTS} # Reset counts to 0
        return

    try:
        service_account_info_json = get_secret(SECRET_MANAGER_PROJECT_ID, SECRET_MANAGER_SECRET_ID)
        if not service_account_info_json:
            STATUS_COUNTS = {k: 0 for k in STATUS_COUNTS}
            return
        
        service_account_info = json.loads(service_account_info_json)

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        service = build("sheets", "v4", credentials=credentials)

        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=GOOGLE_CONTENT_STATUS_RANGE # Use the new range variable for content status
        ).execute()
        values = result.get("values", [])

        if not values:
            print("No data found in content sheet for status counts.")
            STATUS_COUNTS = {k: 0 for k in STATUS_COUNTS}
            return

        # Initialize counts
        current_counts = {
            "ready_prompt": 0,
            "ready_image": 0,
            "ready_post": 0,
            "done": 0
        }

        # Iterate through values (skipping header if present, assuming first row is header)
        # Using values[1:] to skip the first row (header)
        for row in values[1:]:
            if row and row[0]: # Check if row exists and the first element (column J) is not empty
                status = row[0].strip().lower() # Get status, strip whitespace, and convert to lowercase
                if status in current_counts:
                    current_counts[status] += 1
        
        STATUS_COUNTS = current_counts
        print(f"Fetched status counts: {STATUS_COUNTS}")

    except Exception as e:
        print(f"Error fetching status counts from Google Sheet: {e}")
        STATUS_COUNTS = {k: 0 for k in STATUS_COUNTS} # Reset counts on error

# --- Helper function: Call n8n Webhook ---
def call_n8n_webhook(webhook_type, payload=None):
    """
    Sends an HTTP Request to the specified n8n Webhook.
    """
    url = N8N_WEBHOOKS.get(webhook_type)
    if not url:
        return {"ok": False, "error": f"Webhook URL for '{webhook_type}' is not configured."}, 400

    timeout_seconds = 300 # Timeout > 300 seconds as specified

    try:
        if webhook_type == "create_idea":
            # create_idea is a POST request with a JSON body
            if payload is None:
                return {"ok": False, "error": "Payload is required for 'create_idea' webhook."}, 400
            resp = requests.post(url, json=payload, timeout=timeout_seconds)
        else:
            # Other webhooks are GET requests
            resp = requests.get(url, timeout=timeout_seconds)

        # Check response status (2xx means success)
        if 200 <= resp.status_code < 300:
            return {"ok": True, "status": resp.status_code, "response_text": resp.text}, resp.status_code
        else:
            # For non-2xx statuses, return status and response text
            return {"ok": False, "status": resp.status_code, "response_text": resp.text}, resp.status_code

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "Webhook request timed out.", "status": 504}, 504
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"Could not connect to webhook: {str(e)}", "status": 503}, 503
    except Exception as e:
        return {"ok": False, "error": f"An unexpected error occurred: {str(e)}", "status": 500}, 500

# --- Flask Routes ---
@app.route("/")
def index():
    """
    Displays the main UI dashboard page.
    """
    # Fetch categories when the page loads for the first time (or if not already fetched)
    if not UNIQUE_CATEGORIES:
        get_unique_categories_from_sheet()
    
    # Always fetch status counts when index page is loaded
    get_status_counts_from_sheet() 

    return render_template(
        "index.html",
        categories=UNIQUE_CATEGORIES,
        status_counts=STATUS_COUNTS, # Pass status counts to the frontend
        workflow_pages=N8N_WORKFLOW_PAGES
    )

@app.route("/trigger/<webhook_type>", methods=["GET", "POST"])
def trigger_n8n_workflow(webhook_type):
    """
    Endpoint to trigger n8n webhooks based on the specified type.
    """
    if webhook_type not in N8N_WEBHOOKS:
        return jsonify({"ok": False, "error": "Invalid webhook type."}), 400

    payload = None
    if webhook_type == "create_idea":
        # If create_idea, it must be a POST request with a JSON body containing "category"
        if request.method != "POST":
            return jsonify({"ok": False, "error": "create_idea must be a POST request."}), 405
        
        request_data = request.get_json()
        if not request_data or "category" not in request_data:
            return jsonify({"ok": False, "error": "Category not specified in the request body."}), 400
        payload = {"category": request_data["category"]}
    elif request.method == "POST":
        # Prevent POST requests for GET-only webhooks
        return jsonify({"ok": False, "error": f"'{webhook_type}' only supports GET requests."}), 405

    data, status_code = call_n8n_webhook(webhook_type, payload)
    
    # After a webhook is triggered, refresh status counts
    get_status_counts_from_sheet() 
    
    return jsonify(data), status_code

@app.route("/get_categories")
def get_categories_api():
    """
    API Endpoint for the frontend to dynamically fetch categories.
    """
    # Ensure categories are fetched
    if not UNIQUE_CATEGORIES:
        get_unique_categories_from_sheet() 

    return jsonify({"categories": UNIQUE_CATEGORIES})

@app.route("/get_status_counts")
def get_status_counts_api():
    """
    API Endpoint for the frontend to dynamically fetch status counts.
    """
    get_status_counts_from_sheet() # Refresh counts before returning
    return jsonify({"status_counts": STATUS_COUNTS})

if __name__ == "__main__":
    # For Cloud Run deployment, Gunicorn will manage this.
    # For local development, this runs the Flask development server.
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)