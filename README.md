# Web App UI สำหรับควบคุม n8n Webhook
โปรเจกต์นี้คือ Web Application UI แบบง่ายๆ ที่สร้างด้วย Flask และ Python เพื่อใช้สำหรับ Trigger n8n Webhook โดยเฉพาะ แอปพลิเคชันนี้ถูกออกแบบมาให้สามารถ Deploy บน Google Cloud Run ได้อย่างง่ายดาย

# คุณสมบัติ (Features)
หน้า UI ที่เรียบง่ายพร้อมปุ่มเดียวสำหรับ Trigger n8n Webhook
แสดงสถานะการ Trigger (สำเร็จ/ล้มเหลว)
ดึง URL ของ n8n Webhook จาก Environment Variable ทำให้ง่ายต่อการจัดการในสภาพแวดล้อมต่างๆ

# เทคโนโลยีที่ใช้ (Technologies Used)
- Python 3.11
- Flask: Web Framework สำหรับ Python
- Gunicorn: WSGI HTTP Server สำหรับ Production
- n8n: Workflow Automation Tool (ต้องมี n8n Instance แยกต่างหาก)
- Google Cloud Run: Serverless Platform สำหรับ Deploy Container
- Google Artifact Registry: สำหรับจัดเก็บ Docker Images

# การตั้งค่า (Setup)
1. การพัฒนาในเครื่อง (Local Development)
ก่อนเริ่มต้น ตรวจสอบให้แน่ใจว่าคุณได้ติดตั้ง Python 3.11 และ pip บนเครื่องของคุณแล้ว

- Clone Repository:
```
git clone <URL_TO_YOUR_REPO>
cd <YOUR_REPO_DIRECTORY>
```

สร้าง Virtual Environment:
python3 -m venv venv


Activate Virtual Environment:
macOS / Linux:
source venv/bin/activate


Windows (Command Prompt):
venv\Scripts\activate.bat


Windows (PowerShell):
.\venv\Scripts\Activate.ps1


ติดตั้ง Dependencies:
สร้างไฟล์ requirements.txt ใน Root Directory ของโปรเจกต์ (ถ้ายังไม่มี) และเพิ่มไลบรารีที่จำเป็น:
Flask
gunicorn
requests

จากนั้นติดตั้ง:
pip install -r requirements.txt


ตั้งค่า Environment Variable:
สร้างไฟล์ .env ใน Root Directory ของโปรเจกต์ และเพิ่ม URL ของ n8n Webhook ของคุณ:
WEBHOOK_URL="YOUR_N8N_WEBHOOK_URL_HERE"
หมายเหตุ: แทนที่ YOUR_N8N_WEBHOOK_URL_HERE ด้วย URL จริงของ n8n Webhook ที่คุณต้องการ Trigger
สำหรับการโหลดไฟล์ .env ใน Local Development คุณอาจต้องติดตั้ง python-dotenv และเพิ่มโค้ดใน main.py เพื่อโหลด Environment Variables:
pip install python-dotenv

เพิ่มโค้ดนี้ที่ บนสุด ของไฟล์ main.py:
from dotenv import load_dotenv
load_dotenv() # โหลด environment variables จากไฟล์ .env


รัน Flask Application:
python main.py

แอปพลิเคชันจะรันอยู่ที่ http://127.0.0.1:8080 (หรือพอร์ตอื่นตามที่กำหนด) เปิด Browser และเข้าถึง URL นี้เพื่อทดสอบ
2. การ Deploy บน Google Cloud Run
ตรวจสอบให้แน่ใจว่าคุณได้ติดตั้งและตั้งค่า Google Cloud SDK รวมถึงได้ Authenticate ไปยัง Project ของคุณแล้ว
สร้าง Docker Image:
ใช้ Dockerfile ที่ให้มาเพื่อสร้าง Image ของแอปพลิเคชันของคุณ:
gcloud builds submit --tag gcr.io/$YOUR_PROJECT_ID/n8n-ui
หมายเหตุ: แทนที่ $YOUR_PROJECT_ID ด้วย Project ID ของ Google Cloud ของคุณ
Deploy ไปยัง Cloud Run:
Deploy Docker Image ที่สร้างขึ้นไปยัง Google Cloud Run และตั้งค่า Environment Variable WEBHOOK_URL:
gcloud run deploy n8n-ui \
  --image gcr.io/$YOUR_PROJECT_ID/n8n-ui \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars WEBHOOK_URL="YOUR_N8N_WEBHOOK_URL_HERE" \
  --region YOUR_GCP_REGION # เช่น us-central1, asia-southeast1
หมายเหตุ:
แทนที่ $YOUR_PROJECT_ID ด้วย Project ID ของ Google Cloud ของคุณ
แทนที่ YOUR_N8N_WEBHOOK_URL_HERE ด้วย URL จริงของ n8n Webhook ที่คุณต้องการ Trigger
แทนที่ YOUR_GCP_REGION ด้วย Region ที่คุณต้องการ Deploy (เช่น asia-southeast1 สำหรับสิงคโปร์)
--allow-unauthenticated อนุญาตให้เข้าถึงแอปพลิเคชันได้โดยไม่ต้องมีการยืนยันตัวตน (Public Access) หากต้องการจำกัดการเข้าถึง ให้ลบ Option นี้ออกและตั้งค่า IAM Permissions เพิ่มเติม
การใช้งาน (Usage)
หลังจาก Deploy สำเร็จ Cloud Run จะให้ URL สำหรับเข้าถึง Web App ของคุณ
เปิด Browser และเข้าถึง URL ที่ Cloud Run ให้มา
คุณจะเห็นหน้า UI ที่มีปุ่ม "Trigger Webhook"
คลิกปุ่ม "Trigger Webhook" เพื่อส่งคำขอ HTTP ไปยัง n8n Webhook ที่คุณตั้งค่าไว้
สถานะการ Trigger จะแสดงอยู่ใต้ปุ่ม (สำเร็จ/ล้มเหลว)
การปรับแต่ง (Customization)
เปลี่ยน UI: คุณสามารถแก้ไขไฟล์ templates/index.html เพื่อปรับแต่งหน้าตาของ Web App ได้ตามต้องการ
เพิ่ม Logic ใน Flask: หากต้องการส่งข้อมูลเพิ่มเติมไปยัง n8n Webhook คุณสามารถแก้ไขฟังก์ชัน trigger_webhook ใน main.py เพื่อเพิ่ม Payload ใน requests.get() หรือเปลี่ยนเป็น requests.post()
# ตัวอย่างการส่ง POST request พร้อม JSON payload
# resp = requests.post(WEBHOOK_URL, json={"key": "value"}, timeout=10)