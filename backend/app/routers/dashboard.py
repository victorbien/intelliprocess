"""Dashboard and admin endpoints."""

from fastapi import APIRouter

router = APIRouter()


# GET /dashboard/stats - Invoice processing statistics
# POST /dashboard/admin/seed-data - Load sample PO/GR data
