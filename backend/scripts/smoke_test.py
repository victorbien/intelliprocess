"""End-to-end smoke test against the in-process app with moto mocks.

Run from backend/ directory:
    python scripts/smoke_test.py
"""

import sys

from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
passed = 0
failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  PASS  {label}" + (f"  [{detail}]" if detail else ""))
        passed += 1
    else:
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))
        failed += 1


print("\n=== IntelliProcess AI — Smoke Test ===\n")

# ── Health ────────────────────────────────────────────────────────────────────
r = c.get("/health")
check("/health returns 200", r.status_code == 200)
check("/health stage=dev", r.json().get("stage") == "dev")

# ── Invoices list ─────────────────────────────────────────────────────────────
r = c.get("/invoices")
check("GET /invoices returns 200", r.status_code == 200)
items = r.json()["data"]["items"]
check("GET /invoices returns seeded data", len(items) == 4, f"{len(items)} invoices")
statuses = {i["status"] for i in items}
check("Seeded statuses include APPROVED", "APPROVED" in statuses)
check("Seeded statuses include ESCALATED", "ESCALATED" in statuses)
check("Seeded statuses include PROCESSING", "PROCESSING" in statuses)

# ── Invoice detail — APPROVED ─────────────────────────────────────────────────
doc_approved = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
r = c.get(f"/invoices/{doc_approved}")
check("GET /invoices/{id} APPROVED returns 200", r.status_code == 200)
d = r.json()["data"]
check("APPROVED invoice has extraction", d.get("extraction") is not None)
check("APPROVED invoice has matchResult", d.get("matchResult") is not None)
check("APPROVED invoice has approvalDecision", d.get("approvalDecision") is not None)
check("APPROVED invoice overallConfidence >= 0.85",
      (d.get("overallConfidence") or 0) >= 0.85, str(d.get("overallConfidence")))

# ── Invoice detail — ESCALATED ────────────────────────────────────────────────
doc_escalated = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
r = c.get(f"/invoices/{doc_escalated}")
check("GET /invoices/{id} ESCALATED returns 200", r.status_code == 200)
d2 = r.json()["data"]
check("ESCALATED invoice status correct", d2["status"] == "ESCALATED")
ad = d2.get("approvalDecision", {})
check("ESCALATED has reason", "exceeds" in (ad.get("reason") or "").lower(),
      ad.get("reason", "")[:60])

# ── Invoice detail — 404 ──────────────────────────────────────────────────────
r = c.get("/invoices/00000000-0000-0000-0000-000000000000")
check("GET /invoices/{missing} returns 404", r.status_code == 404)

# ── Invoice detail — invalid UUID ────────────────────────────────────────────
r = c.get("/invoices/not-a-uuid")
# Our validation error handler normalises all validation errors to 400
check("GET /invoices/not-a-uuid returns 400", r.status_code == 400)

# ── Filter by status ──────────────────────────────────────────────────────────
r = c.get("/invoices?status=APPROVED")
check("GET /invoices?status=APPROVED returns 200", r.status_code == 200)
check("Status filter returns APPROVED invoices only",
      all(i["status"] == "APPROVED" for i in r.json()["data"]["items"]))

r = c.get("/invoices?status=ESCALATED")
check("GET /invoices?status=ESCALATED returns 200", r.status_code == 200)
check("Status filter returns ESCALATED only",
      all(i["status"] == "ESCALATED" for i in r.json()["data"]["items"]))

# ── Upload invoice — valid ────────────────────────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "new-invoice.pdf", "contentType": "application/pdf"})
check("POST /invoices/upload valid PDF returns 201", r.status_code == 201)
data = r.json()["data"]
check("Upload response has documentId", "documentId" in data)
check("Upload response has uploadUrl", "uploadUrl" in data)
check("Upload response has expiresIn=300", data.get("expiresIn") == 300)
new_id = data["documentId"]

# Verify the new item appears in DynamoDB
r2 = c.get(f"/invoices/{new_id}")
check("New invoice appears in GET /invoices/{id}", r2.status_code == 200)
check("New invoice status is UPLOADED", r2.json()["data"]["status"] == "UPLOADED")

# ── Upload invoice — PNG ───────────────────────────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "scan.png", "contentType": "image/png"})
check("POST /invoices/upload PNG returns 201", r.status_code == 201)

# ── Upload invoice — bad content type ─────────────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "sheet.xlsx", "contentType": "application/vnd.ms-excel"})
check("POST /invoices/upload bad type returns 400", r.status_code == 400)
check("Error message mentions 'Unsupported'", "Unsupported" in r.json().get("error", ""))

# ── Upload invoice — TIFF rejected ────────────────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "scan.tiff", "contentType": "image/tiff"})
check("POST /invoices/upload TIFF rejected", r.status_code == 400)

# ── Upload invoice — path traversal rejected ──────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "../../etc/passwd.pdf", "contentType": "application/pdf"})
check("POST /invoices/upload path traversal rejected", r.status_code == 400)

# ── Upload invoice — empty filename ───────────────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "   ", "contentType": "application/pdf"})
check("POST /invoices/upload empty name rejected", r.status_code == 400)

# ── Upload invoice — missing fields ───────────────────────────────────────────
r = c.post("/invoices/upload", json={})
check("POST /invoices/upload missing fields returns 400", r.status_code == 400)

# ── Pagination token — invalid ────────────────────────────────────────────────
r = c.get("/invoices?startKey=not-valid-base64!!!")
check("Invalid pagination token returns 400", r.status_code == 400)

# ── Documents list ────────────────────────────────────────────────────────────
r = c.get("/documents")
check("GET /documents returns 200", r.status_code == 200)
check("GET /documents returns 3 seeded docs", r.json()["data"]["count"] == 3)

# ── Documents category filter ─────────────────────────────────────────────────
r = c.get("/documents?category=policies")
check("GET /documents?category=policies returns 200", r.status_code == 200)
check("Category filter returns only policies",
      all(i["category"] == "policies" for i in r.json()["data"]["items"]))

r = c.get("/documents?category=contracts")
check("GET /documents?category=contracts returns 200", r.status_code == 200)

# ── Upload document — valid ───────────────────────────────────────────────────
r = c.post("/documents/upload", json={
    "fileName": "remote-work-policy.pdf",
    "contentType": "application/pdf",
    "category": "policies",
    "description": "Remote work eligibility guidelines",
})
check("POST /documents/upload valid PDF returns 201", r.status_code == 201)
doc_data = r.json()["data"]
check("Document upload has documentId", "documentId" in doc_data)
check("Document upload note mentions KB sync", "sync" in doc_data.get("note", "").lower())

# ── Upload document — DOCX ────────────────────────────────────────────────────
r = c.post("/documents/upload", json={
    "fileName": "contract.docx",
    "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "category": "contracts",
})
check("POST /documents/upload DOCX returns 201", r.status_code == 201)

# ── Upload document — image rejected ─────────────────────────────────────────
r = c.post("/documents/upload", json={
    "fileName": "scan.png",
    "contentType": "image/png",
    "category": "policies",
})
check("POST /documents/upload image rejected with 400", r.status_code == 400)

# ── Upload document — path traversal ─────────────────────────────────────────
r = c.post("/documents/upload", json={
    "fileName": "../../../secret.pdf",
    "contentType": "application/pdf",
    "category": "general",
})
check("POST /documents/upload path traversal rejected", r.status_code == 400)

# ── Upload document — description too long ────────────────────────────────────
r = c.post("/documents/upload", json={
    "fileName": "doc.pdf",
    "contentType": "application/pdf",
    "category": "finance",
    "description": "x" * 501,
})
check("POST /documents/upload description too long rejected", r.status_code == 400)

# ── Correlation ID ────────────────────────────────────────────────────────────
r = c.get("/health", headers={"X-Correlation-Id": "test-correlation-123"})
check("Correlation ID echoed in response", r.headers.get("x-correlation-id") == "test-correlation-123")

r = c.get("/health")
cid = r.headers.get("x-correlation-id", "")
check("Correlation ID auto-generated (UUID len=36)", len(cid) == 36)

# ── Error response structure ───────────────────────────────────────────────────
r = c.post("/invoices/upload", json={"fileName": "bad.xlsx", "contentType": "application/vnd.ms-excel"})
body = r.json()
check("Error response has 'statusCode'", "statusCode" in body)
check("Error response has 'error' string", isinstance(body.get("error"), str))

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*40}\n")

if failed:
    sys.exit(1)
