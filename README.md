# 🌍 VoyageMind

> **Agentic AI Travel Orchestrator powered by Amazon Nova**

VoyageMind is a production-ready, microservices-based Agentic AI system that builds personalized, real-time, contingency-aware travel itineraries using Amazon Nova (Nova 2 Pro / Lite / Sonic) on AWS Bedrock.

It processes:

- Budget
- Number of travelers
- Travel dates
- Destination
- Voice input (optional)
- Real-time flight, hotel, and weather data

…and generates a smart itinerary with fallback plans.

---

## 🚀 What Makes VoyageMind Different?

Unlike static travel planners, VoyageMind:

- Uses ReAct-style Agent Orchestration
- Calls real-time APIs (flights, weather, hotels)
- Simulates delays & risks
- Generates contingency branches
- Streams reasoning steps to UI
- Is built for horizontal scaling on AWS

---

## 🧠 Architecture Overview

VoyageMind follows a microservices + agentic orchestration architecture:

```
Frontend (Next.js)
        ↓
API Gateway
        ↓
FastAPI Backend (Orchestrator Service)
        ↓
Nova 2 Pro (AWS Bedrock)
        ↓
Tool Services (Flights, Weather, Hotels, Maps)
        ↓
Database + Cache
```

---

## 🏗 Tech Stack

### 🧠 AI & Agents

- Amazon Nova 2 Pro (primary reasoning model)
- Nova 2 Lite (lightweight subtasks)
- Nova 2 Sonic (voice-to-voice, optional)
- AWS Bedrock SDK
- ReAct Agent Pattern
- Structured Tool Calling

### ⚙ Backend

- FastAPI
- Python 3.11+
- Redis (caching)
- PostgreSQL or DynamoDB
- Pydantic
- Uvicorn / Gunicorn
- Docker

### 💻 Frontend

- Next.js 14 (App Router)
- TypeScript
- TailwindCSS
- Zustand (state management)
- Chart.js (budget graphs)
- D3.js (contingency tree)
- Web Speech API (voice input)
- SSE/WebSocket streaming

### ☁ Infrastructure

- AWS EC2 (Backend)
- AWS S3 (Frontend hosting)
- AWS Bedrock (Nova models)
- AWS IAM (role-based access)
- Terraform / AWS CDK
- GitHub Actions (CI/CD)
- Docker Compose (local dev)

---

## 📂 Monorepo Structure

```
voyagemind/
├── backend/
├── frontend/
├── infrastructure/
├── data/
├── docs/
├── .github/workflows/
├── docker-compose.yml
└── README.md
```

Each directory is mapped to a specific team member to avoid merge conflicts during the 20-day sprint.

---

## 🤖 Agent Workflow

### 1️⃣ User Input

User provides:

- Budget
- Travelers
- Dates
- Destination

Optional:

- Voice input
- Image upload

### 2️⃣ Orchestrator Agent (Nova 2 Pro)

The Orchestrator:

- Validates feasibility
- Calls tool APIs
- Reasons step-by-step
- Builds itinerary
- Generates fallback plan

### 3️⃣ Tool Calling Layer

Nova invokes structured tools:

- Flights API (Amadeus / AviationStack)
- Weather API (OpenWeatherMap)
- Hotels API (RapidAPI or mock data)
- OpenStreetMap (geo clustering)

Each tool:

- Has JSON schema
- Returns structured data
- Is cached in Redis

### 4️⃣ Contingency Simulation

- Weather risk? → Indoor activity alternative.
- Flight delay? → Buffer reallocation.
- Budget exceeded? → Suggest mid-range downgrade.

### 5️⃣ Streaming Response

Backend streams:

- Agent reasoning
- Tool outputs
- Final itinerary
- Fallback tree

Frontend visualizes:

- Daily schedule
- Budget breakdown
- Risk graph
- Contingency tree

---

## 🛠 Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker
- AWS Account with Bedrock enabled

### 1️⃣ Clone Repository

```bash
git clone https://github.com/your-org/voyagemind.git
cd voyagemind
```

### 2️⃣ Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=nova-2-pro
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://...
```

Run:

```bash
uvicorn app.main:app --reload
```

### 3️⃣ Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4️⃣ Docker Setup (Recommended)

From root:

```bash
docker-compose up --build
```

This spins up:

- Backend
- Redis
- Database
- Frontend

---

## 🧪 Testing

### Backend

```bash
pytest
```

### Frontend

```bash
npm run lint
npm run test
```

CI runs automatically via GitHub Actions on every PR.

---

## 👥 Team Structure (20-Day Sprint)

- **👤 Member 1 – AI Engineer:** Nova prompt engineering, Orchestrator logic, Sub-agent creation
- **👤 Member 2 – Backend Engineer:** Tool wrappers, API integration, Caching & DB
- **👤 Member 3 – Frontend Engineer:** UI, Streaming integration, Visualization
- **👤 Member 4 – Data Engineer:** Static datasets, Clustering logic, Geo optimizations
- **👤 Member 5 – Cloud Engineer:** Terraform/CDK, IAM policies, Deployment
- **👤 Member 6 – QA & Documentation:** Test cases, Edge cases, Documentation

---

## 📋 Development Guidelines

### 🔹 Branching Strategy

- `main` → production
- `develop` → staging
- `feature/<name>` → new feature

Pull Request rules:

- Minimum 1 reviewer
- All tests must pass
- No direct pushes to main

### 🔹 Code Standards

**Backend:**

- Type hints required
- Pydantic for validation
- Modular tools

**Frontend:**

- Functional components
- No inline styles
- Reusable UI components

### 🔹 Agent Design Rules

- Tools must be idempotent
- Every tool must have a schema
- No hardcoded API keys
- All reasoning must be logged
- All external calls cached

---

## 📊 Scalability Plan

- Stateless backend containers
- Horizontal scaling via load balancer
- Redis for shared cache
- Async FastAPI endpoints
- Model fallback: Nova 2 Lite for lightweight steps

---

## 🔐 Security Best Practices

- IAM role-based Bedrock access
- API rate limiting
- Input validation via Pydantic
- Secrets in AWS Secrets Manager
- HTTPS only

---

## 🌟 Future Enhancements

- Real-time booking integration
- Mobile app
- Personalized memory graph
- Multi-destination planning
- Carbon footprint optimizer
- Group consensus agent
- Multi-language support via Nova

---

## 📜 License

MIT License

---

## ✨ Vision

VoyageMind is not just a travel planner.

It is a multi-agent reasoning system that understands constraints, adapts to real-time changes, and simulates future risks before they happen.

This is how intelligent travel orchestration should work.