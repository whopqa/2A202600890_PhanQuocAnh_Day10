"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_YMD_SLASH_DATETIME = re.compile(r"^(\d{4})/(\d{2})/(\d{2})T(\d{2}):(\d{2}):(\d{2})$")


# Chuẩn hoá text để so sánh và dedupe ổn định hơn.
def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


# Loại prefix nhiễu trước khi áp rule business.
def _sanitize_chunk_text(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^Nội dung không rõ ràng:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^!+\s*", "", s)
    return " ".join(s.split())


# Sinh chunk_id ổn định để rerun có thể upsert/prune.
def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


# Chuẩn hoá effective_date về ISO hoặc trả về reason để quarantine.
def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


# Chuẩn hoá exported_at để freshness và audit dùng được.
def _normalize_exported_at(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_datetime, error_reason).
    exported_at rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "missing_exported_at"
    if _ISO_DATETIME.match(s):
        return s, ""
    m = _YMD_SLASH_DATETIME.match(s)
    if m:
        yyyy, mm, dd, hh, mi, ss = m.groups()
        return f"{yyyy}-{mm}-{dd}T{hh}:{mi}:{ss}", ""
    return "", "invalid_exported_at_format"


# Đọc raw CSV thành list row để clean và embed dùng chung.
def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


# Nhận diện annual leave stale của HR 2025 theo nội dung.
def _is_stale_hr_annual_leave(text: str) -> bool:
    t = _norm_text(text)
    if "bản hr 2025" in t:
        return True
    if "dưới 3 năm kinh nghiệm" in t and "10 ngày phép năm" in t:
        return True
    return False


# Chuẩn hoá phrasing SLA P1 để retrieval khớp câu hỏi tốt hơn.
def _normalize_sla_p1_text(doc_id: str, text: str) -> str:
    if doc_id != "sla_p1_2026":
        return text
    normalized = text
    if normalized.startswith("Escalation P1:"):
        return "Nếu không có phản hồi với ticket P1 sau 10 phút, hệ thống tự động escalate lên Senior Engineer."
    if normalized.startswith("Thông báo stakeholder P1:"):
        return "Trong sự cố P1, thông tin tiến độ cần được cập nhật mỗi 30 phút cho đến khi resolve."
    return normalized


# Chuẩn hoá phrasing refund window để before/after rõ hơn khi eval.
def _normalize_policy_refund_text(doc_id: str, text: str) -> str:
    if doc_id != "policy_refund_v4":
        return text
    normalized = text
    if "7 ngày làm việc" in normalized and "xác nhận đơn" in normalized:
        return "Sau khi đơn được xác nhận, khách hàng có tối đa 7 ngày làm việc để gửi yêu cầu hoàn tiền."
    if "14 ngày làm việc" in normalized and "xác nhận đơn" in normalized:
        return "Sau khi đơn được xác nhận, khách hàng có tối đa 14 ngày làm việc để gửi yêu cầu hoàn tiền."
    return normalized


# Hàm chính: clean raw rows và tách cleaned/quarantine.
def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Chuẩn hoá exported_at sang ISO datetime; quarantine nếu không parse được.
    4) Quarantine: chunk hr_leave_policy có nội dung stale của HR 2025.
    5) Sanitize text nhiễu trước dedupe và stale detection.
    6) Quarantine: chunk_text rỗng sau sanitize hoặc effective_date rỗng sau chuẩn hoá.
    7) Loại trùng nội dung chunk_text (giữ bản đầu).
    8) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = _sanitize_chunk_text(raw.get("chunk_text", ""))
        eff_raw = raw.get("effective_date", "")
        exported_at_raw = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        exported_at, exported_err = _normalize_exported_at(exported_at_raw)
        if exported_err:
            quarantine.append({**raw, "reason": exported_err, "exported_at_raw": exported_at_raw})
            continue

        if doc_id == "hr_leave_policy" and _is_stale_hr_annual_leave(text):
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_content",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text_after_sanitize"})
            continue

        text = _normalize_sla_p1_text(doc_id, text)
        text = _normalize_policy_refund_text(doc_id, text)

        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


# Ghi cleaned snapshot ra CSV để embed và audit.
def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


# Ghi quarantine snapshot kèm reason để debug dữ liệu bẩn.
def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
