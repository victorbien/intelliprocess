"""Admin-configurable approval settings store.

Persists a single 'approval settings' record in the AppConfig DynamoDB table
(PK ``configKey = "APPROVAL_SETTINGS"``) and exposes typed get/put helpers.

When no record exists, ``get_approval_settings`` returns the built-in defaults
(which mirror the module-level constants in ``rules.py`` / ``matcher.py``) so
the pipeline behaves exactly as before this feature was added.

Values
------
- amountThreshold:      invoice auto-approval ceiling in USD (default 10000).
- confidenceThreshold:  min extraction confidence to auto-approve (default 0.85).
- poAmountTolerance:    three-way match PO amount margin (default 0.05 = 5%).
- grQtyTolerance:       three-way match GR quantity margin (default 0.02 = 2%).
"""

import logging
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from app.config import settings
from app.services.dynamo import DynamoClient

logger = logging.getLogger(__name__)

# Singleton primary key for the approval-settings record.
_CONFIG_KEY = "APPROVAL_SETTINGS"

# Built-in defaults — mirror rules.AMOUNT_THRESHOLD / rules.CONFIDENCE_THRESHOLD
# and matcher._PO_AMOUNT_TOLERANCE / matcher._GR_QTY_TOLERANCE.
_DEFAULTS: dict[str, float] = {
    "amountThreshold":     10_000.00,
    "confidenceThreshold": 0.85,
    "poAmountTolerance":   0.05,
    "grQtyTolerance":      0.02,
}

_FIELDS = tuple(_DEFAULTS.keys())

_config_db = DynamoClient(settings.CONFIG_TABLE)


def get_approval_settings() -> dict[str, float]:
    """Return the current approval settings, falling back to defaults.

    Never raises for a missing record or an unconfigured table — the pipeline
    must always get usable thresholds. Reads that fail are logged and the
    defaults are returned so processing degrades safely.
    """
    try:
        item = _config_db.get_item({"configKey": _CONFIG_KEY})
    except (ClientError, RuntimeError) as exc:
        logger.warning(
            "Could not read approval settings — using defaults",
            extra={"error": str(exc)},
        )
        return dict(_DEFAULTS)

    if not item:
        return dict(_DEFAULTS)

    # Coerce stored Decimals to float; fill any missing field from defaults.
    result: dict[str, float] = {}
    for field, default in _DEFAULTS.items():
        value = item.get(field)
        result[field] = float(value) if value is not None else default
    return result


def put_approval_settings(values: dict[str, float]) -> dict[str, float]:
    """Persist the approval settings singleton. Returns the stored values.

    ``values`` must contain all four fields (validated upstream by the
    ApprovalSettings schema). Floats are stored as Decimal for DynamoDB.
    """
    item: dict[str, Any] = {"configKey": _CONFIG_KEY}
    for field in _FIELDS:
        item[field] = Decimal(str(values[field]))

    _config_db.put_item(item)
    logger.info("Approval settings updated", extra={k: values[k] for k in _FIELDS})
    return {field: float(item[field]) for field in _FIELDS}
