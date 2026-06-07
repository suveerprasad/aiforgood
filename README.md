# BloodBridge AI

> AI-powered blood donation management platform that intelligently connects blood banks, donors, and patients using AWS cloud services and machine learning.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [User Roles](#user-roles)
- [Features](#features)
- [AWS Services](#aws-services)
- [Local Setup](#local-setup)
- [Running the App](#running-the-app)
- [Seeding Demo Data](#seeding-demo-data)
- [API Reference](#api-reference)
- [ML Pipeline](#ml-pipeline)
- [Deployment](#deployment)

---

## Overview

BloodBridge AI solves the critical challenge of matching blood donors to patients in real time. Traditional blood banks rely on manual calls and spreadsheets. BloodBridge AI replaces this with:

- **Intelligent donor matching** using a multi-factor scoring algorithm (eligibility, reliability, distance, response rate, active status)
- **Automated escalation** through a Step Functions workflow that progressively widens the search radius and escalates to NGO networks
- **AI-generated outreach messages** via Amazon Bedrock (Claude Sonnet) personalized to each donor
- **Demand forecasting** to predict blood shortages before they happen
- **Conversational AI** via Amazon Lex for donor interactions over chat

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)               │
│  Blood Bank Portal │ Donor Portal │ Patient Portal           │
└───────────────┬──────────────────────────────────────────────┘
                │ REST API (Axios + JWT)
┌───────────────▼──────────────────────────────────────────────┐
│                    Backend (FastAPI / Python)                 │
│  /auth  /donors  /patients  /matching  /inventory  /webhooks │
│  /insights  (running on AWS App Runner or local uvicorn)     │
└───┬───────────────┬───────────────┬────────────────┬─────────┘
    │               │               │                │
┌───▼───┐    ┌──────▼──┐    ┌───────▼─────┐  ┌──────▼──────┐
│Dynamo │    │ Bedrock  │    │Step Functions│  │  Amazon Lex  │
│  DB   │    │(Claude)  │    │(Escalation) │  │  (Chat Bot)  │
└───────┘    └─────────┘    └─────────────┘  └─────────────┘
    │
┌───▼────────────────────────────────────────────────────────┐
│  DynamoDB Tables                                           │
│  bb_users │ bb_requests │ bb_inventory │ bb_notifications  │
│  bb_sessions │ bb_auth_users                               │
└────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer      | Technology                                      |
|------------|-------------------------------------------------|
| Frontend   | React 18, Vite, Tailwind CSS, React Router v6, Axios, Lucide React |
| Backend    | FastAPI, Python 3.12, Uvicorn, Pydantic v2      |
| Auth       | JWT (`python-jose`), bcrypt password hashing    |
| Database   | AWS DynamoDB (6 tables, on-demand billing)      |
| AI / ML    | Amazon Bedrock (Claude Sonnet), scikit-learn    |
| Messaging  | Amazon SES (email), Amazon SNS (SMS)            |
| Chatbot    | Amazon Lex V2                                   |
| Orchestration | AWS Step Functions + Lambda (10 handlers)    |
| Storage    | Amazon S3 (dataset, ML models)                  |
| Deployment | AWS App Runner (backend), AWS Amplify (frontend) |
| IaC        | AWS CDK / manual CLI (Step Functions, Lex)      |

---

## Project Structure

```
aiforgood/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── auth.py          # Register, login, JWT, /me
│   │   │   ├── donors.py        # List, get, consent, status
│   │   │   ├── patients.py      # Create/list/update blood requests
│   │   │   ├── matching.py      # Donor matching + eligible-requests
│   │   │   ├── inventory.py     # Stock management, issue, release
│   │   │   ├── insights.py      # AI insights via Bedrock
│   │   │   └── webhooks.py      # Donor response, volunteer, Lex chat
│   │   ├── services/
│   │   │   ├── donor_matcher.py    # 4-stage matching engine
│   │   │   ├── donor_ranker.py     # Multi-factor scoring algorithm
│   │   │   ├── demand_predictor.py # Blood demand forecasting
│   │   │   ├── inventory_manager.py
│   │   │   ├── communicator.py     # SES/SNS notification sender
│   │   │   ├── ai_insights.py      # Bedrock Claude integration
│   │   │   ├── window_planner.py   # Collection window calculation
│   │   │   └── feedback_loop.py    # Post-donation outcome tracking
│   │   ├── models/              # Pydantic models
│   │   ├── utils/
│   │   │   ├── blood_compat.py  # Compatibility matrix
│   │   │   └── haversine.py     # Distance calculation
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   └── main.py              # FastAPI app entry point
│   ├── lambdas/                 # Step Functions Lambda handlers
│   │   ├── check_inventory/
│   │   ├── reserve_inventory/
│   │   ├── update_request_status/
│   │   ├── schedule_donation/
│   │   ├── escalate_ngo/
│   │   ├── match_donors/
│   │   ├── send_notification/
│   │   ├── check_response/
│   │   ├── feedback_loop/
│   │   └── lex_fulfillment/
│   ├── step_functions/
│   │   └── escalation_workflow.json
│   ├── lex_bot/
│   │   ├── bot_definition.json
│   │   └── deploy_lex_bot.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── apprunner.yaml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── Dashboard.jsx       # Blood bank admin home
│   │   │   ├── Donors.jsx          # Donor list + scoring table
│   │   │   ├── Requests.jsx        # All requests + matching panel
│   │   │   ├── Inventory.jsx       # Stock management + issue/release
│   │   │   ├── Insights.jsx        # AI insights (Bedrock)
│   │   │   ├── DonorPortal.jsx     # Donor-facing portal
│   │   │   └── PatientPortal.jsx   # Patient-facing portal
│   │   ├── components/
│   │   │   ├── DonorRankTable.jsx
│   │   │   ├── DonorChatWidget.jsx
│   │   │   ├── EscalationTimeline.jsx
│   │   │   ├── InventoryExpiryAlert.jsx
│   │   │   ├── DemandBarChart.jsx
│   │   │   └── layout/
│   │   │       ├── Navbar.jsx
│   │   │       └── Sidebar.jsx
│   │   ├── contexts/
│   │   │   └── AuthContext.jsx
│   │   ├── services/
│   │   │   └── api.js             # Axios client + all API calls
│   │   └── App.jsx                # Routes + role-based guards
│   └── package.json
└── ml/
    ├── glue_ingest.py             # ETL: CSV → DynamoDB
    ├── seed_demo_data.py          # Demo data seeder
    ├── fix_table_schemas.py       # DynamoDB schema migration
    ├── notebooks/
    │   ├── 01_eda.ipynb
    │   ├── 02_demand_forecast.ipynb
    │   └── 03_donor_scoring_validation.ipynb
    └── sagemaker/
        ├── train_demand_model.py
        └── feature_store_setup.py
```

---

## User Roles

| Role         | Access                                                              |
|--------------|---------------------------------------------------------------------|
| `blood_bank` | Full admin — Dashboard, Donors, Requests, Inventory, AI Insights   |
| `donor`      | Donor Portal — view compatible requests, volunteer, chat bot       |
| `patient`    | Patient Portal — create blood requests, track status, re-match     |

---

## Features

### Blood Bank Admin Portal
- **Dashboard** — live KPIs: total requests, matched, fulfilled, inventory levels, demand forecast chart
- **Donors** — paginated donor list with search by name/email/blood group, filter by role & eligibility, scoring breakdown
- **Requests** — create/manage all blood requests, trigger matching, view ranked donor list per request, issue / release blood units
- **Inventory** — per-blood-group stock levels, expiry alerts, add units, issue transfusions, release reservations
- **AI Insights** — Bedrock-powered narrative insights: demand patterns, donor engagement, inventory risk, outreach recommendations

### Donor Portal
- View compatible open requests (filtered by blood group compatibility)
- See patient details (anonymized first name), distance, urgency, transfusion date
- Click **"I'm Available"** to volunteer — automatically creates a reserved blood unit in inventory
- View notifications sent by the blood bank
- Confirm / Decline donation via notification
- AI chat bot (Amazon Lex) for Q&A

### Patient Portal
- Create blood requests (blood group locked to registered group)
- Auto-triggers donor matching on submission
- Track request status: `open → matching → matched → fulfilled`
- Escalation timeline visualization
- **Re-match** button to find newly registered donors
- Cancel active requests

---

## AWS Services

| Service | Usage |
|---------|-------|
| **DynamoDB** | Primary database — 6 tables with GSIs |
| **Bedrock (Claude Sonnet)** | AI insights, donor outreach message generation |
| **SES** | Email notifications to donors |
| **SNS** | SMS notifications to donors |
| **Lex V2** | Donor chat bot (DonorResponseBot) |
| **Step Functions** | 10-step donor escalation workflow |
| **Lambda** | Step Functions task handlers (10 functions) |
| **S3** | Dataset storage, ML model artifacts |
| **App Runner** | Backend hosting (containerized FastAPI) |
| **Amplify** | Frontend hosting |
| **Secrets Manager** | Production secret management |

### DynamoDB Tables

| Table | Key | Purpose |
|-------|-----|---------|
| `bb_users` | `user_id` | All user profiles (donors, patients, blood bank staff) |
| `bb_auth_users` | `email` | Authentication credentials (hashed passwords) |
| `bb_requests` | `request_id` | Blood requests from patients |
| `bb_inventory` | `blood_unit_id` | Blood unit stock with `blood_group-status-index` GSI |
| `bb_notifications` | `notification_id` | Donor notification log |
| `bb_sessions` | `session_id` | Lex chat sessions |

---

## Local Setup

### Prerequisites
- Python 3.12
- Node.js 18+
- AWS CLI configured with credentials (`aws configure`)
- AWS region: `us-east-1`

### 1. Clone & configure

```bash
git clone <repo-url>
cd aiforgood
```

### 2. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:
```env
AWS_REGION=us-east-1
ENVIRONMENT=development
SECRET_KEY=your-random-secret-key-here
DYNAMODB_USERS_TABLE=bb_users
DYNAMODB_REQUESTS_TABLE=bb_requests
DYNAMODB_INVENTORY_TABLE=bb_inventory
DYNAMODB_NOTIFICATIONS_TABLE=bb_notifications
DYNAMODB_SESSIONS_TABLE=bb_sessions
DYNAMODB_AUTH_TABLE=bb_auth_users
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
SES_SENDER_EMAIL=your-verified-ses-email@example.com
# Optional — leave blank to use direct notification fallback:
# STEP_FUNCTIONS_ARN=arn:aws:states:us-east-1:ACCOUNT:stateMachine:BloodBridgeEscalation
# LEX_BOT_ID=XXXXX
# LEX_BOT_ALIAS_ID=YYYYY
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

Create `frontend/.env`:
```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
```

### 4. Initialize DynamoDB tables

```bash
cd ml
pip install -r requirements.txt
AWS_REGION=us-east-1 python3 glue_ingest.py
```

### 5. Seed demo data

```bash
AWS_REGION=us-east-1 python3 ml/seed_demo_data.py --reset
```

---

## Running the App

### Start backend (terminal 1)

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```

Backend available at: `http://localhost:8080`  
Interactive API docs: `http://localhost:8080/docs`

### Start frontend (terminal 2)

```bash
cd frontend
npm run dev
```

Frontend available at: `http://localhost:5173`

---

## Seeding Demo Data

The seed script populates DynamoDB with:
- 84 patient records with future transfusion dates
- 46 blood units across all blood groups
- Sample blood requests with urgency levels and collection windows

```bash
# First time
AWS_REGION=us-east-1 python3 ml/seed_demo_data.py

# Reset and re-seed (clears existing inventory + requests)
AWS_REGION=us-east-1 python3 ml/seed_demo_data.py --reset
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register as blood_bank / donor / patient |
| POST | `/api/v1/auth/login` | Login → JWT token |
| GET | `/api/v1/auth/me` | Get current user profile |
| GET | `/api/v1/donors` | List all donors (paginated, filterable) |
| GET | `/api/v1/donors/{id}` | Get donor by ID |
| PATCH | `/api/v1/donors/{id}/consent` | Update consent |
| POST | `/api/v1/patients/requests` | Create blood request |
| GET | `/api/v1/patients/requests` | List requests (filter by patient_id, status) |
| PATCH | `/api/v1/patients/requests/{id}` | Update request status |
| POST | `/api/v1/matching/match` | Run donor matching + notify |
| GET | `/api/v1/matching/eligible-requests` | Requests compatible for a donor |
| GET | `/api/v1/matching/demand-forecast` | Blood demand forecast |
| GET | `/api/v1/inventory/summary` | Per-blood-group stock summary |
| POST | `/api/v1/inventory/units` | Add blood unit |
| POST | `/api/v1/inventory/requests/{id}/issue` | Issue blood (mark fulfilled) |
| POST | `/api/v1/inventory/requests/{id}/release` | Release reservation |
| GET | `/api/v1/insights/ai-insights` | Bedrock AI narrative insights |
| POST | `/api/v1/webhooks/donor-volunteer` | Donor volunteers for a request |
| GET | `/api/v1/webhooks/donor-notifications` | Donor's notification history |
| POST | `/api/v1/webhooks/chat` | Chat proxy to Amazon Lex |

---

## ML Pipeline

### Demand Forecasting (`demand_predictor.py`)
- Reads transfusion history from `bb_users`
- Groups by blood group and date
- Applies scikit-learn linear regression to forecast demand 7–14 days ahead
- Calculates urgency scores per blood group

### Donor Scoring Algorithm (`donor_ranker.py`)
Multi-factor weighted score (0–100):

| Factor | Weight | Description |
|--------|--------|-------------|
| Eligibility | 30% | `eligible` status or next eligible date |
| Reliability | 25% | Past donations × donor type multiplier |
| Distance | 20% | Haversine distance, capped at search radius |
| Response Rate | 15% | Historical calls-to-donations ratio |
| Active Status | 10% | Active/Inactive flag + prior donation bonus |

### 4-Stage Matching Engine (`donor_matcher.py`)

| Stage | Description |
|-------|-------------|
| 1 | Bridge donors (existing patient-donor relationships) |
| 2 | Emergency + Bridge donors within expanding radius (10 → 25 → 50 → 100 km) |
| 3 | Regional expansion — all compatible donors within 100 km |
| 4 | NGO escalation flag — no donors found anywhere |

### Escalation Workflow (Step Functions)
10-step state machine:
1. Check inventory
2. Reserve inventory (if available)
3. Notify top donor
4. Wait for response
5. Check donor response
6. If confirmed → Schedule donation
7. If declined → Try next donor (loops back)
8. If exhausted → Escalate to NGO
9. Update request status
10. Trigger feedback loop

---

## Deployment

### Backend → AWS App Runner

```bash
# Build Docker image
cd backend
docker build -t bloodbridge-api .

# Push to ECR
aws ecr create-repository --repository-name bloodbridge-api --region us-east-1
docker tag bloodbridge-api:latest <account>.dkr.ecr.us-east-1.amazonaws.com/bloodbridge-api:latest
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/bloodbridge-api:latest

# Deploy via App Runner (uses apprunner.yaml)
aws apprunner create-service --cli-input-json file://apprunner.yaml
```

### Frontend → AWS Amplify

```bash
cd frontend
npm run build
# Connect the /dist folder to Amplify console or use Amplify CLI
```

### Step Functions + Lambda

```bash
# Deploy each Lambda
cd backend/lambdas/check_inventory
zip -r function.zip .
aws lambda create-function \
  --function-name bb-check-inventory \
  --runtime python3.12 \
  --handler handler.lambda_handler \
  --role arn:aws:iam::ACCOUNT:role/BloodBridgeLambdaRole \
  --zip-file fileb://function.zip

# Deploy state machine
aws stepfunctions create-state-machine \
  --name BloodBridgeEscalation \
  --definition file://backend/step_functions/escalation_workflow.json \
  --role-arn arn:aws:iam::ACCOUNT:role/BloodBridgeStepFunctionsRole
```

### Lex Chatbot

```bash
cd backend/lex_bot
pip install boto3
python deploy_lex_bot.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_REGION` | Yes | AWS region (e.g. `us-east-1`) |
| `SECRET_KEY` | Yes | JWT signing secret |
| `DYNAMODB_USERS_TABLE` | Yes | Default: `bb_users` |
| `DYNAMODB_REQUESTS_TABLE` | Yes | Default: `bb_requests` |
| `DYNAMODB_INVENTORY_TABLE` | Yes | Default: `bb_inventory` |
| `DYNAMODB_NOTIFICATIONS_TABLE` | Yes | Default: `bb_notifications` |
| `DYNAMODB_AUTH_TABLE` | Yes | Default: `bb_auth_users` |
| `BEDROCK_MODEL_ID` | Yes | Claude model ID |
| `SES_SENDER_EMAIL` | Yes | Verified SES sender address |
| `STEP_FUNCTIONS_ARN` | No | If blank, uses direct notification fallback |
| `LEX_BOT_ID` | No | Lex bot ID for chat widget |
| `LEX_BOT_ALIAS_ID` | No | Lex bot alias ID |
| `JWT_EXPIRE_MINUTES` | No | Default: `1440` (24h) |

---

## Key Design Decisions

- **Dev fallback for Step Functions** — When `STEP_FUNCTIONS_ARN` is not set, the matching endpoint directly notifies the top 3 donors via SES/SNS, so the app works fully locally without Step Functions deployed.
- **Donor-volunteered inventory** — When a donor clicks "I'm Available", a blood unit is automatically created in `bb_inventory` with `status = Reserved`, so the blood bank can immediately issue it.
- **Blood group locked for patients** — The request form always uses the patient's registered blood group, preventing mismatched requests.
- **Paginated DynamoDB scans** — All list endpoints follow `LastEvaluatedKey` to ensure no records are cut off by the 1MB scan limit.
- **Privacy** — Only the patient's first name is shown to donors; full details stay server-side.

---

## License

MIT — built for the AI for Good Hackathon.
