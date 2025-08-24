FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app
COPY monitor.py /app/monitor.py

# Explicitly install playwright bindings + requests
RUN pip install --no-cache-dir playwright requests

# Make sure Chromium and dependencies are available
RUN playwright install --with-deps chromium

CMD ["python", "monitor.py"]
