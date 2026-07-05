# BaladiGuard MVP Tech Stack

This document lists the agreed MVP technology choices only.

## Frontend

| Area | Choice |
|---|---|
| Mobile app | React Native with Expo |
| Language | TypeScript |
| Navigation | Expo Router |
| UI components | React Native Paper |
| Forms | React Hook Form |
| Validation | Zod |
| HTTP client | Native `fetch` |

## Backend

| Area | Choice |
|---|---|
| API framework | FastAPI |
| Language | Python 3.11+ |
| Validation | Pydantic |
| ASGI server | Uvicorn |
| Testing | Pytest |

## Database

| Area | Choice |
|---|---|
| MVP database | Amazon DynamoDB |
| Local development | DynamoDB Local (Docker) |
| Unit tests | In-memory ticket store (`DATABASE_BACKEND=memory`) |
| Migrations | Idempotent boto3 scripts in `backend/scripts/db/` |

## Storage

| Area | Choice |
|---|---|
| Report images | Amazon S3 |
| Image reference stored in API | S3 object key string, exposed as `imageObjectKey` |

## AI Services

| Area | Choice |
|---|---|
| Text classification and cleanup | Amazon Bedrock |
| Image analysis support | Amazon Rekognition |
| Agent-style workflow support | Amazon Bedrock Agents, when needed in later tickets |

## Location Services

| Area | Choice |
|---|---|
| Maps, geocoding, and location validation | Amazon Location Service |
| MVP location input | Typed address or placeholder/sample location from mobile UI |

## Authentication

| Area | Choice |
|---|---|
| User authentication | Amazon Cognito |

## Deployment

| Area | Choice |
|---|---|
| API hosting | AWS Lambda behind Amazon API Gateway |
| Media storage | Amazon S3 |
| Logs and monitoring | Amazon CloudWatch |
| Notifications | Amazon SNS and/or Amazon SES |
