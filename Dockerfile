FROM python:3.11-slim
WORKDIR /app

# Install Ookla speedtest CLI (official, multi-threaded)
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates &&     curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash &&     apt-get install -y speedtest &&     apt-get purge -y gnupg && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--ws", "websockets"]
