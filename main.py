from flask import Flask, render_template, jsonify
import requests
import os

app = Flask(__name__)

# ดึง URL ของ Webhook จาก Environment Variable โดยตรง
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

@app.route("/")
def index():
    """แสดงหน้า UI หลักที่มีปุ่มเดียว"""
    return render_template("index.html")

@app.route("/trigger-webhook")
def trigger_webhook():
    """Endpoint สำหรับการ Trigger Webhook"""
    if not WEBHOOK_URL:
        # กรณีที่ไม่ได้ตั้งค่า Environment Variable
        return jsonify({"ok": False, "error": "WEBHOOK_URL environment variable is not set."}), 500

    try:
        # ใช้ requests.get เพื่อส่งคำขอไปยัง Webhook
        # ตั้งค่า timeout เพื่อป้องกันการรอนานเกินไป
        resp = requests.get(WEBHOOK_URL, timeout=10) # ลด timeout เหลือ 10 วินาทีสำหรับการทดสอบ
        
        # ส่ง Status Code กลับไปให้ Frontend ทราบ
        return jsonify({"ok": True, "status": resp.status_code}), resp.status_code
    except requests.exceptions.Timeout:
        # จัดการกรณี Timeout
        return jsonify({"ok": False, "error": "Webhook request timed out."}), 504
    except requests.exceptions.ConnectionError as e:
        # จัดการกรณีเชื่อมต่อไม่ได้ (เช่น URL ผิด, n8n ไม่ทำงาน)
        return jsonify({"ok": False, "error": f"Failed to connect to webhook: {str(e)}"}), 503
    except Exception as e:
        # จัดการข้อผิดพลาดอื่นๆ
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # สำหรับการรันบน Cloud Run, Flask จะใช้ PORT ที่ Cloud Run กำหนดให้
    # หากรันบน Local, จะใช้ 8080 เป็นค่าเริ่มต้น
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)