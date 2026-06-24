FROM python:3.11-slim

# git: required for PR workspace cloning + git history analysis
# nodejs + npm: required for ESLint (JS/TS multi-language support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    && npm install -g eslint \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
