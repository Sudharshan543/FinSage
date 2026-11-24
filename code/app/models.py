
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    region: str = "India"


class FlagInvoiceRequest(BaseModel):
    invoice_id: str
    reason: str = Field(..., min_length=1)
    confirmed: bool = False


class LogExpenseExceptionRequest(BaseModel):
    employee_id: str
    employee_name: str
    expense_category: Literal[
        "HOTEL", "MEAL", "MEALS", "TRANSPORT", "TRAVEL", "OTHER"
    ]
    expense_amount: float = Field(..., gt=0)
    currency: Literal["INR", "USD"] = "INR"
    expense_date: str
    region: Literal["IN", "INDIA", "India", "USA"] = "IN"
    policy_reference: str = Field(..., min_length=1)
    exception_reason: str = Field(..., min_length=1)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    nights: int | None = Field(default=None, ge=1)
    days: int | None = Field(default=None, ge=1)
    receipt_status: Literal["SUBMITTED", "MISSING", "UNKNOWN"] = "UNKNOWN"
    confirmed: bool = False

    @model_validator(mode="after")
    def validate_expense_details(self):
        region = self.region.upper()
        expected_currency = "USD" if region == "USA" else "INR"
        if self.currency != expected_currency:
            raise ValueError(
                f"Region {self.region} requires currency {expected_currency}."
            )

        category = self.expense_category.upper()
        if category == "HOTEL" and self.nights is None:
            raise ValueError("Hotel exceptions require the number of nights.")
        if category in ("MEAL", "MEALS") and self.days is None:
            raise ValueError("Meal exceptions require the number of days.")

        return self
