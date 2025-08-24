# Playwright with Python + Chromium already bundled
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

WORKDIR /app
COPY monitor.py /app/monitor.py

# Install Python dependencies (requests only, playwright is already included in base image)
RUN pip install --no-cache-dir requests

# Koyeb will run this script
CMD ["python", "monitor.py"]
