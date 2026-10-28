"""Rule-based extraction of visible label fields.

These checks report text that looks present in the supplied text. They do not
determine whether a package meets any legal or regulatory requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DETECTED = "Detected"
NOT_DETECTED = "Not detected"
MANUAL_REVIEW = "Requires manual review"


@dataclass(frozen=True)
class FieldResult:
    key: str
    label: str
    value: str
    status: str
    explanation: str


_MRP_LABEL = re.compile(
    r"(?:maximum\s+retail\s+price|m\s*\.?\s*r\s*\.?\s*p\s*\.?)"
    r"\s*(?:\([^)]*\))?\s*(?:is\s*)?[:\-]?\s*"
    r"(?:(?:₹|¥|rs\.?|inr)\s*)?([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_CURRENCY_PRICE = re.compile(r"(?:₹|¥|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
_QUANTITY = re.compile(
    r"(?:net\s*(?:quantity|qty|weight|wt|volume|contents?)|quantity|net\s*qty)"
    r"\s*[:\-]?\s*"
    r"([\d.,]+\s*(?:kg|g|gm|grams?|mg|l|ml|litres?|liters?))",
    re.IGNORECASE,
)
_DATE_LABEL = re.compile(
    r"(?:manufacturing\s+date|date\s+of\s+manufacture|mfg\.?\s*date|"
    r"mfd\.?|mfg\.?|pkd\.?|date\s+of\s+packing|packing\s+date|packed\s+on)"
    r"\s*[:\-]?\s*(.*)",
    re.IGNORECASE,
)
_DATE_VALUE = re.compile(
    r"(?:(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{2,4}(?!\d)|"
    r"(?<!\d)\d{1,2}[./-]\d{4}(?!\d)|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"[a-z]*\s+\d{4}\b)",
    re.IGNORECASE,
)
_MAKER_LABEL = re.compile(
    r"(?:manufactured|manufacture|packed|packer|marketed|imported|distributed)"
    r"\s+(?:and\s+packed\s+)?(?:by|for)\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)
_CARE_LABEL = re.compile(
    r"(?:consumer|customer)\s*care|careline|toll[\s-]*free|"
    r"customer\s*service|contact\s*(?:us|details?)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_INDIAN_PHONE = re.compile(
    r"(?<!\d)(?:(?:\+91|0091)[\s-]?)?(?:0[\s-]?)?"
    r"(?:[6-9]\d{4}[\s-]?\d{5}|1800[\s-]?\d{3}[\s-]?\d{4})(?!\d)"
)
_EXPIRY_LABEL = re.compile(
    r"(?:best[\s-]*before|use\s*by|expiry(?:\s*date)?|exp\.?\s*date|"
    r"expiration(?:\s*date)?)\s*[:\-]?\s*(.*)",
    re.IGNORECASE,
)
_ADDRESS_CUE = re.compile(
    r"\b(?:address|road|street|plot|industrial\s+area|pin(?:\s*code)?|"
    r"postal\s*code|india)\b|\b\d{6}\b",
    re.IGNORECASE,
)
_OTHER_FIELD_START = re.compile(
    r"^\s*(?:mrp|maximum\s+retail|net\s|quantity|mfg|mfd|manufacturing\s+date|"
    r"packed\s+on|packing\s+date|pkd\.?|best[\s-]*before|use\s*by|expiry|"
    r"consumer\s*care|customer\s*care|ingredients|nutrition|fssai|"
    r"customer\s*service|email|phone|contact)\b",
    re.IGNORECASE,
)


def _text_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]


def _result(
    key: str,
    label: str,
    value: str,
    status: str,
    explanation: str,
) -> FieldResult:
    return FieldResult(
        key=key,
        label=label,
        value=value.strip(),
        status=status,
        explanation=explanation,
    )


def _find_mrp(text: str) -> FieldResult:
    match = _MRP_LABEL.search(text)
    if match:
        return _result(
            "mrp",
            "Maximum Retail Price (MRP)",
            f"₹{match.group(1)}",
            DETECTED,
            "A value appears beside an MRP label. Confirm it matches the printed package.",
        )

    possible_price = _CURRENCY_PRICE.search(text)
    if possible_price:
        return _result(
            "mrp",
            "Maximum Retail Price (MRP)",
            f"Possible price: ₹{possible_price.group(1)}",
            MANUAL_REVIEW,
            "A currency value was found, but it was not clearly labelled as MRP.",
        )

    return _result(
        "mrp",
        "Maximum Retail Price (MRP)",
        "",
        NOT_DETECTED,
        "No clearly labelled MRP value was recognized in the text.",
    )


def _find_quantity(text: str) -> FieldResult:
    match = _QUANTITY.search(text)
    if match:
        return _result(
            "net_quantity",
            "Net quantity",
            match.group(1),
            DETECTED,
            "A quantity and unit appear beside a quantity label.",
        )
    # OCR sometimes turns a unit into a digit (for example, "200 g" -> "2009").
    # Do not guess the intended unit; preserve the number for human correction.
    labelled_number = re.search(
        r"(?:net\s*(?:quantity|qty|weight|wt|volume|contents?)|quantity|net\s*qty)"
        r"\s*[:\-]?\s*([\d.,]+)",
        text,
        re.IGNORECASE,
    )
    if labelled_number:
        return _result(
            "net_quantity",
            "Net quantity",
            labelled_number.group(1),
            MANUAL_REVIEW,
            "A number appears beside the quantity label, but OCR did not recognize a unit. Check and correct the printed quantity.",
        )
    return _result(
        "net_quantity",
        "Net quantity",
        "",
        NOT_DETECTED,
        "No labelled net quantity with a recognized unit was found.",
    )


def _find_manufacturer(lines: list[str]) -> FieldResult:
    for index, line in enumerate(lines):
        match = _MAKER_LABEL.search(line)
        if not match or not match.group(1).strip():
            continue

        details = [line]
        for following in lines[index + 1 : index + 4]:
            if _OTHER_FIELD_START.search(following):
                break
            if _ADDRESS_CUE.search(following) or following.lower().startswith("address"):
                details.append(following)
            elif details[-1] != line and not _ADDRESS_CUE.search(following):
                break

        value = " ".join(details)
        if _ADDRESS_CUE.search(value):
            return _result(
                "manufacturer",
                "Manufacturer or packer",
                value,
                DETECTED,
                "A manufacturer/packer line and a possible address cue were found. Verify the full address.",
            )
        return _result(
            "manufacturer",
            "Manufacturer or packer",
            value,
            MANUAL_REVIEW,
            "A name appears, but a complete address was not clearly recognized.",
        )

    if re.search(r"\b(?:manufacturer|manufactured|packer|packed\s+by)\b", "\n".join(lines), re.I):
        return _result(
            "manufacturer",
            "Manufacturer or packer",
            "",
            MANUAL_REVIEW,
            "A manufacturer/packer reference appears, but no clear name and address were extracted.",
        )
    return _result(
        "manufacturer",
        "Manufacturer or packer",
        "",
        NOT_DETECTED,
        "No manufacturer or packer line was recognized.",
    )


def _find_manufacturing_date(lines: list[str]) -> FieldResult:
    for line in lines:
        match = _DATE_LABEL.search(line)
        if match:
            value = match.group(1).strip(" .:")
            date_match = _DATE_VALUE.search(value)
            if not date_match:
                # OCR may put a short heading (e.g. "PKD.:") on one line
                # and the date on the next line.
                line_index = lines.index(line)
                if line_index + 1 < len(lines):
                    next_line = lines[line_index + 1]
                    if not _OTHER_FIELD_START.search(next_line):
                        date_match = _DATE_VALUE.search(next_line)
                        if date_match:
                            value = next_line
            if date_match:
                return _result(
                    "manufacturing_date",
                    "Manufacturing or packing date",
                    date_match.group(0),
                    DETECTED,
                    "A date appears beside a manufacturing or packing label. Check the printed format.",
                )
            return _result(
                "manufacturing_date",
                "Manufacturing or packing date",
                value,
                MANUAL_REVIEW,
                "A date label was found, but its value could not be confidently read.",
            )
    return _result(
        "manufacturing_date",
        "Manufacturing or packing date",
        "",
        NOT_DETECTED,
        "No manufacturing or packing date label was recognized.",
    )


def _find_consumer_care(text: str, lines: list[str]) -> FieldResult:
    care_context = bool(_CARE_LABEL.search(text))
    email = _EMAIL.search(text)
    phone = _INDIAN_PHONE.search(text)
    contact = email.group(0) if email else phone.group(0) if phone else ""

    if contact and care_context:
        return _result(
            "consumer_care",
            "Consumer-care contact",
            contact,
            DETECTED,
            "A contact detail and consumer-care context were found. Verify that the number or email is complete.",
        )
    if contact:
        return _result(
            "consumer_care",
            "Consumer-care contact",
            contact,
            MANUAL_REVIEW,
            "A possible contact detail was found, but it was not clearly associated with consumer care.",
        )
    if care_context:
        return _result(
            "consumer_care",
            "Consumer-care contact",
            "",
            MANUAL_REVIEW,
            "A consumer-care heading was found, but no readable phone number or email was recognized.",
        )
    return _result(
        "consumer_care",
        "Consumer-care contact",
        "",
        NOT_DETECTED,
        "No consumer-care contact detail was recognized.",
    )


def _find_expiry(lines: list[str]) -> FieldResult:
    for line in lines:
        match = _EXPIRY_LABEL.search(line)
        if match:
            value = match.group(1).strip(" .:")
            if not value:
                line_index = lines.index(line)
                if line_index + 1 < len(lines):
                    next_line = lines[line_index + 1]
                    if not _OTHER_FIELD_START.search(next_line) and _DATE_VALUE.search(next_line):
                        value = next_line
            if value:
                return _result(
                    "expiry",
                    "Expiry or best-before information",
                    f"{line} {value}".strip(),
                    DETECTED,
                    "Expiry/best-before wording and a possible date were found. Confirm the printed format and value.",
                )
            return _result(
                "expiry",
                "Expiry or best-before information",
                line,
                MANUAL_REVIEW,
                "An expiry heading was found, but no value was clearly recognized.",
            )
    return _result(
        "expiry",
        "Expiry or best-before information",
        "",
        MANUAL_REVIEW,
        "No expiry/best-before text was recognized. Whether and how this applies can depend on the product.",
    )


def validate_label_text(text: str) -> list[FieldResult]:
    """Inspect text for common packaged-label fields and return transparent findings."""
    if not isinstance(text, str):
        raise TypeError("Label text must be a string.")
    lines = _text_lines(text)
    normalized_text = "\n".join(lines)
    return [
        _find_mrp(normalized_text),
        _find_quantity(normalized_text),
        _find_manufacturer(lines),
        _find_manufacturing_date(lines),
        _find_consumer_care(normalized_text, lines),
        _find_expiry(lines),
    ]
