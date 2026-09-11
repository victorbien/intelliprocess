# AI Agent Design

## IntelliProcess AI Platform

------------------------------------------------------------------------

## 1. Agent Architecture Overview

The platform uses two specialized AI agents orchestrated by AWS
AgentCore. Each agent has distinct responsibilities, tools, and
reasoning patterns.

    ┌─────────────────────────────────────────────────────────────────┐
    │                    AWS AgentCore                                  │
    │                                                                  │
    │  ┌─────────────────────────────┐  ┌───────────────────────────┐│
    │  │   AP Invoice Agent          │  │   Records Search Agent     ││
    │  │                             │  │                           ││
    │  │   Model: Claude 3 Sonnet    │  │   Model: Claude 3 Sonnet  ││
    │  │   Style: Tool-use agent     │  │   Style: RAG agent        ││
    │  │   Tools: 4 custom tools     │  │   Tools: KB Retrieve      ││
    │  │   Memory: None (stateless)  │  │   Memory: Session (5 msg) ││
    │  │                             │  │                           ││
    │  │   Responsibilities:         │  │   Responsibilities:       ││
    │  │   - Invoice field analysis  │  │   - Query understanding   ││
    │  │   - PO/GR matching logic    │  │   - Document retrieval    ││
    │  │   - Approval reasoning      │  │   - Answer synthesis      ││
    │  │   - Escalation decisions    │  │   - Citation assembly     ││
    │  └─────────────────────────────┘  └───────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

### Why Two Agents (Not One)

  ------------------------------------------------------------------------
  Consideration         Single Agent       Two Specialized Agents
  --------------------- ------------------ -------------------------------
  Prompt complexity     Very long, mixed   Focused, shorter prompts
                        concerns           

  Tool surface          5+ tools,          3-4 tools each, clear
                        confusing          

  Testing               Hard to isolate    Test each independently
                        failures           

  Cost                  Every call loads   Lighter per invocation
                        all context        

  Latency               Larger prompt =    Smaller prompt = faster
                        slower             
  ------------------------------------------------------------------------

**Decision**: Two agents. The AP Agent is invoked only during invoice
processing (async). The Records Agent is invoked only during chat
queries (sync). They never need to coordinate in real-time.

------------------------------------------------------------------------

## 2. AP Invoice Agent

### 2.1 Agent Identity

  Property      Value
  ------------- -----------------------------------------------------------
  Name          AP Invoice Processing Agent
  ID            `ap-invoice-agent`
  Model         Claude 3 Sonnet (anthropic.claude-3-sonnet-20240229-v1:0)
  Temperature   0.0 (deterministic for business logic)
  Max Tokens    2048
  Invocation    Asynchronous (from InvoiceProcessor Lambda)
  Timeout       120 seconds

### 2.2 Agent Reasoning Pattern

The AP Agent follows a **sequential tool-use pattern** --- it executes a
predefined workflow rather than free-form reasoning:

    ┌────────────────────────────────────────────────────────────┐
    │                AP Agent Reasoning Loop                       │
    │                                                            │
    │  Input: documentId + extraction results                    │
    │                                                            │
    │  Step 1: Analyze extraction quality                        │
    │           → Check confidence scores                        │
    │           → Identify low-confidence fields                 │
    │                                                            │
    │  Step 2: Call match_purchase_order tool                     │
    │           → Input: PO reference, vendor, amount            │
    │           → Output: PO match result                        │
    │                                                            │
    │  Step 3: Call match_goods_receipt tool                      │
    │           → Input: PO number from Step 2                   │
    │           → Output: GR match result                        │
    │                                                            │
    │  Step 4: Call evaluate_approval_rules tool                  │
    │           → Input: extraction + PO match + GR match        │
    │           → Output: approval decision                      │
    │                                                            │
    │  Step 5: Return structured decision                        │
    │           → APPROVED or ESCALATED with full reasoning      │
    └────────────────────────────────────────────────────────────┘

### 2.3 Tools

#### Tool 1: `match_purchase_order`

  -------------------------------------------------------------------------------------------------------------------------------------
  Property                                  Value
  ----------------------------------------- -------------------------------------------------------------------------------------------
  Description                               Looks up a Purchase Order by number and compares it against invoice data

  Input Schema                              `{ "poNumber": string, "vendorName": string, "invoiceAmount": number }`

  Output                                    `{ "status": "MATCHED|PARTIAL_MATCH|NO_MATCH", "poData": {...}, "discrepancies": [...] }`

  Implementation                            Lambda function querying DynamoDB PO table
  -------------------------------------------------------------------------------------------------------------------------------------

``` python
# tools/match_po.py
def match_purchase_order(po_number: str, vendor_name: str, invoice_amount: float) -> dict:
    """Match invoice against Purchase Order."""
    
    # 1. Exact PO number lookup
    po = dynamo.get_item(TableName=PO_TABLE, Key={"poNumber": po_number})
    
    if not po:
        # 2. Fallback: fuzzy vendor match
        pos = dynamo.query(IndexName="GSI-VendorDate", 
                          KeyConditionExpression="vendorName = :v",
                          ExpressionAttributeValues={":v": vendor_name})
        if not pos:
            return {"status": "NO_MATCH", "reason": "PO not found"}
        po = find_closest_amount(pos, invoice_amount)
    
    # 3. Compare amounts (5% tolerance)
    variance = abs(po["totalAmount"] - invoice_amount) / po["totalAmount"]
    discrepancies = []
    
    if variance > 0.05:
        discrepancies.append(f"Amount variance: {variance*100:.1f}% "
                           f"(PO: ${po['totalAmount']}, Invoice: ${invoice_amount})")
    
    # 4. Compare vendor names (fuzzy)
    if not fuzzy_match(po["vendorName"], vendor_name, threshold=0.85):
        discrepancies.append(f"Vendor mismatch: PO='{po['vendorName']}', Invoice='{vendor_name}'")
    
    status = "MATCHED" if not discrepancies else "PARTIAL_MATCH"
    
    return {
        "status": status,
        "poId": po["poNumber"],
        "poData": po,
        "amountVariancePct": variance,
        "discrepancies": discrepancies
    }
```

#### Tool 2: `match_goods_receipt`

  -------------------------------------------------------------------------------------------------------------------------------------
  Property                                  Value
  ----------------------------------------- -------------------------------------------------------------------------------------------
  Description                               Verifies that goods/services have been received for a given PO

  Input Schema                              `{ "poNumber": string, "invoicedQuantity": number }`

  Output                                    `{ "status": "CONFIRMED|PARTIAL|NOT_RECEIVED", "grData": {...}, "discrepancies": [...] }`

  Implementation                            Lambda function querying DynamoDB GR table
  -------------------------------------------------------------------------------------------------------------------------------------

``` python
# tools/match_gr.py
def match_goods_receipt(po_number: str, invoiced_quantity: int) -> dict:
    """Verify goods receipt against PO."""
    
    # Query GRs for this PO
    grs = dynamo.query(
        IndexName="GSI-PONumber",
        KeyConditionExpression="poNumber = :po",
        ExpressionAttributeValues={":po": po_number}
    )
    
    if not grs:
        return {"status": "NOT_RECEIVED", "reason": "No goods receipt found for this PO"}
    
    # Sum total received across all GRs (partial deliveries)
    total_received = sum(gr["totalQuantityReceived"] for gr in grs)
    
    # 2% tolerance on quantity
    tolerance = invoiced_quantity * 0.02
    
    if total_received >= invoiced_quantity - tolerance:
        return {
            "status": "CONFIRMED",
            "grId": grs[0]["grId"],
            "quantityReceived": total_received,
            "quantityInvoiced": invoiced_quantity,
            "discrepancies": []
        }
    else:
        shortage = invoiced_quantity - total_received
        return {
            "status": "PARTIAL",
            "grId": grs[0]["grId"],
            "quantityReceived": total_received,
            "quantityInvoiced": invoiced_quantity,
            "discrepancies": [f"Quantity shortage: invoiced {invoiced_quantity}, received {total_received} (short by {shortage})"]
        }
```

#### Tool 3: `evaluate_approval_rules`

  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Property                                  Value
  ----------------------------------------- ---------------------------------------------------------------------------------------------------------------------------------------
  Description                               Evaluates business rules to determine auto-approval or escalation

  Input Schema                              `{ "totalAmount": number, "overallConfidence": number, "vendorName": string, "threeWayMatchStatus": string, "discrepancies": [...] }`

  Output                                    `{ "decision": "APPROVE|ESCALATE", "reason": string, "escalateTo": string|null, "rulesResults": [...] }`

  Implementation                            Pure logic function (no external calls)
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

``` python
# tools/evaluate_rules.py
#
# Thresholds are admin-configurable and loaded from the AppConfig table
# (APPROVAL_SETTINGS) at evaluation time; the values below are the defaults
# used when no override is stored.
DEFAULT_AMOUNT_THRESHOLD = 10000.00
DEFAULT_CONFIDENCE_THRESHOLD = 0.85

def evaluate_approval_rules(total_amount: float, overall_confidence: float,
                           vendor_name: str, three_way_match_status: str,
                           discrepancies: list,
                           amount_threshold: float = DEFAULT_AMOUNT_THRESHOLD,
                           confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict:
    """Evaluate all approval rules and return decision.

    NOTE: The former RULE-004 (approved-vendor allow-list) has been REMOVED.
    vendor_name is still accepted for PO matching and logging, but it no longer
    gates approval.
    """
    
    rules_results = []
    
    # Rule 1: Three-way match
    rule1_pass = three_way_match_status == "PASS"
    rules_results.append({
        "ruleId": "RULE-001", "name": "Three-Way Match",
        "passed": rule1_pass,
        "detail": f"Match status: {three_way_match_status}"
    })
    
    # Rule 2: Amount threshold (configurable)
    rule2_pass = total_amount <= amount_threshold
    rules_results.append({
        "ruleId": "RULE-002", "name": "Amount Threshold",
        "passed": rule2_pass,
        "detail": f"Amount ${total_amount:.2f} vs threshold ${amount_threshold:.2f}"
    })
    
    # Rule 3: Confidence threshold (configurable)
    rule3_pass = overall_confidence >= confidence_threshold
    rules_results.append({
        "ruleId": "RULE-003", "name": "Confidence Threshold",
        "passed": rule3_pass,
        "detail": f"Confidence {overall_confidence:.2f} vs threshold {confidence_threshold}"
    })
    
    # Decision logic
    if all(r["passed"] for r in rules_results):
        return {
            "decision": "APPROVE",
            "reason": "All approval rules passed",
            "escalateTo": None,
            "rulesResults": rules_results
        }
    
    # Route escalation by highest-priority failing rule
    if not rule2_pass:
        escalate_to = "FINANCE_MANAGER"
        reason = f"Amount ${total_amount:.2f} exceeds auto-approval threshold of ${amount_threshold:.2f}"
    elif not rule1_pass:
        escalate_to = "AP_CLERK"
        reason = f"Three-way match failed: {', '.join(discrepancies)}"
    else:  # not rule3_pass
        escalate_to = "AP_CLERK"
        reason = f"Low extraction confidence ({overall_confidence:.2f}). Manual verification required."
    
    return {
        "decision": "ESCALATE",
        "reason": reason,
        "escalateTo": escalate_to,
        "rulesResults": rules_results
    }
```

#### Tool 4: `get_extraction_summary`

  -----------------------------------------------------------------------
  Property                                  Value
  ----------------------------------------- -----------------------------
  Description                               Retrieves and summarizes the
                                            extraction results for agent
                                            reasoning

  Input Schema                              `{ "documentId": string }`

  Output                                    Extraction data with
                                            confidence analysis

  Implementation                            DynamoDB read + confidence
                                            analysis
  -----------------------------------------------------------------------

### 2.4 Agent Invocation Pattern

``` python
# How the InvoiceProcessor Lambda invokes the AP Agent
def invoke_ap_agent(document_id: str, extraction: dict) -> dict:
    """Invoke the AP Invoice Agent via AgentCore."""
    
    client = boto3.client('bedrock-agent-runtime')
    
    # Construct the input prompt with extraction data
    input_text = f"""Process this invoice and determine if it should be approved or escalated.

Document ID: {document_id}

Extracted Invoice Data:
- Vendor: {extraction['vendorName']} (confidence: {extraction['confidence']['vendorName']})
- Invoice Number: {extraction['invoiceNumber']}
- PO Reference: {extraction.get('poReference', 'NOT FOUND')}
- Total Amount: ${extraction['totalAmount']}
- Overall Confidence: {extraction['overallConfidence']}

Total line items quantity: {sum(item['quantity'] for item in extraction['lineItems'])}

Please:
1. Match this invoice against the Purchase Order
2. Verify goods receipt
3. Evaluate approval rules
4. Return your decision with reasoning
"""
    
    response = client.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=document_id,  # Use doc ID as session (one-shot)
        inputText=input_text
    )
    
    # Parse agent response
    return parse_agent_decision(response)
```

------------------------------------------------------------------------

## 3. Records Search Agent

### 3.1 Agent Identity

  Property         Value
  ---------------- -----------------------------------------------------------
  Name             Records Search Assistant Agent
  ID               `records-search-agent`
  Model            Claude 3 Sonnet (anthropic.claude-3-sonnet-20240229-v1:0)
  Temperature      0.3 (some creativity in synthesis, grounded in facts)
  Max Tokens       1024
  Invocation       Synchronous (from ChatHandler Lambda)
  Timeout          30 seconds
  Knowledge Base   Integrated via AgentCore KB association

### 3.2 Agent Reasoning Pattern

The Records Agent follows a **Retrieve-then-Generate pattern** (RAG):

    ┌────────────────────────────────────────────────────────────┐
    │             Records Agent Reasoning Loop                    │
    │                                                            │
    │  Input: user question + conversation history + filters     │
    │                                                            │
    │  Step 1: Understand the query                              │
    │           → Resolve pronouns from history                  │
    │           → Identify topic and intent                      │
    │           → Determine if answerable from org records       │
    │                                                            │
    │  Step 2: Retrieve relevant documents                       │
    │           → Call Knowledge Base (semantic search)           │
    │           → Apply category filter if specified             │
    │           → Get top-k chunks (k=5)                        │
    │                                                            │
    │  Step 3: Evaluate retrieval quality                        │
    │           → Are chunks relevant to the question?           │
    │           → If no relevant chunks → "I don't know" path   │
    │                                                            │
    │  Step 4: Synthesize answer                                 │
    │           → Generate response from retrieved context       │
    │           → Include specific facts and details             │
    │           → Maintain professional tone                     │
    │                                                            │
    │  Step 5: Attach citations                                  │
    │           → Map answer claims to source chunks             │
    │           → Include document name, page, relevance         │
    │                                                            │
    │  Output: answer + citations array                          │
    └────────────────────────────────────────────────────────────┘

### 3.3 Knowledge Base Configuration

``` json
{
  "knowledgeBaseId": "KB_XXXXXXXXXX",
  "name": "IntelliProcess-Knowledge-Base",
  "description": "Organizational records including policies, contracts, invoices, and procurement documents",
  "storageConfiguration": {
    "type": "OPENSEARCH_SERVERLESS",
    "opensearchServerlessConfiguration": {
      "collectionArn": "arn:aws:aoss:us-east-1:123456789012:collection/intelliprocess-vectors",
      "vectorIndexName": "intelliprocess-index",
      "fieldMapping": {
        "vectorField": "embedding",
        "textField": "text",
        "metadataField": "metadata"
      }
    }
  },
  "dataSource": {
    "type": "S3",
    "s3Configuration": {
      "bucketArn": "arn:aws:s3:::intelliprocess-ai-documents",
      "inclusionPrefixes": ["records/", "invoices/", "purchase-orders/"]
    }
  },
  "embeddingModel": "amazon.titan-embed-text-v2:0",
  "chunkingStrategy": {
    "chunkingStrategy": "FIXED_SIZE",
    "fixedSizeChunkingConfiguration": {
      "maxTokens": 300,
      "overlapPercentage": 20
    }
  }
}
```

### 3.4 Retrieval Configuration

  Parameter                 Value        Rationale
  ------------------------- ------------ ------------------------------------------------
  Top K results             5            Balance between context breadth and token cost
  Chunk size                300 tokens   Standard for paragraph-level retrieval
  Overlap                   20%          Preserve context at chunk boundaries
  Similarity metric         Cosine       Standard for text embeddings
  Minimum score threshold   0.5          Filter out irrelevant chunks

### 3.5 Guardrails Configuration

``` json
{
  "guardrailId": "GUARDRAIL_XXXXXXXXXX",
  "name": "IntelliProcess-Records-Guardrail",
  "blockedInputMessaging": "I can only answer questions about organizational records and documents.",
  "blockedOutputsMessaging": "I'm unable to provide that information.",
  "topicPolicyConfig": {
    "topicsConfig": [
      {
        "name": "off-topic",
        "definition": "Questions not related to organizational policies, contracts, finance, procurement, or business operations",
        "type": "DENY",
        "examples": [
          "What's the weather today?",
          "Write me a poem",
          "How do I hack into a system?",
          "Tell me a joke"
        ]
      }
    ]
  },
  "contentPolicyConfig": {
    "filtersConfig": [
      {"type": "SEXUAL", "inputStrength": "HIGH", "outputStrength": "HIGH"},
      {"type": "VIOLENCE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
      {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
      {"type": "INSULTS", "inputStrength": "HIGH", "outputStrength": "HIGH"}
    ]
  }
}
```

### 3.6 Agent Invocation Pattern

``` python
# How the ChatHandler Lambda invokes the Records Agent
def invoke_records_agent(question: str, history: list, category_filter: str = None) -> dict:
    """Invoke the Records Search Agent via AgentCore."""
    
    client = boto3.client('bedrock-agent-runtime')
    
    # Build retrieval configuration with optional filter
    retrieval_config = {
        "vectorSearchConfiguration": {
            "numberOfResults": 5
        }
    }
    
    if category_filter and category_filter != "all":
        retrieval_config["vectorSearchConfiguration"]["filter"] = {
            "equals": {
                "key": "category",
                "value": category_filter
            }
        }
    
    # Use RetrieveAndGenerate for simplified RAG
    response = client.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": f"arn:aws:bedrock:us-east-1::foundation-model/{MODEL_ID}",
                "retrievalConfiguration": retrieval_config,
                "generationConfiguration": {
                    "inferenceConfig": {
                        "textInferenceConfig": {
                            "temperature": 0.3,
                            "maxTokens": 1024
                        }
                    },
                    "guardrailConfiguration": {
                        "guardrailId": GUARDRAIL_ID,
                        "guardrailVersion": "DRAFT"
                    }
                }
            }
        },
        sessionId=session_id  # Maintains conversation context
    )
    
    return {
        "answer": response["output"]["text"],
        "citations": extract_citations(response.get("citations", []))
    }


def extract_citations(raw_citations: list) -> list:
    """Transform Bedrock KB citations into our API format."""
    citations = []
    for citation in raw_citations:
        for reference in citation.get("retrievedReferences", []):
            location = reference.get("location", {})
            metadata = reference.get("metadata", {})
            citations.append({
                "documentName": metadata.get("x-amz-bedrock-kb-source-uri", "").split("/")[-1],
                "documentId": metadata.get("documentId", ""),
                "pageNumber": metadata.get("pageNumber"),
                "relevanceScore": reference.get("score", 0.0),
                "snippet": reference.get("content", {}).get("text", "")[:200],
                "category": metadata.get("category", "general")
            })
    return citations[:5]  # Limit to top 5 citations
```

------------------------------------------------------------------------

## 4. MVP Architecture: Direct Bedrock Calls (Primary)

The MVP uses **direct Bedrock API calls** within Lambda functions. This
is simpler, faster to implement, and avoids the complexity of AgentCore
configuration. AgentCore can be added post-MVP for more sophisticated
reasoning.

### 4.1 AP Agent --- Direct Orchestration (MVP Primary)

``` python
# Simplified: Direct orchestration in Lambda (no AgentCore)
def process_invoice_direct(document_id: str, extraction: dict) -> dict:
    """Process invoice using direct function calls instead of AgentCore."""
    
    # Step 1: Match PO (direct function call, no agent)
    po_result = match_purchase_order(
        po_number=extraction.get("poReference"),
        vendor_name=extraction["vendorName"],
        invoice_amount=extraction["totalAmount"]
    )
    
    # Step 2: Match GR (direct function call)
    gr_result = match_goods_receipt(
        po_number=po_result.get("poId", extraction.get("poReference")),
        invoiced_quantity=sum(item["quantity"] for item in extraction["lineItems"])
    )
    
    # Step 3: Determine three-way match
    three_way = "PASS" if (po_result["status"] == "MATCHED" and 
                           gr_result["status"] == "CONFIRMED") else "FAIL"
    all_discrepancies = po_result["discrepancies"] + gr_result["discrepancies"]
    
    # Step 4: Evaluate rules (direct function call)
    decision = evaluate_approval_rules(
        total_amount=extraction["totalAmount"],
        overall_confidence=extraction["overallConfidence"],
        vendor_name=extraction["vendorName"],
        three_way_match_status=three_way,
        discrepancies=all_discrepancies
    )
    
    return {
        "poMatch": po_result,
        "grMatch": gr_result,
        "threeWayMatch": three_way,
        "decision": decision
    }
```

**This is the MVP implementation.** The AgentCore approach (Sections 2-3
above) is retained as a post-MVP enhancement for when more sophisticated
reasoning is needed.

### 4.2 Records Agent --- Direct KB Call (MVP Primary)

``` python
# Simplified: Direct Bedrock KB RetrieveAndGenerate (no AgentCore)
def search_records_direct(question: str, session_id: str, category: str = None) -> dict:
    """Use Bedrock KB directly without AgentCore wrapper."""
    
    client = boto3.client('bedrock-agent-runtime')
    
    response = client.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": MODEL_ARN
            }
        },
        sessionId=session_id
    )
    
    return {
        "answer": response["output"]["text"],
        "citations": extract_citations(response.get("citations", []))
    }
```

**This is the MVP implementation.** Bedrock KB's `retrieve_and_generate`
handles retrieval, generation, and session memory in a single API call
--- no custom agent loop needed.

------------------------------------------------------------------------

## 5. Model Selection

### 5.1 Model Comparison

  Model               Use Case             Latency   Cost/1K tokens    Quality
  ------------------- -------------------- --------- ----------------- -----------
  Claude 3 Haiku      Fast, simple tasks   \~1s      \$0.00025 input   Good
  Claude 3 Sonnet     Complex reasoning    \~3s      \$0.003 input     Excellent
  Claude 3.5 Sonnet   Best quality         \~3s      \$0.003 input     Best

### 5.2 Model Assignment

  ------------------------------------------------------------------------
  Agent           Primary Model                   Rationale
  --------------- ------------------------------- ------------------------
  AP Invoice      Claude 3 Sonnet                 Needs reasoning about
  Agent                                           matching rules and edge
                                                  cases

  Records Agent   Claude 3 Sonnet                 Needs synthesis quality
                                                  for natural answers

  BDA Extraction  Bedrock Data Automation         Purpose-built for
                                                  document extraction

  Embeddings      Titan Text Embeddings v2        Cost-effective, good
                                                  quality embeddings
  ------------------------------------------------------------------------

**Cost Optimization (if budget is tight)**: Switch Records Agent to
Claude 3 Haiku for faster, cheaper responses. Quality is slightly lower
but acceptable for RAG (most intelligence comes from good retrieval).

------------------------------------------------------------------------

## 6. Agent Testing Strategy

### 6.1 Test Scenarios for AP Agent

  ----------------------------------------------------------------------------
  Scenario         Input          Expected Decision               Tests
  ---------------- -------------- ------------------------------- ------------
  Happy path       Valid invoice, APPROVED                        Rule
                   PO match, GR                                   evaluation
                   confirmed, \<                                  
                   \$10K                                          

  High amount      Valid match,   ESCALATED to FINANCE_MANAGER    Amount
                   \$15,000                                       threshold

  No PO match      Invoice with   ESCALATED to AP_CLERK           Match
                   non-existent                                   failure
                   PO                                             

  Low confidence   Overall        ESCALATED to AP_CLERK           Confidence
                   confidence                                     check
                   0.72                                           

  Unknown vendor   Vendor not in  ESCALATED to AP_CLERK           Vendor check
                   approved list                                  

  Partial GR       Received 8 of  ESCALATED to AP_CLERK           Quantity
                   10 items                                       mismatch

  Amount variance  PO \$500,      ESCALATED to AP_CLERK           Amount
                   Invoice \$600                                  tolerance
                   (20% off)                                      
  ----------------------------------------------------------------------------

### 6.2 Test Scenarios for Records Agent

  ---------------------------------------------------------------------------
  Scenario         Query          Expected Behavior               Tests
  ---------------- -------------- ------------------------------- -----------
  Direct answer    "What is the   Clear answer + citation         RAG
                   travel policy                                  retrieval
                   limit?"                                        

  No information   "What is our   "I don't have information..."   Guardrail
                   Mars                                           
                   colonization                                   
                   budget?"                                       

  Off-topic        "What's the    Topic denial message            Guardrail
                   weather?"                                      

  Follow-up        "Tell me more  Uses conversation context       Memory
                   about that"                                    

  Category filter  "Search only   Filtered retrieval              Metadata
                   contracts"                                     filter

  Multiple sources "Compare       Multi-citation answer           Citation
                   Policy A vs B"                                 quality
  ---------------------------------------------------------------------------

------------------------------------------------------------------------

## 7. Agent Monitoring

### 7.1 Metrics to Track

  Metric                 Agent           How Measured
  ---------------------- --------------- --------------------------------
  Invocation count       Both            CloudWatch metric
  Latency (p50, p95)     Both            CloudWatch metric
  Error rate             Both            CloudWatch error count
  Token usage (input)    Both            Bedrock model invocation logs
  Token usage (output)   Both            Bedrock model invocation logs
  Approval rate          AP Agent        DynamoDB status counts
  Citation count         Records Agent   Average citations per response
  Guardrail triggers     Records Agent   Bedrock guardrail metrics

### 7.2 Logging

``` python
# Agent invocation logging
log_event("agent_invocation", document_id,
    agent="ap-invoice-agent",
    input_tokens=response["usage"]["inputTokens"],
    output_tokens=response["usage"]["outputTokens"],
    latency_ms=elapsed,
    decision=result["decision"],
    rules_passed=result["rulesPassed"]
)
```

------------------------------------------------------------------------

## 8. Agent Evolution Roadmap

  -----------------------------------------------------------------------
  Phase             Capability                  Timeline
  ----------------- --------------------------- -------------------------
  MVP (Week 1-3)    Direct function calls for   Current
                    AP + Direct Bedrock KB      
                    RetrieveAndGenerate for RAG 

  V1.1              Add AgentCore for AP        Post-capstone
                    reasoning on edge cases     

  V1.2              Add memory/learning from    Future
                    past decisions              

  V2.0              Multi-agent collaboration   Future
                    (AP asks Records)           

  V2.1              Proactive anomaly detection Future
                    agent                       
  -----------------------------------------------------------------------
