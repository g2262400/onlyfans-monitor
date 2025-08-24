FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy
WORKDIR /app
COPY monitor.py /app/monitor.py
RUN pip install --no-cache-dir playwright requests
CMD ["python", "monitor.py"]
