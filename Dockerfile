# Use Playwright base image with Python + Chromium preinstalled
FROM mcr.microsoft.com/playwright/python:v1.45.0-focal

# Set working directory
WORKDIR /app

# Copy your Python script into the container
COPY monitor.py /app/monitor.py

# Install dependencies (playwright + requests)
RUN pip install --no-cache-dir playwright requests

# Make sure browsers are installed (Playwright needs this step)
RUN playwright install --with-deps chromium

# Run the script
CMD ["python", "monitor.py"]
