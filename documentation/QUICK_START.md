# Quick Start Guide

Get the Medical Chatbot running locally in minutes.

## Prerequisites

- Docker and Docker Compose installed
- Azure OpenAI API access
- Git repository cloned

## 1. Environment Setup

### Copy Environment File

```bash
cp .env.example .env
```

### Configure Required Variables

Edit `.env` with your credentials:

## 2. Start Services

### Option A: Using Deploy Script (Recommended)

```bash
# Start all services
./deploy.sh
```

### Option B: Individual Docker Compose 

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 3. Verify Installation

| Service | URL | Status Check |
|---------|-----|--------------|
| FastAPI Docs | http://localhost:8010/docs | Swagger UI should load |
| Health Check | http://localhost:8010/api/health | Returns `{"status": "healthy", "version": "1.0.0","message": "All systems operational}` |
| Sessions | http://localhost:8510/api/sessions | Available sessions |
| Streamlit UI | http://localhost:8510 | Chat interface visible |
| Neo4j Browser | http://localhost:7476 | Login with neo4j/password |

## 4. Data Ingestion (First Time)

If starting with an empty database, populate it with medical data:

```bash
cd ingest_service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run ingestion
python scripts/run_ingestion.py
```

## 5. Using the Chatbot

### Via Streamlit UI

1. Open http://localhost:8510
2. Start typing medical queries like:
   - "What nutrients does Metformin deplete?"
   - "I'm taking Lisinopril and feel tired"
   - "Recommend supplements for statin users"

### Via API

```bash
curl -X POST http://localhost:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the side effects of Metformin?",
    "session_id": "test-session"
  }'
```

## Troubleshooting

### Neo4j Connection Issues

```bash
# Check Neo4j is running
docker ps | grep neo4j

# View Neo4j logs
docker logs neo4j-medical
```

### API Won't Start

- Verify `.env` file exists and is properly configured
- Check Azure OpenAI credentials are valid
- Ensure Neo4j is accessible at configured URI


## Next Steps

- Read the [Architecture Overview](ARCHITECTURE.md) to understand how the system works
- Explore the Langfuse dashboard for prompt monitoring (if configured)
