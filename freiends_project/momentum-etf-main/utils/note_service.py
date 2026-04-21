from __future__ import annotations

from datetime import datetime
from typing import Any

from utils.account_notes import load_account_note, save_account_note
from utils.account_registry import load_account_configs, pick_default_account


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalize_account_id(value: str) -> str:
    account_id = str(value or "").strip().lower()
    if not account_id:
        raise ValueError("account_id가 필요합니다.")
    return account_id


def _build_accounts_payload() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accounts = load_account_configs()
    if not accounts:
        raise ValueError("선택 가능한 계좌가 없습니다.")

    default_account = pick_default_account(accounts)
    payload = [
        {
            "account_id": str(account["account_id"]),
            "order": int(account["order"]),
            "name": str(account["name"]),
            "icon": str(account.get("icon") or ""),
        }
        for account in accounts
    ]
    return payload, default_account


def load_note_page_data(account_id: str | None = None) -> dict[str, Any]:
    accounts_payload, default_account = _build_accounts_payload()
    selected_account_id = _normalize_account_id(account_id or str(default_account["account_id"]))

    target_account = next(
        (account for account in accounts_payload if account["account_id"] == selected_account_id),
        None,
    )
    if target_account is None:
        raise ValueError(f"계좌 '{selected_account_id}'을(를) 찾을 수 없습니다.")

    note_doc = load_account_note(selected_account_id)
    return {
        "accounts": accounts_payload,
        "account_id": selected_account_id,
        "content": str(note_doc.get("content") or "") if note_doc else "",
        "updated_at": _serialize_datetime(note_doc.get("updated_at")) if note_doc else None,
    }


def save_note_page_data(account_id: str, content: str) -> dict[str, str]:
    updated_at = save_account_note(_normalize_account_id(account_id), str(content or ""))
    return {"updated_at": updated_at.isoformat()}
