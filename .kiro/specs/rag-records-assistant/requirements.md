# Requirements Document

## Module 3: RAG Records Assistant

## Introduction

The RAG Records Assistant extends the IntelliProcess AI platform with an intelligent conversational interface that answers natural language questions about organizational records. The assistant routes each query to the appropriate data source — the Bedrock Knowledge Base for unstructured documents (policies, contracts, procurement guidelines), DynamoDB for structured financial data (invoice counts, totals, PO status), or both for hybrid questions that span the two domains.

The assistant is exposed as a floating widget (bottom-right icon + side drawer) that persists across all pages of the application — it is not a standalone page. The chat endpoint (`POST /chat`) already exists in the API; this module extends it with intent classification and routing while keeping the response shape backward-compatible.

Because Bedrock Knowledge Base is unavailable in the local development environment, the structured-data (DynamoDB) path must be fully functional with mocked AWS services before the document-search path is enabled. Bedrock KB integration is layered on top once available.

---

## Glossary

- **Assistant**: The RAG Records Assistant — the AI component that receives user questions and returns answers.
- **ChatRouter**: The backend service responsible for classifying query intent and dispatching to the correct handler.
- **IntentClassifier**: The component that determines whether a question is `document_search`, `structured_query`, or `hybrid`.
- **DocumentSearchHandler**: The handler that retrieves answers from the Bedrock Knowledge Base.
- **StructuredQueryHandler**: The handler that queries DynamoDB tables (invoices, POs, GRs) and synthesizes a natural language answer.
- **HybridHandler**: The handler that invokes both DocumentSearchHandler and StructuredQueryHandler and merges their results.
- **FloatingWidget**: The persistent UI element (bottom-right icon + collapsible side drawer) that hosts the chat interface.
- **Session**: A conversation context identified by a `sessionId`, stored in the `CONVERSATION_TABLE`.
- **Citation**: A reference to the source document from which an answer was derived (applies to document search results).
- **Bedrock KB**: Amazon Bedrock Knowledge Base — the vector search index over organizational PDF/DOCX/TXT documents stored in S3.
- **CONVERSATION_TABLE**: DynamoDB table (`IntelliProcess-Conversations`) keyed on `sessionId` + `timestamp`.
- **INVOICE_TABLE**: DynamoDB table (`IntelliProcess-Invoices`) containing invoice metadata and extraction results.
- **PO_TABLE**: DynamoDB table (`IntelliProcess-POs`) containing purchase order records.
- **GR_TABLE**: DynamoDB table (`IntelliProcess-GRs`) containing goods receipt records.
- **DOCUMENT_TABLE**: DynamoDB table (`IntelliProcess-Documents`) containing organizational document metadata.
- **kbSyncStatus**: Field on a document record indicating whether the document has been ingested into the Bedrock KB (`SYNCED`, `PENDING`, `FAILED`).

---

## Requirements

---

### Requirement 1: Intent Classification

**User Story:** As a user, I want the assistant to understand what kind of question I am asking, so that the correct data source is queried and I receive an accurate answer.

#### Acceptance Criteria

1. WHEN a chat request is received, THE IntentClassifier SHALL classify the question into exactly one of three intent categories: `document_search`, `structured_query`, or `hybrid`.
2. THE IntentClassifier SHALL treat questions about policies, contracts, procedures, guidelines, and document content as `document_search` intent.
3. THE IntentClassifier SHALL treat questions about invoice counts, amounts, statuses, totals, and PO/GR data as `structured_query` intent.
4. THE IntentClassifier SHALL treat questions that require both document content and transactional data as `hybrid` intent.
5. WHEN the IntentClassifier cannot determine intent with sufficient confidence, THE IntentClassifier SHALL default to `document_search` intent.
6. THE IntentClassifier SHALL resolve intent using a prompt-based LLM call to Amazon Bedrock Claude 3 Haiku.
7. WHERE Bedrock is unavailable (local development), THE IntentClassifier SHALL apply keyword-based heuristics to classify intent without an LLM call.
8. THE ChatRouter SHALL log the resolved intent and the confidence level for each request to structured application logs.

---

### Requirement 2: Structured Query Handler (DynamoDB Path)

**User Story:** As a Finance Manager or AP Clerk, I want to ask questions like "how many invoices are pending approval?" and receive an accurate answer sourced from live data, so that I do not need to navigate to the invoice list to get a count.

#### Acceptance Criteria

1. WHEN the resolved intent is `structured_query`, THE ChatRouter SHALL delegate the question to the StructuredQueryHandler.
2. THE StructuredQueryHandler SHALL query the INVOICE_TABLE, PO_TABLE, and GR_TABLE as needed to answer the question.
3. WHEN querying the INVOICE_TABLE, THE StructuredQueryHandler SHALL use the existing `GSI-StatusDate` index for status-filtered queries and the `GSI-UserDate` index for user-scoped queries.
4. THE StructuredQueryHandler SHALL support at minimum the following query patterns:
   - Invoice count by status (e.g., "how many invoices are ESCALATED?")
   - Invoice total amount by status or vendor
   - Invoice list by vendor name
   - PO status lookup by PO number
   - Goods receipt confirmation for a given PO
5. THE StructuredQueryHandler SHALL synthesize the raw DynamoDB results into a natural language answer using an LLM call.
6. WHERE Bedrock is unavailable (local development), THE StructuredQueryHandler SHALL format the raw DynamoDB results into a human-readable response without an LLM synthesis call.
7. THE StructuredQueryHandler SHALL return answers that include a `sourceType` field set to `"structured"` and a `dataSnapshot` containing the key figures used to generate the answer.
8. IF the DynamoDB query returns zero results, THEN THE StructuredQueryHandler SHALL return a natural language response stating that no matching records were found, rather than an empty answer.
9. WHILE processing a structured query, THE StructuredQueryHandler SHALL respect the authenticated user's role: AP Clerks SHALL only see their own invoices; Finance Managers and Admins SHALL see all invoices.

---

### Requirement 3: Document Search Handler (Bedrock KB Path)

**User Story:** As a General Staff member or Finance Manager, I want to ask questions about policies, contracts, and procedures, so that I can find answers without manually searching through PDF documents.

#### Acceptance Criteria

1. WHEN the resolved intent is `document_search`, THE ChatRouter SHALL delegate the question to the DocumentSearchHandler.
2. THE DocumentSearchHandler SHALL call the Bedrock Knowledge Base `retrieve_and_generate` API to retrieve relevant passages and generate an answer.
3. THE DocumentSearchHandler SHALL apply the `categoryFilter` parameter from the request to narrow the KB search to a specific document category, when provided.
4. THE DocumentSearchHandler SHALL include citations in the response, where each citation contains: `documentName`, `documentId`, `pageNumber` (if available), `relevanceScore`, and a `snippet` of the retrieved passage.
5. WHERE Bedrock KB is unavailable (local development), THE DocumentSearchHandler SHALL return a fallback response indicating that document search is unavailable in the current environment, with HTTP status 200 and an `unavailable` flag in the response.
6. IF the Bedrock KB `retrieve_and_generate` call times out after 60 seconds, THEN THE DocumentSearchHandler SHALL return HTTP status 504 with error code `TIMEOUT`.
7. IF the Bedrock KB returns zero relevant passages above the relevance threshold, THEN THE DocumentSearchHandler SHALL return a response stating that no relevant information was found, with an empty `citations` array.
8. THE DocumentSearchHandler SHALL return answers that include a `sourceType` field set to `"documents"`.

---

### Requirement 4: Hybrid Query Handler

**User Story:** As a Finance Manager, I want to ask questions that combine document rules with live data — for example, "does the Acme invoice exceed the travel policy limit?" — so that I can get a single integrated answer without manually cross-referencing systems.

#### Acceptance Criteria

1. WHEN the resolved intent is `hybrid`, THE ChatRouter SHALL delegate the question to the HybridHandler.
2. THE HybridHandler SHALL invoke both the DocumentSearchHandler and the StructuredQueryHandler in parallel.
3. THE HybridHandler SHALL merge the results from both handlers into a single coherent answer using an LLM synthesis call.
4. THE HybridHandler SHALL include all citations from the DocumentSearchHandler in the final response.
5. THE HybridHandler SHALL include the `dataSnapshot` from the StructuredQueryHandler in the final response.
6. THE HybridHandler SHALL return answers that include a `sourceType` field set to `"hybrid"`.
7. IF the DocumentSearchHandler is unavailable (Bedrock KB offline), THEN THE HybridHandler SHALL downgrade to `structured_query` handling and note in the response that document context was unavailable.
8. IF the StructuredQueryHandler returns zero results, THEN THE HybridHandler SHALL return the DocumentSearchHandler result alone, with `sourceType` set to `"documents"`.

---

### Requirement 5: Extended Chat API (POST /chat)

**User Story:** As a frontend developer, I want the `POST /chat` endpoint to support intent routing transparently, so that the frontend does not need to select a data source explicitly and the existing response shape continues to work.

#### Acceptance Criteria

1. THE ChatRouter SHALL accept `POST /chat` requests with the existing request body shape: `{ "question": string, "sessionId": string (optional), "categoryFilter": string (optional) }`.
2. THE ChatRouter SHALL extend the existing response body with two additional optional fields: `sourceType` (`"documents"` | `"structured"` | `"hybrid"`) and `dataSnapshot` (object, present only for `structured_query` and `hybrid` responses).
3. THE ChatRouter SHALL preserve backward compatibility: existing fields (`answer`, `citations`, `sessionId`, `responseTimeMs`) SHALL remain present in all responses.
4. WHEN a request does not include a `sessionId`, THE ChatRouter SHALL generate a new UUID session identifier and return it in the response.
5. THE ChatRouter SHALL require a valid Cognito Bearer token; unauthenticated requests SHALL receive HTTP 401.
6. WHEN the `question` field is empty or exceeds 1000 characters, THE ChatRouter SHALL return HTTP 400 with error code `VALIDATION_ERROR`.
7. THE ChatRouter SHALL write each user turn and assistant turn to the CONVERSATION_TABLE, storing `sessionId`, `userId`, `role`, `content`, `intent`, `timestamp`, and (for assistant turns) `citations` and `sourceType`.
8. THE ChatRouter SHALL include `responseTimeMs` in all successful responses, measured from request receipt to response dispatch.

---

### Requirement 6: Conversation Session Management

**User Story:** As a user, I want my chat history to be preserved across page reloads and widget close/open cycles, so that I can refer back to previous answers without re-asking questions.

#### Acceptance Criteria

1. THE ChatRouter SHALL persist each conversation turn to the CONVERSATION_TABLE using `sessionId` as the partition key and `timestamp` (ISO 8601 UTC) as the sort key.
2. WHEN a `GET /chat/sessions` request is received, THE ChatRouter SHALL return the current user's sessions ordered by most-recent activity, limited to the requested count (default 10, maximum 50).
3. WHEN a `GET /chat/sessions/{sessionId}` request is received, THE ChatRouter SHALL return the full message history for that session in chronological order.
4. WHILE returning session data, THE ChatRouter SHALL enforce ownership: a user SHALL only retrieve sessions where `userId` matches the authenticated user's sub claim.
5. IF a `GET /chat/sessions/{sessionId}` request is made for a session not owned by the requesting user, THEN THE ChatRouter SHALL return HTTP 403.
6. THE ChatRouter SHALL retain conversation records in the CONVERSATION_TABLE for 90 days, after which records MAY be expired using DynamoDB TTL.

---

### Requirement 7: Floating Widget UI Component

**User Story:** As a user, I want a persistent chat widget available on every page of the application, so that I can ask questions without navigating away from my current task.

#### Acceptance Criteria

1. THE FloatingWidget SHALL render as a circular icon button fixed to the bottom-right corner of the viewport at all times, regardless of the current page route.
2. WHEN the user clicks the FloatingWidget icon, THE FloatingWidget SHALL open a side drawer panel anchored to the right edge of the viewport without navigating away from the current page.
3. WHEN the side drawer is open, THE FloatingWidget SHALL display the full chat interface including: message history, a text input field, a send button, and a loading indicator during response generation.
4. THE FloatingWidget SHALL preserve the current session's message history when the drawer is closed and reopened within the same browser session.
5. WHILE a response is being generated, THE FloatingWidget SHALL display a loading indicator and disable the send button to prevent duplicate submissions.
6. WHEN a response includes citations, THE FloatingWidget SHALL render each citation as an expandable reference showing the document name, page number (if available), and snippet.
7. WHEN a response includes a `dataSnapshot`, THE FloatingWidget SHALL render the key figures as a compact summary table or key-value list below the answer text.
8. THE FloatingWidget SHALL be keyboard accessible: focus SHALL move to the input field when the drawer opens, and the drawer SHALL close when the Escape key is pressed.
9. THE FloatingWidget SHALL be visually distinct from the page content using a contrasting accent color and a drop shadow, consistent with the application design system.

---

### Requirement 8: Local Development Fallback

**User Story:** As a developer, I want the RAG Records Assistant to function in the local development environment without a real Bedrock Knowledge Base, so that I can develop and test the structured-query path independently.

#### Acceptance Criteria

1. WHILE the environment variable `STAGE` is set to `dev`, THE IntentClassifier SHALL use keyword-based heuristics instead of a Bedrock LLM call to classify intent.
2. WHILE the environment variable `STAGE` is set to `dev`, THE StructuredQueryHandler SHALL operate against the moto-mocked DynamoDB tables seeded by `dev_mock.py`.
3. WHILE the environment variable `STAGE` is set to `dev` and `BEDROCK_KB_ID` is not set, THE DocumentSearchHandler SHALL return a response with `answer` set to `"Document search is not available in the local development environment."`, `citations` set to `[]`, and `unavailable` set to `true`.
4. THE local fallback behavior SHALL not require any code changes to activate — it SHALL be controlled exclusively by the `STAGE` and `BEDROCK_KB_ID` environment variables.
5. WHEN running under moto mocks, THE StructuredQueryHandler SHALL return accurate counts and totals derived from the seed data in `dev_mock.py`.

---

### Requirement 9: Intent Classification Prompt

**User Story:** As a developer, I want the intent classification logic to be defined in a maintainable prompt, so that routing rules can be updated without changing application code.

#### Acceptance Criteria

1. THE IntentClassifier SHALL use a prompt that instructs the LLM to return a JSON object with the fields `intent` (one of `document_search`, `structured_query`, `hybrid`) and `confidence` (a float between 0.0 and 1.0).
2. THE intent classification prompt SHALL include at minimum three labeled examples for each intent category.
3. THE IntentClassifier SHALL treat any LLM response that cannot be parsed as valid JSON as a classification failure and apply the default `document_search` fallback.
4. THE IntentClassifier SHALL treat any `confidence` value below 0.6 as insufficient and apply the default `document_search` fallback.
5. THE intent classification prompt SHALL be stored as a named constant or loaded from a configuration file, separate from the routing logic code.
6. FOR ALL valid question strings of length between 1 and 1000 characters, THE IntentClassifier SHALL return a non-null intent value (round-trip property: any question input SHALL produce a classifiable output without raising an exception).

---

### Requirement 10: Error Handling and Resilience

**User Story:** As a user, I want to receive a clear, non-technical error message when the assistant encounters a problem, so that I understand what happened and what to do next.

#### Acceptance Criteria

1. IF a DynamoDB query in the StructuredQueryHandler raises a `ClientError`, THEN THE ChatRouter SHALL return HTTP 500 with error code `INTERNAL_ERROR` and a user-facing message of `"An error occurred while retrieving records. Please try again."`.
2. IF the Bedrock API call raises a `ServiceUnavailableException` or `ThrottlingException`, THEN THE ChatRouter SHALL return HTTP 503 with error code `SERVICE_UNAVAILABLE` and a user-facing message of `"The AI service is temporarily unavailable. Please try again in a few seconds."`.
3. IF the Bedrock `retrieve_and_generate` call does not complete within 60 seconds, THEN THE ChatRouter SHALL cancel the request and return HTTP 504 with error code `TIMEOUT`.
4. THE ChatRouter SHALL include the `X-Correlation-Id` header in all error responses so that errors can be traced in CloudWatch Logs.
5. THE ChatRouter SHALL never expose internal exception details, stack traces, or DynamoDB table names in error responses returned to the client.
6. WHEN a handler error occurs, THE ChatRouter SHALL log the full exception with the correlation ID, user ID (redacted sub), intent, and question text (truncated to 200 characters) to structured application logs.

