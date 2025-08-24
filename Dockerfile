FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app
COPY monitor.py /app/monitor.py

# Only install requests, playwright already included
RUN pip install --no-cache-dir requests

CMD ["python", "monitor.py"]
