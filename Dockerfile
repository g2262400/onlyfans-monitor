FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app
COPY monitor.py /app/monitor.py

# Ensure the Python package exists, without installing browsers
RUN python - <<'PY'
try:
    import playwright  # noqa
    print("playwright already present")
except Exception:
    import sys, subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", "playwright"])
PY

RUN pip install --no-cache-dir requests

CMD ["python", "monitor.py"]
