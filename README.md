# BloodBridge AI

**Autonomous Blood Coordination & Transfusion Planning System**
Built for AI for Good 2.0 Hackathon — Blood Warriors Foundation

---

## What It Does

BloodBridge AI transforms blood donation coordination from reactive manual work into a predictive, autonomous, and intelligent healthcare logistics system.

| Problem | BloodBridge Solution |
|---|---|
| Delayed donor discovery | Demand forecast 7–14 days ahead using patient transfusion schedules |
| Manual follow-ups | Step Functions escalation workflow with SES/SNS automation |
| Donor fatigue | Consent-aware outreach, rotation via scoring, call-ratio tracking |
| No self-improvement | Feedback loop recalculates donor scores after every outcome |
| No conversational channel | Amazon Lex V2 donor chatbot with DynamoDB session memory |
| Blood wastage | Expiry-first inventory allocation, reallocation on cancellation |
| Communication gaps | Bedrock Claude generates personalised messages per donor/context |

---

## Architecture

```
React (Amplify) → API Gateway + Cognito → FastAPI (App Runner)
                                                ↓
                        DynamoDB (5 tables) ← → SageMaker Feature Store
                                                ↓
                        Step Functions Escalation Workflow
                                                ↓
                    Lambda (match → notify → check → feedback)
                                                ↓
                              SES Email / SNS SMS → Donor
                                                ↓
                        Amazon Lex V2 DonorResponseBot
                                                ↓
                        Bedrock Claude (messages + insights)
EventBridge Scheduler → daily demand + expiry cron jobs
CloudWatch + X-Ray → observability
Secrets Manager → credentials
AWS Glue → CSV ETL pipeline
```

---

## Project Structure

```
aiforgood/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI app entry
│   │   ├── config.py                Secrets Manager config
│   │   ├── models/                  Pydantic models (user, request, inventory, notification, session)
│   │   ├── api/v1/                  6 API routers
│   │   ├── services/                Core business logic (9 service modules)
│   │   └── utils/                   haversine.py, blood_compat.py
│   ├── lambdas/                     4 Step Functions Lambda handlers + Lex fulfillment
│   ├── step_functions/              escalation_workflow.json (ASL)
│   ├── lex_bot/                     bot_definition.json + deploy_lex_bot.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── apprunner.yaml
├── frontend/
│   └── src/
│       ├── pages/                   Dashboard, Requests, Donors, Inventory, Insights
│       ├── components/              DemandBarChart, EscalationTimeline, DonorRankTable,
│       │                            InventoryExpiryAlert, DonorChatWidget
│       └── services/api.js          Axios wrapper
└── ml/
    ├── glue_ingest.py               AWS Glue ETL: S3 CSV → DynamoDB
    ├── notebooks/                   EDA, demand forecast, scoring validation
    └── sagemaker/                   Training job + Feature Store setup
```

---

## Setup & Deployment

### 1. Upload Dataset to S3

```bash
aws s3 mb s3://bloodbridge-data --region ap-south-1
aws s3 cp /path/to/Dataset.csv s3://bloodbridge-data/data/Dataset.csv
```

### 2. Run Glue ETL (creates all 5 DynamoDB tables + loads data)

```bash
# Create Glue job with ml/glue_ingest.py
# Set env vars: S3_BUCKET=bloodbridge-data, S3_KEY=data/Dataset.csv
aws glue start-job-run --job-name bloodbridge-csv-ingest
```

### 3. Store Secrets

```bash
aws secretsmanager create-secret --name bloodbridge/config \
  --secret-string '{
    "SES_SENDER_EMAIL": "noreply@yourdomain.com",
    "STEP_FUNCTIONS_ARN": "arn:aws:states:...",
    "BEDROCK_MODEL_ID": "anthropic.claude-sonnet-4-5",
    "LEX_BOT_ID": "...",
    "LEX_BOT_ALIAS_ID": "TSTALIASID"
  }'
```

### 4. Deploy Backend (App Runner)

```bash
cd backend
aws apprunner create-service \
  --service-name bloodbridge-api \
  --source-configuration file://apprunner.yaml
```

### 5. Create Lex Bot

```bash
cd backend/lex_bot
python deploy_lex_bot.py \
  --role-arn arn:aws:iam::ACCT:role/LexRole \
  --fulfillment-lambda arn:aws:lambda:ap-south-1:ACCT:function:bb-lex-fulfillment
```

### 6. Deploy Step Functions

```bash
aws stepfunctions create-state-machine \
  --name BloodBridgeEscalation \
  --type EXPRESS \
  --definition file://backend/step_functions/escalation_workflow.json \
  --role-arn arn:aws:iam::ACCT:role/StepFunctionsRole
```

### 7. Deploy Frontend (Amplify)

```bash
cd frontend
npm run build
# Connect to Amplify Console or:
amplify publish
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/patients/requests` | Create blood request |
| GET | `/api/v1/matching/demand-forecast` | 7-day demand forecast |
| POST | `/api/v1/matching/match` | Trigger Step Functions matching |
| GET | `/api/v1/inventory/summary` | Blood inventory by group |
| GET | `/api/v1/inventory/expiry-alerts` | Units expiring in 5 days |
| GET | `/api/v1/insights/admin-summary` | Bedrock AI weekly summary |
| POST | `/api/v1/insights/outreach-message` | Generate donor message |
| POST | `/api/v1/webhooks/lex-fulfillment` | Lex V2 fulfillment hook |
| POST | `/api/v1/webhooks/donor-response` | Record donor response |

---

## Donor Scoring Formula

```
Score = 30% × Eligibility
      + 25% × Reliability (donations normalized × type multiplier)
      + 20% × Distance (Haversine inverse, clipped 0–100)
      + 15% × Response Rate (calls_to_donations_ratio)
      + 10% × Active Status
```

---

## AI Components

| Service | Usage |
|---|---|
| **Amazon Bedrock** (Claude Sonnet) | Personalised outreach messages, follow-up reminders, admin insights, failure pattern analysis |
| **Amazon Lex V2** | Donor conversational bot: confirm/reschedule/decline/ask. Session memory in DynamoDB |
| **Amazon SageMaker** | GradientBoosting demand forecast model + Feature Store for donor scores |

---

## AWS Services Used

Amplify · Cognito · API Gateway · App Runner · Lambda · Step Functions (Express) ·
DynamoDB · S3 · SES · SNS · SQS · EventBridge · Bedrock · Lex V2 · SageMaker ·
Feature Store · Glue · Secrets Manager · CloudWatch · IAM

---

## Dataset

7034 records across 5 roles: Guest (2420), Emergency Donor (2385), Bridge Donor (2061), Patient (84), Volunteer (83)

Rare blood groups handled: Bombay Blood Group, A2 Negative, A2B Negative (auto-expanded search radius)
