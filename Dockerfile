# AgentCore는 ARM64 필수
FROM --platform=linux/arm64 python:3.13-slim-bookworm

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agentcore.py ./

EXPOSE 8080

CMD ["python", "agentcore.py"]
