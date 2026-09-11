---
output:
  pdf_document: default
  html_document: default
---

# Software Requirements Specification (SRS)
# Group 6
## Project: IntelliProcess AI

**An Autonomous Accounts Payable Agent with an Intelligent Records Assistant**

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for **IntelliProcess AI**, an integrated enterprise AI platform that combines autonomous accounts payable invoice processing with an intelligent document search assistant. The system is designed as a university capstone project demonstrating modern Agentic AI architecture on AWS.

### 1.2 Scope

IntelliProcess AI delivers two integrated business capabilities through a unified platform:

1. **AP Invoice Agent** - Autonomous extraction, matching, and approval of vendor invoices
2. **Ask-Your-Records Assistant** - Natural language search and retrieval across organizational documents

Both capabilities share a common document ingestion pipeline, authentication layer, and AI orchestration framework built on AWS managed services.

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|-----------|
| AP | Accounts Payable |
| PO | Purchase Order |
| GR | Goods Receipt |
| RAG | Retrieval Augmented Generation |
| BDA | Bedrock Data Automation |
| LLM | Large Language Model |
| Three-Way Match | Verification of Invoice against PO and Goods Receipt |
| MVP | Minimum Viable Product |

### 1.4 Project Constraints

| Constraint | Detail |
|-----------|--------|
| Timeline | 3 weeks (15 working days) |
| Team | University student team (3-5 members) |
| Budget | AWS Free Tier + limited educational credits |
| Environment | AWS Cloud (single region; **deployed in `ap-southeast-2`** — earlier docs reference `us-east-1` as a placeholder in example URLs/ARNs) |
| Authentication | Simplified (API key or Cognito basic) |

---

## 2. Overall Description

### 2.1 Product Perspective

IntelliProcess AI is a greenfield cloud-native application. It does not integrate with existing enterprise ERP systems in the MVP phase. It operates as a standalone demonstration platform with simulated data.

### 2.2 Product Functions (High-Level)

| ID | Function | Priority |
|----|----------|----------|
| F1 | Document Upload & Storage | MVP |
| F2 | Intelligent Document Processing | MVP |
| F3 | Three-Way Matching | MVP |
| F4 | Exception Handling | MVP |
| F5 | Dashboard & Monitoring | MVP |
| F6 | AI Assistant | MVP |
| F7 | Email notifications | Deferred |
| F8 | Multi-tenant support | Deferred |
| F9 | Audit & Compliance Reporting | Deferred |

### 2.3 User Classes

| User Class | Description | Access Level |
|-----------|-------------|-------------|
| AP Clerk | Uploads invoices, reviews exceptions | Standard |
| Finance Manager | Approves escalated invoices, views reports | Elevated |
| General Staff | Searches organizational records | Standard |
| System Administrator | Manages configuration, monitors system | Admin |

### 2.4 Operating Environment

- **Cloud Provider**: AWS (deployed in `ap-southeast-2`)
- **Runtime**: Serverless (Lambda, API Gateway)
- **AI Foundation**: Amazon Bedrock (Claude 3.x models)
- **Document Processing**: Bedrock Data Automation
- **Agent Orchestration**: AWS AgentCore
- **Frontend**: React SPA (hosted on S3 + CloudFront or local dev)
- **API**: REST via API Gateway

### 2.5 Design and Implementation Constraints

1. Must use AWS managed services to minimize operational overhead
2. Serverless-first to stay within budget constraints
3. No on-premises components
4. English language only for MVP
5. PDF and image invoice formats supported (PNG, JPEG, PDF)
6. Maximum document size: 10MB
7. Maximum concurrent users for demo: 10

### 2.6 Assumptions and Dependencies

**Assumptions:**
- AWS educational credits are available (~$100-200)
- Team has basic AWS knowledge (IAM, Lambda, S3)
- Sample invoices and PO data will be generated/simulated
- Internet connectivity available for all development and demo

**Dependencies:**
- Amazon Bedrock model access (Claude 3 Sonnet/Haiku)
- Bedrock Data Automation availability in the deployment region (`ap-southeast-2`)
- AWS AgentCore GA availability
- Bedrock Knowledge Bases for RAG

---

## 3. External Interface Requirements

### 3.1 User Interfaces

| Interface | Type | Description |
|-----------|------|-------------|
| Web Dashboard | React SPA | Invoice processing status, upload, search |
| Chat Interface | Embedded widget | Natural language records assistant |
| File Upload | Drag-and-drop | Invoice and document upload |

### 3.2 Hardware Interfaces

None - fully cloud-hosted.

### 3.3 Software Interfaces

| System | Interface Type | Purpose |
|--------|---------------|---------|
| Amazon Bedrock | AWS SDK | LLM inference, embeddings |
| Bedrock Data Automation | AWS SDK | Document extraction |
| S3 | AWS SDK | Document storage |
| DynamoDB | AWS SDK | Metadata and state storage |
| API Gateway | REST | Client-server communication |

### 3.4 Communication Interfaces

- HTTPS (TLS 1.2+) for all API calls
- WebSocket (optional) for real-time processing updates
- JSON request/response format

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Target (MVP) |
|--------|-------------|
| Invoice extraction time | < 30 seconds |
| Search response time | < 10 seconds |
| API response time (non-AI) | < 2 seconds |
| Concurrent users | 10 |

### 4.2 Security

| Requirement | Implementation |
|-------------|---------------|
| Authentication | API Key or Amazon Cognito (basic) |
| Authorization | Role-based (AP Clerk, Manager, Staff) |
| Data encryption at rest | S3 SSE, DynamoDB encryption |
| Data encryption in transit | TLS 1.2+ |
| Input validation | All API inputs validated |

### 4.3 Reliability

| Metric | Target |
|--------|--------|
| Availability | 99% (demo environment) |
| Data durability | S3 standard (99.999999999%) |
| Error handling | Graceful degradation with user feedback |

### 4.4 Scalability

Not a primary concern for MVP. The serverless architecture inherently supports scaling, but no load testing or optimization is required for the capstone demonstration.

### 4.5 Maintainability

- Infrastructure as Code (AWS SAM or CDK)
- Centralized logging (CloudWatch)
- Modular code structure with clear separation of concerns

---

## 5. MVP Boundary Definition

### 5.1 In Scope (3-Week Delivery)

- Single-tenant application
- 5-10 sample invoices for demonstration
- 20-50 sample organizational documents for RAG
- 3-5 sample Purchase Orders and Goods Receipts
- Basic web UI (functional, not polished)
- Core AI extraction and matching logic
- Natural language search with citations
- Simple approval rules (amount thresholds)
- CloudWatch logging

### 5.2 Explicitly Deferred

| Feature | Reason |
|---------|--------|
| Multi-tenant architecture | Complexity exceeds timeline |
| Email/SMS notifications | Nice-to-have, not core |
| Advanced exception workflows | Requires complex state machines |
| Integration with real ERP | No access to production systems |
| User management UI | Use AWS Console/Cognito directly |
| Mobile responsive design | Desktop-only for demo |
| Advanced analytics/reporting | Focus on core AI capabilities |
| Document versioning | Adds storage complexity |
| Batch invoice processing | Single invoice flow for MVP |
| Multi-language support | English only |

---

## 6. Document Revision History

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | 2026-07-27 | Capstone Team | Initial SRS |
| 1.1 | 2026-07-31 | Capstone Team | Revised Product Functions |
