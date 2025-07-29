import os
import json
import requests
from flask import Flask, render_template, jsonify, request

# Google Sheets API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import secretmanager

app = Flask(__name__)

# --- Environment Variables (ดึงค่าจาก Cloud Run หรือ .env) ---
# n8n Webhook URLs ที่ดึงมาจาก Postman Collection ของคุณ
N8N_WEBHOOKS = {
    "create_idea": os.getenv("N8N_WEBHOOK_CREATE_IDEA_URL"),
    "create_image_prompt": os.getenv("N8N_WEBHOOK_CREATE_IMAGE_PROMPT_URL"),
    "create_image": os.getenv("N8N_WEBHOOK_CREATE_IMAGE_URL"),
    "post_fb": os.getenv("N8N_WEBHOOK_POST_FB_URL"),
}

# n8n Workflow Page URLs (สำหรับลิงก์ในกรณีเกิดข้อผิดพลาด เพื่อให้ผู้ใช้ไปดู Workflow ได้)
# คุณต้องตั้งค่า URL เหล่านี้ใน Environment Variables ด้วย
N8N_WORKFLOW_PAGES = {
    "create_idea": os.getenv("N8N_WORKFLOW_CREATE_IDEA_PAGE_URL"),
    "create_image_prompt": os.getenv("N8N_WORKFLOW_CREATE_IMAGE_PROMPT_PAGE_URL"),
    "create_image": os.getenv("N8N_WORKFLOW_CREATE_IMAGE_PAGE_URL"),
    "post_fb": os.getenv("N8N_WORKFLOW_POST_FB_PAGE_URL"),
}

# การตั้งค่า Google Sheets และ Secret Manager
# อัปเดต Google Sheet ID ตามที่คุณให้มา
GOOGLE_SHEET_ID = "10YZyFoqNMsA8CayIhJipLl_i431QqzXaN0tcCmZMiVo"
SECRET_MANAGER_PROJECT_ID = os.getenv("SECRET_MANAGER_PROJECT_ID")
SECRET_MANAGER_SECRET_ID = os.getenv("SECRET_MANAGER_SECRET_ID")
# *** สำคัญ: คุณต้องเปลี่ยน "Sheet1" เป็นชื่อจริงของ Sheet ย่อยที่มี gid=1074598749 ***
# *** และยืนยันว่า Column ที่มี Category อยู่คือ Column A (ถ้าไม่ใช่ ให้เปลี่ยน A เป็นชื่อ Column ที่ถูกต้อง) ***
GOOGLE_SHEET_RANGE = "product!C:C"

# --- ตัวแปร Global สำหรับเก็บ Category ที่ดึงมาจาก Google Sheet ---
UNIQUE_CATEGORIES = []

# --- Helper function: ดึง Secret จาก Google Secret Manager ---
def get_secret(project_id, secret_id):
    """
    ดึงค่า Secret (Service Account Key JSON) จาก Google Secret Manager
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret '{secret_id}' from Secret Manager: {e}")
        return None

# --- Function: ดึง Unique Category จาก Google Sheet ---
def get_unique_categories_from_sheet():
    """
    ดึงรายการ Category ที่ไม่ซ้ำกันจาก Google Sheet ที่ระบุ
    และเก็บไว้ในตัวแปร UNIQUE_CATEGORIES
    """
    global UNIQUE_CATEGORIES
    
    # ตรวจสอบว่า Environment Variables ที่จำเป็นถูกตั้งค่าหรือไม่
    if not GOOGLE_SHEET_ID or not SECRET_MANAGER_PROJECT_ID or not SECRET_MANAGER_SECRET_ID:
        print("Google Sheet ID หรือ Secret Manager credentials ไม่ได้ถูกตั้งค่า. ข้ามการดึง Category.")
        UNIQUE_CATEGORIES = []
        return

    try:
        # ดึง Service Account Key จาก Secret Manager
        service_account_info_json = get_secret(SECRET_MANAGER_PROJECT_ID, SECRET_MANAGER_SECRET_ID)
        if not service_account_info_json:
            UNIQUE_CATEGORIES = []
            return
        
        service_account_info = json.loads(service_account_info_json)

        # Authenticate กับ Google Sheets API ด้วย Service Account
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"] # สิทธิ์อ่านอย่างเดียว
        )
        service = build("sheets", "v4", credentials=credentials)

        # อ่านข้อมูลจาก Sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=GOOGLE_SHEET_RANGE
        ).execute()
        values = result.get("values", [])

        if not values:
            print("ไม่พบข้อมูลใน Google Sheet.")
            UNIQUE_CATEGORIES = []
            return

        # ดึง Category จาก Column แรก (index 0) และทำให้เป็น Unique
        # โดยข้ามแถวแรก (สมมติว่าเป็น Header)
        categories = [row[0] for row in values[1:] if row and row[0]] # ข้าม Header, ตรวจสอบว่าแถวไม่ว่างและ Column แรกไม่ว่าง
        UNIQUE_CATEGORIES = sorted(list(set(categories))) # ทำให้ไม่ซ้ำและเรียงลำดับ
        print(f"ดึงมาได้ {len(UNIQUE_CATEGORIES)} Unique Categories.")

    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการดึง Category จาก Google Sheet: {e}")
        UNIQUE_CATEGORIES = [] # ล้าง Category ถ้าเกิดข้อผิดพลาด

# --- Helper function: เรียก n8n Webhook ---
def call_n8n_webhook(webhook_type, payload=None):
    """
    ส่ง HTTP Request ไปยัง n8n Webhook ที่ระบุ
    """
    url = N8N_WEBHOOKS.get(webhook_type)
    if not url:
        return {"ok": False, "error": f"Webhook URL สำหรับ '{webhook_type}' ไม่ได้ถูกตั้งค่า."}, 400

    timeout_seconds = 300 # Timeout > 300 วินาที ตามที่ระบุ

    try:
        if webhook_type == "create_idea":
            # create_idea เป็น POST request พร้อม JSON body
            if payload is None:
                return {"ok": False, "error": "Payload จำเป็นสำหรับ webhook 'create_idea'."}, 400
            resp = requests.post(url, json=payload, timeout=timeout_seconds)
        else:
            # Webhook อื่นๆ เป็น GET request
            resp = requests.get(url, timeout=timeout_seconds)

        # ตรวจสอบสถานะการตอบกลับ (2xx คือสำเร็จ)
        if 200 <= resp.status_code < 300:
            return {"ok": True, "status": resp.status_code, "response_text": resp.text}, resp.status_code
        else:
            # สำหรับสถานะที่ไม่ใช่ 2xx ให้ส่งสถานะและข้อความตอบกลับไปด้วย
            return {"ok": False, "status": resp.status_code, "response_text": resp.text}, resp.status_code

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "คำขอ Webhook หมดเวลา.", "status": 504}, 504
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"ไม่สามารถเชื่อมต่อ Webhook ได้: {str(e)}", "status": 503}, 503
    except Exception as e:
        return {"ok": False, "error": f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {str(e)}", "status": 500}, 500

# --- Flask Routes ---
@app.route("/")
def index():
    """
    แสดงหน้า UI หลักของ Dashboard
    """
    # ดึง Category เมื่อโหลดหน้าครั้งแรก (หรือเมื่อยังไม่มี)
    if not UNIQUE_CATEGORIES:
        get_unique_categories_from_sheet() 

    return render_template(
        "index.html",
        categories=UNIQUE_CATEGORIES,
        workflow_pages=N8N_WORKFLOW_PAGES # ส่ง URL หน้า Workflow ไปให้ Frontend สำหรับลิงก์ error
    )

@app.route("/trigger/<webhook_type>", methods=["GET", "POST"])
def trigger_n8n_workflow(webhook_type):
    """
    Endpoint สำหรับ Trigger n8n Webhook ตามประเภทที่ระบุ
    """
    if webhook_type not in N8N_WEBHOOKS:
        return jsonify({"ok": False, "error": "ประเภท Webhook ไม่ถูกต้อง."}), 400

    payload = None
    if webhook_type == "create_idea":
        # ถ้าเป็น create_idea ต้องเป็น POST request พร้อม JSON body ที่มี "category"
        if request.method != "POST":
            return jsonify({"ok": False, "error": "create_idea ต้องเป็น POST request."}), 405
        
        request_data = request.get_json()
        if not request_data or "category" not in request_data:
            return jsonify({"ok": False, "error": "ไม่ได้ระบุ Category ใน Body ของคำขอ."}), 400
        payload = {"category": request_data["category"]}
    elif request.method == "POST":
        # ป้องกัน POST request สำหรับ Webhook ที่เป็น GET-only
        return jsonify({"ok": False, "error": f"'{webhook_type}' รองรับเฉพาะ GET request เท่านั้น."}), 405

    data, status_code = call_n8n_webhook(webhook_type, payload)
    return jsonify(data), status_code

@app.route("/get_categories")
def get_categories_api():
    """
    API Endpoint สำหรับ Frontend เพื่อดึง Category แบบ Dynamic
    """
    # ตรวจสอบให้แน่ใจว่า Category ถูกดึงมาแล้ว
    if not UNIQUE_CATEGORIES:
        get_unique_categories_from_sheet() 

    return jsonify({"categories": UNIQUE_CATEGORIES})

if __name__ == "__main__":
    # สำหรับการรันบน Cloud Run, Gunicorn จะจัดการเรื่องนี้
    # สำหรับการพัฒนา Local, จะรัน Flask development server
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)