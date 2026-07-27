# Deployment Architecture

## IntelliProcess AI Platform

---

## 1. Deployment Overview

### 1.1 Deployment Strategy

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Model | Serverless (no servers to manage) | Zero ops overhead for students |
| IaC Tool | AWS SAM | Simpler than CDK for Lambda-focused apps |
| Environments | Single (dev/demo) | One environment sufficient for capstone |
| Region | us-east-1 | All required services available |
| CI/CD | Manual deploy via SAM CLI | GitHub Actions optional if time permits |
| Frontend Hosting | S3 (or localhost for demo) | Simplest static hosting |

### 1.2 Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AWS Account (us-east-1)                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CloudFormation Stack                           │   │
│  │                    (intelliprocess-dev)                           │   │
│  │                                                                  │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐  │   │
│  │  │  S3      │  │ API Gateway  │  │  Lambda Functions (4)   │  │   │
│  │  │  Bucket  │  │  (REST API)  │  │  + Shared Layer         │  │   │
│  │  └──────────┘  └──────────────┘  └─────────────────────────┘  │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  DynamoDB Tables (5)                                      │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                                  │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐  │   │
│  │  │ Cognito  │  │  IAM Roles   │  │  CloudWatch Logs        │  │   │
│  │  │ User Pool│  │  (4 roles)   │  │  (auto-created)         │  │   │
│  │  └──────────┘  └──────────────┘  └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Manually Configured Resources                       │   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────────┐  │   │
│  │  │ Bedrock KB   │  │ BDA Project   │  │ Bedrock Guardrails │  │   │
│  │  │ + OpenSearch  │  │ + Blueprint   │  │                    │  │   │
│  │  └──────────────┘  └───────────────┘  └────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Frontend (Choose One)                                │   │
│  │                                                                  │   │
│  │  Option A: S3 Static Website + CloudFront                       │   │
│  │  Option B: localhost:5173 (Vite dev server for demo)            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```


---

## 2. AWS SAM Template (Complete)

### 2.1 template.yaml

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: IntelliProcess AI Platform - AP Invoice Agent & Records Assistant

Parameters:
  Stage:
    Type: String
    Default: dev
    AllowedValues: [dev, prod]
  
  KnowledgeBaseId:
    Type: String
    Description: Bedrock Knowledge Base ID (created manually)
    Default: "PLACEHOLDER"
  
  BDAProjectArn:
    Type: String
    Description: Bedrock Data Automation project ARN
    Default: "PLACEHOLDER"
  
  GuardrailId:
    Type: String
    Description: Bedrock Guardrails ID
    Default: "PLACEHOLDER"

Globals:
  Function:
    Runtime: python3.12
    Architectures: [x86_64]
    Environment:
      Variables:
        STAGE: !Ref Stage
        DOCUMENT_BUCKET: !Ref DocumentsBucket
        INVOICE_TABLE: !Ref InvoicesTable
        PO_TABLE: !Ref PurchaseOrdersTable
        GR_TABLE: !Ref GoodsReceiptsTable
        CONVERSATION_TABLE: !Ref ConversationsTable
        DOCUMENT_TABLE: !Ref DocumentsTable
        KNOWLEDGE_BASE_ID: !Ref KnowledgeBaseId
        BDA_PROJECT_ARN: !Ref BDAProjectArn
        GUARDRAIL_ID: !Ref GuardrailId
        BEDROCK_MODEL_ID: "anthropic.claude-3-sonnet-20240229-v1:0"
        LOG_LEVEL: "INFO"

Resources:
  # ==================== S3 ====================
  DocumentsBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "intelliprocess-docs-${Stage}-${AWS::AccountId}"
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      CorsConfiguration:
        CorsRules:
          - AllowedHeaders: ['*']
            AllowedMethods: [PUT, POST]
            AllowedOrigins: ['http://localhost:5173', 'http://localhost:3000']
            MaxAge: 3600

  # ==================== DynamoDB ====================
  InvoicesTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-Invoices-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: documentId, AttributeType: S }
        - { AttributeName: status, AttributeType: S }
        - { AttributeName: uploadedBy, AttributeType: S }
        - { AttributeName: uploadedAt, AttributeType: S }
      KeySchema:
        - { AttributeName: documentId, KeyType: HASH }
      GlobalSecondaryIndexes:
        - IndexName: GSI-StatusDate
          KeySchema:
            - { AttributeName: status, KeyType: HASH }
            - { AttributeName: uploadedAt, KeyType: RANGE }
          Projection: { ProjectionType: ALL }
        - IndexName: GSI-UserDate
          KeySchema:
            - { AttributeName: uploadedBy, KeyType: HASH }
            - { AttributeName: uploadedAt, KeyType: RANGE }
          Projection: { ProjectionType: ALL }

  PurchaseOrdersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-PurchaseOrders-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: poNumber, AttributeType: S }
        - { AttributeName: vendorName, AttributeType: S }
        - { AttributeName: createdDate, AttributeType: S }
      KeySchema:
        - { AttributeName: poNumber, KeyType: HASH }
      GlobalSecondaryIndexes:
        - IndexName: GSI-VendorDate
          KeySchema:
            - { AttributeName: vendorName, KeyType: HASH }
            - { AttributeName: createdDate, KeyType: RANGE }
          Projection: { ProjectionType: ALL }

  GoodsReceiptsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-GoodsReceipts-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: grId, AttributeType: S }
        - { AttributeName: poNumber, AttributeType: S }
        - { AttributeName: receivedDate, AttributeType: S }
      KeySchema:
        - { AttributeName: grId, KeyType: HASH }
      GlobalSecondaryIndexes:
        - IndexName: GSI-PONumber
          KeySchema:
            - { AttributeName: poNumber, KeyType: HASH }
            - { AttributeName: receivedDate, KeyType: RANGE }
          Projection: { ProjectionType: ALL }

  ConversationsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-Conversations-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: sessionId, AttributeType: S }
        - { AttributeName: timestamp, AttributeType: S }
        - { AttributeName: userId, AttributeType: S }
      KeySchema:
        - { AttributeName: sessionId, KeyType: HASH }
        - { AttributeName: timestamp, KeyType: RANGE }
      GlobalSecondaryIndexes:
        - IndexName: GSI-UserSessions
          KeySchema:
            - { AttributeName: userId, KeyType: HASH }
            - { AttributeName: timestamp, KeyType: RANGE }
          Projection: { ProjectionType: KEYS_ONLY }
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  DocumentsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-Documents-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: documentId, AttributeType: S }
        - { AttributeName: category, AttributeType: S }
        - { AttributeName: uploadedAt, AttributeType: S }
      KeySchema:
        - { AttributeName: documentId, KeyType: HASH }
      GlobalSecondaryIndexes:
        - IndexName: GSI-CategoryDate
          KeySchema:
            - { AttributeName: category, KeyType: HASH }
            - { AttributeName: uploadedAt, KeyType: RANGE }
          Projection: { ProjectionType: ALL }

  # ==================== Cognito ====================
  CognitoUserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub "IntelliProcess-Users-${Stage}"
      AutoVerifiedAttributes: [email]
      UsernameAttributes: [email]
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
          RequireSymbols: false

  CognitoUserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      ClientName: intelliprocess-web
      UserPoolId: !Ref CognitoUserPool
      GenerateSecret: false
      ExplicitAuthFlows:
        - ALLOW_USER_SRP_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH
      SupportedIdentityProviders: [COGNITO]

  CognitoAPClerkGroup:
    Type: AWS::Cognito::UserPoolGroup
    Properties:
      GroupName: AP_CLERK
      UserPoolId: !Ref CognitoUserPool

  CognitoFinanceGroup:
    Type: AWS::Cognito::UserPoolGroup
    Properties:
      GroupName: FINANCE_MANAGER
      UserPoolId: !Ref CognitoUserPool

  CognitoStaffGroup:
    Type: AWS::Cognito::UserPoolGroup
    Properties:
      GroupName: STAFF
      UserPoolId: !Ref CognitoUserPool

  CognitoAdminGroup:
    Type: AWS::Cognito::UserPoolGroup
    Properties:
      GroupName: ADMIN
      UserPoolId: !Ref CognitoUserPool

  # ==================== Lambda Layer ====================
  SharedLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: !Sub "intelliprocess-shared-${Stage}"
      ContentUri: functions/shared/
      CompatibleRuntimes: [python3.12]
      Description: Shared utilities

  # ==================== API Gateway ====================
  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      Name: !Sub "IntelliProcess-API-${Stage}"
      StageName: !Ref Stage
      Auth:
        DefaultAuthorizer: CognitoAuth
        Authorizers:
          CognitoAuth:
            UserPoolArn: !GetAtt CognitoUserPool.Arn
      Cors:
        AllowMethods: "'GET,POST,OPTIONS'"
        AllowHeaders: "'Content-Type,Authorization,X-Correlation-Id'"
        AllowOrigin: "'*'"

  # ==================== Lambda Functions ====================
  UploadHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "intelliprocess-upload-${Stage}"
      Handler: app.lambda_handler
      CodeUri: functions/upload_handler/
      MemorySize: 256
      Timeout: 30
      Layers: [!Ref SharedLayer]
      Policies:
        - S3CrudPolicy: { BucketName: !Ref DocumentsBucket }
        - DynamoDBCrudPolicy: { TableName: !Ref InvoicesTable }
        - DynamoDBCrudPolicy: { TableName: !Ref DocumentsTable }
      Events:
        UploadInvoice:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /invoices/upload
            Method: POST
        UploadDocument:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /documents/upload
            Method: POST

  InvoiceProcessorFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "intelliprocess-processor-${Stage}"
      Handler: app.lambda_handler
      CodeUri: functions/invoice_processor/
      MemorySize: 512
      Timeout: 300
      Layers: [!Ref SharedLayer]
      Policies:
        - S3ReadPolicy: { BucketName: !Ref DocumentsBucket }
        - DynamoDBCrudPolicy: { TableName: !Ref InvoicesTable }
        - DynamoDBReadPolicy: { TableName: !Ref PurchaseOrdersTable }
        - DynamoDBReadPolicy: { TableName: !Ref GoodsReceiptsTable }
        - Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
                - bedrock:InvokeDataAutomationAsync
                - bedrock:GetDataAutomationStatus
              Resource: "*"
      Events:
        S3InvoiceUpload:
          Type: S3
          Properties:
            Bucket: !Ref DocumentsBucket
            Events: s3:ObjectCreated:*
            Filter:
              S3Key:
                Rules:
                  - { Name: prefix, Value: "invoices/" }

  ChatHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "intelliprocess-chat-${Stage}"
      Handler: app.lambda_handler
      CodeUri: functions/chat_handler/
      MemorySize: 256
      Timeout: 60
      Layers: [!Ref SharedLayer]
      Policies:
        - DynamoDBCrudPolicy: { TableName: !Ref ConversationsTable }
        - Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
                - bedrock:Retrieve
                - bedrock:RetrieveAndGenerate
                - bedrock:ApplyGuardrail
              Resource: "*"
      Events:
        Chat:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /chat
            Method: POST
        GetSessions:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /chat/sessions
            Method: GET
        GetSessionHistory:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /chat/sessions/{sessionId}
            Method: GET

  DashboardHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "intelliprocess-dashboard-${Stage}"
      Handler: app.lambda_handler
      CodeUri: functions/dashboard_handler/
      MemorySize: 128
      Timeout: 10
      Layers: [!Ref SharedLayer]
      Policies:
        - DynamoDBReadPolicy: { TableName: !Ref InvoicesTable }
        - DynamoDBCrudPolicy: { TableName: !Ref PurchaseOrdersTable }
        - DynamoDBCrudPolicy: { TableName: !Ref GoodsReceiptsTable }
        - DynamoDBReadPolicy: { TableName: !Ref DocumentsTable }
        - S3ReadPolicy: { BucketName: !Ref DocumentsBucket }
        - Statement:
            - Effect: Allow
              Action: [bedrock:StartIngestionJob]
              Resource: "*"
      Events:
        GetInvoices:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /invoices
            Method: GET
        GetInvoiceDetail:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /invoices/{documentId}
            Method: GET
        ApproveInvoice:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /invoices/{documentId}/approve
            Method: POST
        GetDocuments:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /documents
            Method: GET
        SyncDocuments:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /documents/sync
            Method: POST
        DashboardStats:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /dashboard/stats
            Method: GET
        SeedData:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /admin/seed-data
            Method: POST

Outputs:
  ApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub "https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/${Stage}"
  
  BucketName:
    Description: S3 document bucket name
    Value: !Ref DocumentsBucket
  
  UserPoolId:
    Description: Cognito User Pool ID
    Value: !Ref CognitoUserPool
  
  UserPoolClientId:
    Description: Cognito App Client ID
    Value: !Ref CognitoUserPoolClient
```


---

## 3. Deployment Commands

### 3.1 First-Time Setup

```bash
# 1. Install prerequisites
pip install aws-sam-cli
npm install -g aws-cdk  # Only if using CDK alternative

# 2. Configure AWS CLI
aws configure
# Region: us-east-1
# Output: json

# 3. Build the SAM application
cd backend
sam build

# 4. Deploy with guided setup (first time)
sam deploy --guided
# Stack name: intelliprocess-dev
# Region: us-east-1
# Confirm changes: Y
# Allow SAM to create IAM roles: Y
# Save arguments to samconfig.toml: Y

# 5. Note the outputs (API URL, Cognito IDs)
# Update frontend .env.local with these values
```

### 3.2 Subsequent Deployments

```bash
# Build and deploy (uses saved samconfig.toml)
cd backend
sam build && sam deploy

# Deploy only if template changed
sam build && sam deploy --no-confirm-changeset
```

### 3.3 Frontend Deployment

```bash
# Option A: Local development (for demo)
cd frontend
npm install
npm run dev  # Runs on localhost:5173

# Option B: Deploy to S3 (production-like)
cd frontend
npm run build
aws s3 sync dist/ s3://intelliprocess-frontend-dev/ --delete
```

### 3.4 Post-Deploy Manual Steps

```bash
# 1. Create test users in Cognito
aws cognito-idp admin-create-user \
  --user-pool-id <pool-id> \
  --username clerk@demo.com \
  --temporary-password TempPass1! \
  --user-attributes Name=email,Value=clerk@demo.com

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <pool-id> \
  --username clerk@demo.com \
  --group-name AP_CLERK

# 2. Seed sample data
python scripts/seed_data.py

# 3. Upload sample records and sync KB
python scripts/upload_sample_records.py
python scripts/sync_knowledge_base.py

# 4. Verify deployment
curl -s https://<api-url>/invoices -H "Authorization: Bearer <token>"
```

---

## 4. Environment Configuration

### 4.1 samconfig.toml

```toml
[default.deploy.parameters]
stack_name = "intelliprocess-dev"
resolve_s3 = true
s3_prefix = "intelliprocess-dev"
region = "us-east-1"
confirm_changeset = false
capabilities = "CAPABILITY_IAM CAPABILITY_AUTO_EXPAND"
parameter_overrides = "Stage=dev KnowledgeBaseId=XXXXXXXXXX BDAProjectArn=arn:aws:bedrock:... GuardrailId=XXXXXXXXXX"
```

### 4.2 Frontend .env.local

```bash
VITE_API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev
VITE_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_AWS_REGION=us-east-1
VITE_IDENTITY_POOL_ID=  # Optional, not needed for basic auth
```

---

## 5. Infrastructure Diagram (AWS Perspective)

```
┌─────────────────────────────────────────────────────────────────┐
│  CloudFormation Stack: intelliprocess-dev                         │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  API Gateway (REST)                                        │  │
│  │  Endpoint: https://xxx.execute-api.us-east-1.amazonaws.com │  │
│  │  Stage: dev                                                │  │
│  │  Authorizer: Cognito JWT                                   │  │
│  │                                                            │  │
│  │  Routes:                                                   │  │
│  │  POST /invoices/upload    → UploadHandler                  │  │
│  │  GET  /invoices           → DashboardHandler               │  │
│  │  GET  /invoices/{id}      → DashboardHandler               │  │
│  │  POST /invoices/{id}/approve → DashboardHandler            │  │
│  │  POST /documents/upload   → UploadHandler                  │  │
│  │  GET  /documents          → DashboardHandler               │  │
│  │  POST /documents/sync     → DashboardHandler               │  │
│  │  POST /chat               → ChatHandler                    │  │
│  │  GET  /chat/sessions      → ChatHandler                    │  │
│  │  GET  /chat/sessions/{id} → ChatHandler                    │  │
│  │  GET  /dashboard/stats    → DashboardHandler               │  │
│  │  POST /admin/seed-data    → DashboardHandler               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │Upload      │ │Invoice     │ │Chat        │ │Dashboard   │  │
│  │Handler     │ │Processor   │ │Handler     │ │Handler     │  │
│  │256MB/30s   │ │512MB/300s  │ │256MB/60s   │ │128MB/10s   │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │
│         All reference: SharedLayer (intelliprocess-shared)       │
│                                                                  │
│  S3: intelliprocess-docs-dev-{accountId}                        │
│  DynamoDB: 5 tables (on-demand, encrypted)                      │
│  Cognito: IntelliProcess-Users-dev (4 groups)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Monitoring and Observability

### 6.1 CloudWatch Log Groups (Auto-Created)

| Log Group | Retention | Source |
|-----------|-----------|--------|
| /aws/lambda/intelliprocess-upload-dev | 30 days | UploadHandler |
| /aws/lambda/intelliprocess-processor-dev | 30 days | InvoiceProcessor |
| /aws/lambda/intelliprocess-chat-dev | 30 days | ChatHandler |
| /aws/lambda/intelliprocess-dashboard-dev | 30 days | DashboardHandler |
| /aws/apigateway/IntelliProcess-API-dev | 30 days | API Gateway access logs |

### 6.2 Key CloudWatch Metrics

| Metric | Source | Alarm Threshold |
|--------|--------|----------------|
| Lambda Errors | AWS/Lambda | > 5 errors in 5 min |
| Lambda Duration | AWS/Lambda | > 280s (processor) |
| API Gateway 5xx | AWS/ApiGateway | > 10 in 5 min |
| API Gateway 4xx | AWS/ApiGateway | Monitoring only |
| DynamoDB ThrottleCount | AWS/DynamoDB | > 0 (should never throttle) |

### 6.3 Troubleshooting Commands

```bash
# View recent Lambda logs
aws logs tail /aws/lambda/intelliprocess-processor-dev --follow

# View specific invocation
aws logs filter-log-events \
  --log-group-name /aws/lambda/intelliprocess-processor-dev \
  --filter-pattern "documentId"

# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=intelliprocess-processor-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

---

## 7. Rollback Strategy

### 7.1 SAM Rollback

```bash
# CloudFormation auto-rolls back on deployment failure

# Manual rollback to previous version:
aws cloudformation rollback-stack --stack-name intelliprocess-dev

# Or deploy a specific previous version:
git checkout <previous-commit>
cd backend && sam build && sam deploy
```

### 7.2 Data Safety

| Resource | Deletion Policy | Rationale |
|----------|----------------|-----------|
| S3 Bucket | Retain | Don't lose uploaded documents |
| DynamoDB Tables | Retain | Don't lose processing data |
| Cognito Pool | Retain | Don't lose user accounts |
| Lambda Functions | Delete (recreate on deploy) | Stateless, code in Git |
| API Gateway | Delete (recreate on deploy) | Stateless config |

```yaml
# In SAM template - protect data resources
DocumentsBucket:
  Type: AWS::S3::Bucket
  DeletionPolicy: Retain
  
InvoicesTable:
  Type: AWS::DynamoDB::Table
  DeletionPolicy: Retain
```

---

## 8. Security Hardening

### 8.1 IAM Least Privilege

Each Lambda function has its own IAM role with only the permissions it needs:

| Function | S3 | DynamoDB | Bedrock |
|----------|----|---------|---------| 
| UploadHandler | PutObject, GetObject | PutItem (Invoices, Documents) | None |
| InvoiceProcessor | GetObject | CRUD (Invoices), Read (PO, GR) | InvokeModel, BDA |
| ChatHandler | None | CRUD (Conversations) | Retrieve, RetrieveAndGenerate |
| DashboardHandler | GetObject | Read (All tables), Write (PO, GR) | StartIngestionJob |

### 8.2 Network Security

- No VPC required (all managed services accessed via AWS endpoints)
- All traffic is HTTPS (TLS 1.2+)
- S3 public access blocked
- API Gateway throttling enabled
- Cognito handles brute-force protection

---

## 9. Cleanup Script

```bash
#!/bin/bash
# scripts/cleanup.sh - Remove all deployed resources
# WARNING: This deletes everything including data!

echo "This will DELETE all IntelliProcess resources. Are you sure? (yes/no)"
read confirmation
if [ "$confirmation" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Empty S3 bucket (required before stack deletion)
aws s3 rm s3://intelliprocess-docs-dev-$(aws sts get-caller-identity --query Account --output text) --recursive

# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name intelliprocess-dev
aws cloudformation wait stack-delete-complete --stack-name intelliprocess-dev

# Delete manually-created resources
echo "Remember to manually delete:"
echo "  - Bedrock Knowledge Base"
echo "  - BDA Project"
echo "  - Bedrock Guardrails"
echo "  - OpenSearch Serverless collection (if not auto-deleted with KB)"

echo "Cleanup complete."
```

---

## 10. Deployment Checklist

### Pre-Deployment

- [ ] AWS CLI configured with correct credentials
- [ ] SAM CLI installed (v1.100+)
- [ ] Python 3.12 available locally
- [ ] Node.js 18+ installed (for frontend)
- [ ] Bedrock model access enabled in console
- [ ] sufficient AWS credits available

### Deployment Steps

- [ ] `sam build` succeeds without errors
- [ ] `sam deploy` completes (stack CREATE_COMPLETE)
- [ ] Note API URL from stack outputs
- [ ] Create Bedrock Knowledge Base (console)
- [ ] Create BDA project + blueprint (console)
- [ ] Create Guardrails (console)
- [ ] Update samconfig.toml with KB/BDA/Guardrail IDs
- [ ] Re-deploy with updated parameters: `sam deploy`
- [ ] Create Cognito test users (4 roles)
- [ ] Run seed_data.py (POs and GRs)
- [ ] Upload sample records to S3 /records/
- [ ] Trigger KB sync
- [ ] Update frontend .env.local
- [ ] Test: login → upload → verify extraction
- [ ] Test: ask chat question → verify answer

### Post-Deployment Verification

- [ ] All Lambda functions show in console
- [ ] API Gateway test from console works
- [ ] CloudWatch logs appearing
- [ ] S3 bucket accessible (via presigned URL only)
- [ ] DynamoDB tables have seed data
