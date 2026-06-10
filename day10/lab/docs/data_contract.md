# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `policy_refund_v4` | CSV export từ hệ policy/refund | stale refund window `14 ngày`, phrasing không đồng nhất, duplicate | `refund_no_stale_14d_window`, `duplicate_chunk_text` |
| `sla_p1_2026` | CSV export từ hệ support/SLA | chunk SLA viết tắt, duplicate, thiếu ngày hiệu lực | `required_doc_coverage`, `effective_date_iso_yyyy_mm_dd` |
| `it_helpdesk_faq` | CSV export từ FAQ nội bộ | noisy prefix, duplicate, exported_at format lẫn lộn | `exported_at_iso_datetime`, `duplicate_chunk_text` |
| `hr_leave_policy` | CSV export từ HR policy | annual leave bản 2025 lẫn với policy 2026, thiếu effective_date | `hr_leave_no_stale_10d_annual`, `stale_hr_policy_content` |
| `access_control_sop` | CSV export từ IT security / access matrix | bị bỏ allowlist ở baseline, có chunk trống và duplicate | `required_doc_coverage`, `missing_chunk_text_after_sanitize` |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | ID ổn định cho upsert/prune trong Chroma |
| doc_id | string | Có | Logical source id như `policy_refund_v4` hoặc `access_control_sop` |
| chunk_text | string | Có | Đã sanitize noise prefix, fix stale content nếu có |
| effective_date | date | Có | Chuẩn hoá về `YYYY-MM-DD` |
| exported_at | datetime | Có | Chuẩn hoá về `YYYY-MM-DDTHH:MM:SS` để freshness/audit dùng được |

---

## 3. Quy tắc quarantine vs drop

Trong repo này, record không bị xoá im lặng mà đi theo 2 nhánh rõ ràng:

- `cleaned`: record hợp lệ sau normalize/sanitize, được ghi vào `artifacts/cleaned/cleaned_<run_id>.csv`
- `quarantine`: record bị loại, vẫn giữ lại nguyên row + `reason`, được ghi vào `artifacts/quarantine/quarantine_<run_id>.csv`

Các reason chính trong run tốt `codex-good-submit`:

- `unknown_doc_id = 109`
- `duplicate_chunk_text = 63`
- `stale_hr_policy_content = 25`
- `missing_chunk_text_after_sanitize = 12`
- `missing_effective_date = 6`

Về vận hành, merge lại record từ quarantine chỉ nên được approve khi:

- xác nhận nó là canonical source hợp lệ
- cập nhật cleaning rule hoặc contract tương ứng
- rerun pipeline để expectation + eval vẫn pass

---

## 4. Phiên bản & canonical

Canonical sources hiện tại:

- `data/docs/policy_refund_v4.txt` -> `policy_refund_v4`
- `data/docs/sla_p1_2026.txt` -> `sla_p1_2026`
- `data/docs/it_helpdesk_faq.txt` -> `it_helpdesk_faq`
- `data/docs/hr_leave_policy.txt` -> `hr_leave_policy`
- `data/docs/access_control_sop.txt` -> `access_control_sop`

Source of truth cho các câu khó:

- refund window hiện hành: `policy_refund_v4` với cửa sổ `7 ngày làm việc`
- annual leave dưới 3 năm: `hr_leave_policy` bản 2026 với `12 ngày`
- level 4 admin approval: `access_control_sop`

Owner và alert channel đang được khai báo trong contract YAML:

- `owner_team: cs-it-helpdesk-data`
- `alert_channel: #data-observability`
