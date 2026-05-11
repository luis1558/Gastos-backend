from enum import Enum


class DebtType(str, Enum):
    RECEIVABLE = "receivable"
    PAYABLE = "payable"


class DebtStatus(str, Enum):
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    TRANSFER = "transfer"
    DIGITAL_WALLET = "digital_wallet"
    OTHER = "other"


class CounterpartyType(str, Enum):
    PERSON = "person"
    BANK = "bank"
    BUSINESS = "business"
    FAMILY = "family"
    FRIEND = "friend"
    OTHER = "other"


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]
