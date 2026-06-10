# Quality report — Lab Day 10 (nhóm)

**run_id:** `codex-good-submit`  
**Ngày:** 2026-06-10

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước | Sau | Ghi chú |
|--------|-------|-----|---------|
| raw_records | 247 (`inject-bad-seq`) | 247 (`codex-good-submit`) | cùng một raw snapshot |
| cleaned_records | 32 | 32 | inject chỉ bỏ refund fix, không đổi source coverage |
| quarantine_records | 215 | 215 | distribution quarantine giữ nguyên ở scenario inject |
| Expectation halt? | Yes | No | inject fail `refund_no_stale_14d_window`, run tốt pass hết |

---

## 2. Before / after retrieval (bắt buộc)

> Đính kèm hoặc dẫn link tới `artifacts/eval/before_after_eval.csv` (hoặc 2 file before/after).

**Câu hỏi then chốt:** refund window (`q_refund_window`)  
**Trước:** `artifacts/eval/after_inject_bad.csv` cho thấy `contains_expected=yes` nhưng `hits_forbidden=yes`, nghĩa là top-k vẫn còn chunk stale về refund window.  
**Sau:** `artifacts/eval/after_fix_eval.csv` cho thấy `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`.

**Merit (khuyến nghị):** versioning HR — `q_leave_version` (`contains_expected`, `hits_forbidden`, cột `top1_doc_expected`)

**Trước:** baseline cũ từng halt vì `hr_leave_no_stale_10d_annual` do annual leave bản HR 2025 vẫn lọt cleaned.  
**Sau:** `q_hr_annual_leave_under3` trong `after_fix_eval.csv` có `12 ngày`, `hits_forbidden=no`, `top1_doc_expected=yes`.

---

## 3. Freshness & monitor

`freshness_check=FAIL` ở cả `inject-bad-seq` và `codex-good-submit`.

Giải thích:

- SLA đang để `24 giờ`
- manifest tốt có `latest_exported_at = 2026-04-10T00:00:00`
- ngày chạy lab là 2026-06-10 nên tuổi dữ liệu vượt xa SLA

Điều này phù hợp với FAQ trong `SCORING.md`: data mẫu là snapshot cũ có chủ đích, nên FAIL phản ánh freshness của snapshot, không phải pipeline code bị lỗi.

---

## 4. Corruption inject (Sprint 3)

Corruption inject đã dùng:

```bash
python etl_pipeline.py run --run-id inject-bad-seq --no-refund-fix --skip-validate
```

Ý nghĩa:

- cố ý tắt rule sửa stale refund `14 ngày -> 7 ngày`
- vẫn cho embed tiếp để đo ảnh hưởng xuống retrieval

Cách phát hiện:

- expectation `refund_no_stale_14d_window` fail với `violations=1`
- `after_inject_bad.csv` cho `q_refund_window -> hits_forbidden=yes`
- sau khi rerun tốt `codex-good-submit`, cùng câu hỏi trở về `hits_forbidden=no`

---

## 5. Hạn chế & việc chưa làm

- rule versioning HR vẫn dùng logic nội dung đặc thù, chưa externalize ra config/contract
- `freshness_check` mới đo boundary publish, chưa đo thêm ingest boundary
- report hiện chưa tích hợp LLM-judge; eval mới dừng ở retrieval + keyword
