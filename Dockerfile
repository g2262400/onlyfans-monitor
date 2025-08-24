# Use Playwright base image with Python + Chromium preinstalled
FROM mcr.microsoft.com/playwright/python:v1.45.0-focal

# Set working directory
WORKDIR /app

# Copy your Python script into the container
COPY monitor.py /app/monitor.py

# Install Python dependencies
RUN pip install requests

# Run the script when the container starts
CMD ["python", "monitor.py"]