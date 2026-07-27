# IntelliProcess AI

Integrated enterprise AI platform combining **Autonomous AP Invoice Processing** with an **Intelligent Records Search Assistant**, built on AWS managed services.

## Overview

| Capability | Description |
|-----------|-------------|
| AP Invoice Agent | Extracts invoice data, matches against POs/GRs, auto-approves or escalates |
| Records Assistant | Natural language search across organizational documents with citations |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI (Python 3.12), Mangum (Lambda adapter) |
| AI | Amazon Bedrock (Claude 3), Bedrock Data Automation, Bedrock Knowledge Bases |
| Infrastructure | AWS Lambda, API Gateway, S3, DynamoDB, Cognito |
| IaC | AWS SAM |
| CI/CD | GitHub Actions |

## Project Structure

```
intelliprocess-ai/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py         # FastAPI entry + Lambda handler
│   │   ├── config.py       # Environment configuration
│   │   ├── routers/        # API route handlers
│   │   ├── services/       # Business logic (extraction, matching, rules)
│   │   ├── models/         # Pydantic schemas
│   │   └── middleware/     # Auth, correlation ID
│   ├── tests/              # pytest (unit + integration)
│   ├── scripts/            # Seed data, KB sync, user creation
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React SPA
│   ├── src/
│   │   ├── components/     # UI components (invoice, chat, dashboard)
│   │   ├── pages/          # Route pages
│   │   ├── services/       # API client, auth, types
│   │   └── context/        # React context (auth)
│   ├── Dockerfile
│   └── package.json
├── infrastructure/         # AWS SAM template
│   └── template.yaml
├── data/                   # Sample invoices, POs, GRs, records
├── docs/                   # Design & specification documents
├── .github/workflows/      # CI/CD pipelines
├── docker-compose.yml      # Local development
├── Makefile                # Project commands
└── .env.example            # Environment template
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- AWS CLI configured with credentials
- AWS SAM CLI
- Docker (optional, for containerized dev)

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd intelliprocess-ai
cp .env.example .env
# Edit .env with your AWS resource IDs
```

### 2. Install dependencies

```bash
make install
```

### 3. Run locally

```bash
# Terminal 1 - Backend
make dev-backend

# Terminal 2 - Frontend
make dev-frontend
```

Backend runs at `http://localhost:8000`, frontend at `http://localhost:5173`.

### 4. Run with Docker

```bash
docker-compose up
```

## AWS Deployment

### First-time setup

```bash
# 1. Deploy infrastructure
make deploy-guided

# 2. Manual setup (AWS Console):
#    - Enable Bedrock model access (Claude 3 Sonnet, Titan Embeddings v2)
#    - Create Bedrock Knowledge Base with S3 data source
#    - Create BDA project + invoice blueprint
#    - Create Bedrock Guardrails

# 3. Update .env and samconfig.toml with resource IDs

# 4. Re-deploy with updated parameters
make deploy

# 5. Create test users and seed data
make create-users
make seed
make sync-kb
```

### Subsequent deploys

```bash
make deploy
```

## Development Commands

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies |
| `make dev-backend` | Run backend with hot-reload |
| `make dev-frontend` | Run frontend with hot-reload |
| `make test` | Run all tests |
| `make lint` | Run linters (ruff + eslint) |
| `make build` | Build for production |
| `make deploy` | Deploy to AWS via SAM |
| `make seed` | Load sample PO/GR data |
| `make sync-kb` | Trigger Knowledge Base sync |
| `make clean` | Remove build artifacts |

## Testing

```bash
# Backend only
make test-backend

# Frontend only
make test-frontend

# All
make test
```

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `DOCUMENT_BUCKET` | S3 bucket for document storage |
| `KNOWLEDGE_BASE_ID` | Bedrock KB for RAG search |
| `BDA_PROJECT_ARN` | Bedrock Data Automation for extraction |
| `BEDROCK_MODEL_ID` | LLM model for agent reasoning |
| `COGNITO_USER_POOL_ID` | User authentication pool |

## Architecture

```
Client (React) → API Gateway → Lambda (FastAPI) → Bedrock / DynamoDB / S3
                                    ↑
                            S3 Event → InvoiceProcessor Lambda → BDA + Matching + Rules
```

- **Single Lambda** serves all API routes via FastAPI + Mangum
- **InvoiceProcessor Lambda** triggered by S3 upload for async invoice processing
- **Bedrock Knowledge Bases** handles RAG (chunking, embedding, retrieval)
- **DynamoDB** stores all metadata (on-demand billing)

## Documentation

Full engineering specifications are in the `docs/` folder:

- Software Requirements Specification
- Functional Requirements
- User Stories & Acceptance Criteria
- System Architecture & Technical Design
- API Specification
- AI Agent & Prompt Design
- Implementation Roadmap
- Testing Strategy
- Deployment Architecture

## Team

University Capstone Project - 3-week delivery timeline.

## License

This project is for educational purposes.
