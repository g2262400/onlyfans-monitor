# Playwright base image (includes Chromium and system deps)
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

WORKDIR /app
COPY monitor.py /app/monitor.py

# Install Python bindings + requests
RUN pip install --no-cache-dir playwright requests

# Run the script
CMD ["python", "monitor.py"]
