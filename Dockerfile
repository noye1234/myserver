# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY . .

EXPOSE 8496



CMD ["python", "main.py"]
