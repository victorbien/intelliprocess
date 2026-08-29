# Requirements Document

## Introduction

The Assistant Insights feature extends the existing IntelliProcess Records Assistant in two areas. Part A adds supplier analytics capabilities: three new agent tools that rank and compare suppliers, plus grouped preset question chips in the chat empty state so users can launch common queries with one click. Part B adds conversation continuity: when a user closes the chat drawer, the system generates and stores an AI summary of the conversation; when the user returns, the assistant offers to resume the last conversation and presents a collapsible summary card that can expand into the full message history.

This feature builds on the already-implemented ai-assistant spec (Strands single-agent architecture, SSE streaming, BedrockService with model invocation for summarization, and CONVERSATION_TABLE persistence). Product-level analysis is out of scope. All code and content are English only.

## Glossary

- **Records_Assistant**: The IntelliProcess conversational agent that answers user questions about invoices, purchase orders, goods receipts, and organizational documents.
- **Analytics_Tool**: A Python function in `tools.py`, registered with the Strands agent in `agent.py`, that performs supplier analytics over stored records.
- **Supplier**: A vendor identified by the `vendorName` field on invoice records.
- **Invoice_Amount**: The `extraction.totalAmount` value on an invoice record.
- **Line_Item_Unit_Price**: The `unitPrice` value within an entry of `extraction.lineItems` on an invoice record.
- **Match_Result**: The `matchResult` map on an invoice record, containing `poMatch` and `grMatch` sub-objects used to evaluate order accuracy.
- **Preset_Question_Group**: A labeled cluster of predefined chat questions displayed in the chat empty state, with a heading and one or more question buttons listed vertically beneath it.
- **Chat_Drawer**: The frontend chat panel opened from the global FloatingChatButton.
- **Conversation_Summary**: An AI-generated textual summary of a chat session, produced by BedrockService and stored in CONVERSATION_TABLE.
- **Summary_Card**: A frontend element shown at the top of the chat that displays the Conversation_Summary with an expander to load the full message history.
- **Conversation_Table**: The DynamoDB table (CONVERSATION_TABLE) that stores chat turns and conversation summaries.
- **Session_Id**: The unique identifier for a chat session.

## Requirements

### Requirement 1

**User Story:** As an accounts payable analyst, I want to see the top suppliers ranked by spend and order volume, so that I can identify the vendors that account for the most business.

#### Acceptance Criteria

1. WHEN the Records_Assistant invokes the `top_suppliers` Analytics_Tool, THE Analytics_Tool SHALL return at most 10 Suppliers ranked in descending order by total Invoice_Amount.
2. THE `top_suppliers` Analytics_Tool SHALL include, for each returned Supplier, the total Invoice_Amount and the count of invoices associated with that Supplier.
3. WHERE an invoice has no `extraction` block, THE `top_suppliers` Analytics_Tool SHALL exclude that invoice from Supplier totals.
4. IF no invoices contain Supplier data, THEN THE `top_suppliers` Analytics_Tool SHALL return an empty ranked list with a count of 0.

### Requirement 2

**User Story:** As an accounts payable analyst, I want to see which suppliers have the best order accuracy, so that I can assess vendor reliability against purchase orders and goods receipts.

#### Acceptance Criteria

1. WHEN the Records_Assistant invokes the `supplier_order_accuracy` Analytics_Tool, THE Analytics_Tool SHALL return at most 10 Suppliers ranked in descending order by match rate.
2. THE `supplier_order_accuracy` Analytics_Tool SHALL compute the match rate for each Supplier from the `poMatch` and `grMatch` values within Match_Result.
3. THE `supplier_order_accuracy` Analytics_Tool SHALL include, for each returned Supplier, the match rate and the number of invoices evaluated for that Supplier.
4. WHERE an invoice has no Match_Result, THE `supplier_order_accuracy` Analytics_Tool SHALL exclude that invoice from the Supplier match-rate calculation.
5. IF no invoices contain Match_Result data, THEN THE `supplier_order_accuracy` Analytics_Tool SHALL return an empty ranked list with a count of 0.

### Requirement 3

**User Story:** As an accounts payable analyst, I want to compare suppliers by their average prices, so that I can find the lowest-cost vendors.

#### Acceptance Criteria

1. WHEN the Records_Assistant invokes the `supplier_lowest_prices` Analytics_Tool, THE Analytics_Tool SHALL return the average Invoice_Amount per Supplier.
2. WHEN the Records_Assistant invokes the `supplier_lowest_prices` Analytics_Tool, THE Analytics_Tool SHALL return the average Line_Item_Unit_Price per Supplier.
3. THE `supplier_lowest_prices` Analytics_Tool SHALL return both the average Invoice_Amount per Supplier and the average Line_Item_Unit_Price per Supplier within a single response.
4. WHERE an invoice has no `extraction` block, THE `supplier_lowest_prices` Analytics_Tool SHALL exclude that invoice from the average calculations.
5. IF a Supplier has no line items across all invoices, THEN THE `supplier_lowest_prices` Analytics_Tool SHALL report that Supplier's average Line_Item_Unit_Price as null.

### Requirement 4

**User Story:** As a developer, I want the new supplier analytics tools registered with the agent, so that the Records_Assistant can invoke them during conversations.

#### Acceptance Criteria

1. THE Records_Assistant SHALL register the `top_suppliers`, `supplier_order_accuracy`, and `supplier_lowest_prices` Analytics_Tools in `agent.py`.
2. WHEN the Records_Assistant selects a supplier analytics tool for a user question, THE Records_Assistant SHALL return the tool result formatted as a conversational answer.
3. THE Analytics_Tools SHALL convert all Decimal values to JSON-serializable numeric types before returning results.

### Requirement 5

**User Story:** As a chat user, I want grouped preset question chips in the empty chat state, so that I can quickly launch common supplier and invoice queries.

#### Acceptance Criteria

1. WHILE the chat message list is empty, THE Chat_Drawer SHALL display Preset_Question_Groups.
2. THE Chat_Drawer SHALL render each Preset_Question_Group with a heading and its question buttons listed vertically beneath the heading.
3. WHEN a user selects a preset question button, THE Chat_Drawer SHALL submit the text of that button as a chat question.
4. THE Chat_Drawer SHALL include a Preset_Question_Group labeled "Suppliers" and a Preset_Question_Group labeled "Invoices".

### Requirement 6

**User Story:** As a chat user, I want the assistant to summarize my conversation when I close the chat, so that I can review what was discussed when I return.

#### Acceptance Criteria

1. WHEN a user closes the Chat_Drawer, THE Chat_Drawer SHALL send a request to `POST /chat/sessions/{id}/summary` for the active Session_Id.
2. WHEN the summary endpoint receives a request, THE Records_Assistant SHALL generate a Conversation_Summary of the session using BedrockService model invocation.
3. WHEN a Conversation_Summary is generated, THE Records_Assistant SHALL store the Conversation_Summary in Conversation_Table associated with the Session_Id.
4. IF the active session contains no messages, THEN THE Chat_Drawer SHALL skip the summary request.
5. IF Conversation_Summary generation fails, THEN THE Records_Assistant SHALL return an error response and SHALL leave existing conversation turns in Conversation_Table unchanged.

### Requirement 7

**User Story:** As a returning chat user, I want to see a summary of my last conversation with an option to resume it, so that I can continue where I left off without re-reading everything.

#### Acceptance Criteria

1. WHEN a user opens the Chat_Drawer and a stored Conversation_Summary exists for the last session, THE Chat_Drawer SHALL display the resume prompt "Hello! Do you want to continue the last conversation?".
2. WHEN a stored Conversation_Summary exists for the last session, THE Chat_Drawer SHALL display a Summary_Card at the top of the chat showing the Conversation_Summary.
3. THE Summary_Card SHALL display the Conversation_Summary by default with the full message history collapsed.
4. WHEN a user activates the "view full history" expander on the Summary_Card, THE Chat_Drawer SHALL load the full message history via `GET /chat/sessions/{id}`.
5. THE FloatingChatButton SHALL make the Chat_Drawer available on every application page.
