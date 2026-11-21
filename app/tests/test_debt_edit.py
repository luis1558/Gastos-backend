from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.modules.debts.schemas import DebtUpdateRequest
from app.modules.debts.service import ensure_amount_editable
from app.shared.constants import DebtStatus, DebtType


def test_paid_debt_amount_cannot_change():
    with pytest.raises(HTTPException) as exc:
        ensure_amount_editable(DebtStatus.PAID, Decimal("100"), Decimal("150"))
    assert exc.value.status_code == 400


def test_cancelled_debt_amount_cannot_change():
    with pytest.raises(HTTPException) as exc:
        ensure_amount_editable(DebtStatus.CANCELLED, Decimal("100"), Decimal("150"))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change the amount of a cancelled debt."


@pytest.mark.parametrize("status", [DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID])
def test_unpaid_debt_amount_can_change(status):
    ensure_amount_editable(status, Decimal("100"), Decimal("150"))


def test_paid_debt_accepts_same_amount_or_no_amount():
    ensure_amount_editable(DebtStatus.PAID, Decimal("100"), Decimal("100.00"))
    ensure_amount_editable(DebtStatus.PAID, Decimal("100"), None)


def test_update_request_accepts_debt_type():
    assert DebtUpdateRequest(type="receivable").type == DebtType.RECEIVABLE


def test_update_request_tracks_explicit_null_due_date():
    assert "due_date" in DebtUpdateRequest(due_date=None).model_fields_set
    assert "due_date" not in DebtUpdateRequest().model_fields_set
