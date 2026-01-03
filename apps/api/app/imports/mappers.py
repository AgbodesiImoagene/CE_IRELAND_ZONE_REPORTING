"""Column mapping and auto-detection for imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fuzzywuzzy import fuzz


@dataclass
class ColumnMapping:
    """Column mapping configuration."""

    source_column: str
    target_field: str
    coercion_rules: dict[str, Any]  # Type, format, transformations
    required: bool = False
    default_value: Any = None
    validation_rules: list[dict] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.validation_rules is None:
            self.validation_rules = []


# Field mapping definitions for each entity type
FIELD_MAPPINGS = {
    "people": {
        "first_name": {
            "variations": [
                "first_name",
                "firstname",
                "first name",
                "fname",
                "given_name",
                "given name",
                "forename",
                "name",
            ],
            "required": True,
        },
        "last_name": {
            "variations": [
                "last_name",
                "lastname",
                "last name",
                "lname",
                "surname",
                "family_name",
                "family name",
            ],
            "required": True,
        },
        "email": {
            "variations": [
                "email",
                "e-mail",
                "email_address",
                "email address",
                "mail",
            ],
            "required": False,
        },
        "phone": {
            "variations": [
                "phone",
                "telephone",
                "phone_number",
                "phone number",
                "mobile",
                "cell",
                "contact",
            ],
            "required": False,
        },
        "gender": {
            "variations": ["gender", "sex"],
            "required": True,
        },
        "dob": {
            "variations": [
                "dob",
                "date_of_birth",
                "date of birth",
                "birth_date",
                "birth date",
                "birthday",
            ],
            "required": False,
        },
        "member_code": {
            "variations": [
                "member_code",
                "member code",
                "member_id",
                "member id",
                "id",
                "code",
            ],
            "required": False,
        },
        "title": {
            "variations": ["title", "prefix", "salutation"],
            "required": False,
        },
        "alias": {
            "variations": ["alias", "nickname", "preferred_name", "preferred name"],
            "required": False,
        },
        "address_line1": {
            "variations": [
                "address_line1",
                "address line1",
                "address",
                "street",
                "street_address",
                "street address",
            ],
            "required": False,
        },
        "address_line2": {
            "variations": [
                "address_line2",
                "address line2",
                "address2",
                "apartment",
                "unit",
            ],
            "required": False,
        },
        "town": {
            "variations": ["town", "city"],
            "required": False,
        },
        "county": {
            "variations": ["county", "state", "province"],
            "required": False,
        },
        "eircode": {
            "variations": ["eircode", "postcode", "postal_code", "postal code", "zip"],
            "required": False,
        },
        "marital_status": {
            "variations": [
                "marital_status",
                "marital status",
                "marital",
                "status",
            ],
            "required": False,
        },
    },
    "memberships": {
        "status": {
            "variations": ["status", "membership_status", "membership status"],
            "required": False,
        },
        "join_date": {
            "variations": [
                "join_date",
                "join date",
                "joined",
                "member_since",
                "member since",
            ],
            "required": False,
        },
        "foundation_completed": {
            "variations": [
                "foundation_completed",
                "foundation completed",
                "foundation",
            ],
            "required": False,
        },
        "baptism_date": {
            "variations": [
                "baptism_date",
                "baptism date",
                "baptized",
                "baptism",
            ],
            "required": False,
        },
    },
    "first_timers": {
        "service_id": {
            "variations": ["service_id", "service id", "service"],
            "required": True,
        },
        "source": {
            "variations": ["source", "inviter", "invited_by", "invited by"],
            "required": False,
        },
        "status": {
            "variations": ["status", "first_timer_status", "first timer status"],
            "required": False,
        },
        "notes": {
            "variations": ["notes", "note", "comments", "comment"],
            "required": False,
        },
    },
    "services": {
        "name": {
            "variations": ["name", "service_name", "service name"],
            "required": True,
        },
        "service_date": {
            "variations": [
                "service_date",
                "service date",
                "date",
                "event_date",
                "event date",
            ],
            "required": True,
        },
        "service_time": {
            "variations": [
                "service_time",
                "service time",
                "time",
                "start_time",
                "start time",
            ],
            "required": False,
        },
    },
    "attendance": {
        "service_id": {
            "variations": ["service_id", "service id", "service"],
            "required": True,
        },
        "attendance_count": {
            "variations": [
                "attendance_count",
                "attendance count",
                "attendance",
                "count",
                "total",
            ],
            "required": False,
        },
        "notes": {
            "variations": ["notes", "note", "comments", "comment"],
            "required": False,
        },
    },
    "cells": {
        "name": {
            "variations": [
                "name",
                "cell_name",
                "cell name",
                "group_name",
                "group name",
            ],
            "required": True,
        },
        "leader_id": {
            "variations": [
                "leader_id",
                "leader id",
                "leader",
                "cell_leader",
                "cell leader",
            ],
            "required": False,
        },
        "assistant_leader_id": {
            "variations": [
                "assistant_leader_id",
                "assistant leader id",
                "assistant_leader",
                "assistant leader",
                "co_leader",
                "co leader",
            ],
            "required": False,
        },
        "venue": {
            "variations": ["venue", "location", "address", "meeting_venue"],
            "required": False,
        },
        "meeting_day": {
            "variations": [
                "meeting_day",
                "meeting day",
                "day",
                "meets_on",
                "meets on",
            ],
            "required": False,
        },
        "meeting_time": {
            "variations": [
                "meeting_time",
                "meeting time",
                "time",
                "start_time",
                "start time",
            ],
            "required": False,
        },
        "status": {
            "variations": ["status", "cell_status", "cell status"],
            "required": False,
        },
    },
    "cell_reports": {
        "cell_id": {
            "variations": ["cell_id", "cell id", "cell"],
            "required": True,
        },
        "report_date": {
            "variations": [
                "report_date",
                "report date",
                "date",
                "meeting_date",
                "meeting date",
            ],
            "required": True,
        },
        "report_time": {
            "variations": [
                "report_time",
                "report time",
                "time",
                "meeting_time",
                "meeting time",
            ],
            "required": False,
        },
        "attendance": {
            "variations": [
                "attendance",
                "attendance_count",
                "attendance count",
                "count",
            ],
            "required": False,
        },
        "first_timers": {
            "variations": [
                "first_timers",
                "first timers",
                "first_timer_count",
                "first timer count",
            ],
            "required": False,
        },
        "new_converts": {
            "variations": [
                "new_converts",
                "new converts",
                "converts",
                "conversions",
            ],
            "required": False,
        },
        "testimonies": {
            "variations": ["testimonies", "testimony", "testimonials"],
            "required": False,
        },
        "offerings_total": {
            "variations": [
                "offerings_total",
                "offerings total",
                "offerings",
                "offering",
                "total_offering",
                "total offering",
            ],
            "required": False,
        },
        "meeting_type": {
            "variations": [
                "meeting_type",
                "meeting type",
                "type",
                "meeting_kind",
            ],
            "required": False,
        },
        "status": {
            "variations": ["status", "report_status", "report status"],
            "required": False,
        },
        "notes": {
            "variations": ["notes", "note", "comments", "comment"],
            "required": False,
        },
    },
    "finance_entries": {
        "fund_id": {
            "variations": ["fund_id", "fund id", "fund"],
            "required": True,
        },
        "amount": {
            "variations": ["amount", "value", "total", "sum"],
            "required": True,
        },
        "transaction_date": {
            "variations": [
                "transaction_date",
                "transaction date",
                "date",
                "entry_date",
                "entry date",
            ],
            "required": True,
        },
        "org_unit_id": {
            "variations": [
                "org_unit_id",
                "org unit id",
                "org_unit",
                "org unit",
                "organization",
            ],
            "required": True,
        },
        "batch_id": {
            "variations": ["batch_id", "batch id", "batch"],
            "required": False,
        },
        "service_id": {
            "variations": ["service_id", "service id", "service"],
            "required": False,
        },
        "partnership_arm_id": {
            "variations": [
                "partnership_arm_id",
                "partnership arm id",
                "partnership_arm",
                "partnership arm",
                "arm",
            ],
            "required": False,
        },
        "currency": {
            "variations": ["currency", "curr"],
            "required": False,
        },
        "method": {
            "variations": [
                "method",
                "payment_method",
                "payment method",
                "payment_type",
                "payment type",
            ],
            "required": False,
        },
        "person_id": {
            "variations": [
                "person_id",
                "person id",
                "person",
                "giver_id",
                "giver id",
                "giver",
            ],
            "required": False,
        },
        "cell_id": {
            "variations": ["cell_id", "cell id", "cell"],
            "required": False,
        },
        "external_giver_name": {
            "variations": [
                "external_giver_name",
                "external giver name",
                "external_giver",
                "external giver",
                "giver_name",
                "giver name",
            ],
            "required": False,
        },
        "reference": {
            "variations": [
                "reference",
                "ref",
                "transaction_ref",
                "transaction ref",
            ],
            "required": False,
        },
        "comment": {
            "variations": ["comment", "comments", "notes", "note"],
            "required": False,
        },
        "verified_status": {
            "variations": [
                "verified_status",
                "verified status",
                "status",
                "verification_status",
            ],
            "required": False,
        },
        "source_type": {
            "variations": [
                "source_type",
                "source type",
                "source",
                "entry_source",
            ],
            "required": False,
        },
    },
}


def normalize_column_name(name: str) -> str:
    """Normalize column name for matching."""
    return name.lower().strip().replace("_", " ").replace("-", " ").replace(".", " ")


def calculate_similarity(source: str, target: str) -> int:
    """Calculate similarity score between source and target column names."""
    return fuzz.ratio(normalize_column_name(source), normalize_column_name(target))


def auto_map_columns(
    source_columns: list[str], entity_type: str
) -> dict[str, ColumnMapping]:
    """
    Auto-map source columns to target fields.

    Args:
        source_columns: List of source column names
        entity_type: Target entity type (e.g., "people", "memberships")

    Returns:
        Dictionary mapping source columns to ColumnMapping objects
    """
    if entity_type not in FIELD_MAPPINGS:
        return {}

    target_fields = FIELD_MAPPINGS[entity_type]
    mappings: dict[str, ColumnMapping] = {}
    used_targets = set()

    # First pass: exact matches and high-confidence matches
    for source_col in source_columns:
        best_match = None
        best_score = 0
        best_target = None

        for target_field, config in target_fields.items():
            if target_field in used_targets:
                continue

            # Check variations
            for variation in config.get("variations", []):
                score = calculate_similarity(source_col, variation)
                if score > best_score:
                    best_score = score
                    best_target = target_field
                    best_match = variation

        # Only create mapping if score is above threshold
        if best_score >= 70 and best_target:
            mappings[source_col] = ColumnMapping(
                source_column=source_col,
                target_field=best_target,
                coercion_rules={},
                required=target_fields[best_target].get("required", False),
            )
            used_targets.add(best_target)

    # Second pass: lower confidence matches for unmapped columns
    for source_col in source_columns:
        if source_col in mappings:
            continue

        best_match = None
        best_score = 0
        best_target = None

        for target_field, config in target_fields.items():
            if target_field in used_targets:
                continue

            for variation in config.get("variations", []):
                score = calculate_similarity(source_col, variation)
                if score > best_score:
                    best_score = score
                    best_target = target_field
                    best_match = variation

        # Lower threshold for second pass
        if best_score >= 50 and best_target:
            mappings[source_col] = ColumnMapping(
                source_column=source_col,
                target_field=best_target,
                coercion_rules={},
                required=target_fields[best_target].get("required", False),
            )
            used_targets.add(best_target)

    return mappings


def suggest_mappings(
    source_columns: list[str], entity_type: str
) -> dict[str, dict[str, Any]]:
    """
    Suggest column mappings with confidence scores.

    Args:
        source_columns: List of source column names
        entity_type: Target entity type

    Returns:
        Dictionary with suggestions for each source column
    """
    if entity_type not in FIELD_MAPPINGS:
        return {}

    target_fields = FIELD_MAPPINGS[entity_type]
    suggestions: dict[str, dict[str, Any]] = {}

    for source_col in source_columns:
        candidates = []
        for target_field, config in target_fields.items():
            max_score = 0
            for variation in config.get("variations", []):
                score = calculate_similarity(source_col, variation)
                max_score = max(max_score, score)

            if max_score > 0:
                candidates.append(
                    {
                        "target_field": target_field,
                        "score": max_score,
                        "required": config.get("required", False),
                    }
                )

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        suggestions[source_col] = {
            "best_match": candidates[0] if candidates else None,
            "all_candidates": candidates[:5],  # Top 5 candidates
        }

    return suggestions

