# เลือก image พื้นฐาน
FROM python:3.11-slim

# ตั้ง working directory
WORKDIR /app

# Copy ไฟล์ requirements (ถ้ามี) แล้วติดตั้ง
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# เปิดพอร์ต (Flask default 8080 บน Cloud Run)
ENV PORT=8080

# คำสั่งรันแอป
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]