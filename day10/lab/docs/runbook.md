# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

User hoặc agent trả lời đúng domain nhưng sai version dữ liệu, ví dụ:

- nói `14 ngày` thay vì `7 ngày làm việc` cho refund window
- nói annual leave dưới 3 năm là `10 ngày` thay vì `12 ngày`
- không retrieve được `access_control_sop` dù câu hỏi đúng thuộc tài liệu access control
- ticket P1 escalation không trả về `10 phút`

---

## Detection

Các tín hiệu phát hiện trong repo này:

- expectation halt ở `etl_pipeline.py run`
- `required_doc_coverage` fail nếu thiếu doc canonical như `access_control_sop`
- `refund_no_stale_14d_window` fail khi chạy inject `--no-refund-fix`
- `eval_retrieval.py` báo `hits_forbidden=yes` hoặc `contains_expected=no`
- `grading_run.py` cho `top1_doc_matches=false` hoặc `contains_expected=false`
- `freshness_check=FAIL` nếu manifest vượt SLA 24 giờ

Ví dụ thực tế:

- `inject-bad-seq` fail expectation `refund_no_stale_14d_window`
- `after_inject_bad.csv` có `q_refund_window -> hits_forbidden=yes`
- `codex-good-submit` pass toàn bộ expectation và `after_fix_eval.csv` sạch hoàn toàn

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_<run_id>.json` | biết `raw_records`, `cleaned_records`, `quarantine_records`, `latest_exported_at` |
| 2 | Mở `artifacts/logs/run_<run_id>.log` | biết expectation nào fail và pipeline halt ở đâu |
| 3 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` và group theo `reason` | thấy record bị loại do `unknown_doc_id`, `stale_hr_policy_content`, `missing_chunk_text_after_sanitize`... |
| 4 | Chạy `python eval_retrieval.py --out artifacts/eval/<name>.csv` | xác nhận câu nào `contains_expected=no` hoặc `hits_forbidden=yes` |
| 5 | Nếu cần, chạy `python grading_run.py --out artifacts/eval/grading_run.jsonl` | xác nhận 10 câu grading có pass hết hay chưa |

Run tham chiếu:

- bad: `inject-bad-seq`
- good: `codex-good-submit`

---

## Mitigation

Chuỗi xử lý ngắn:

1. Xác nhận failure mode là data issue hay freshness issue.
2. Nếu là data issue:
   - sửa `transform/cleaning_rules.py` hoặc `quality/expectations.py`
   - rerun `python etl_pipeline.py run`
3. Nếu là inject hoặc run xấu đã embed:
   - rerun pipeline chuẩn để publish snapshot tốt mới nhất
   - vì embed có `prune stale ids`, collection sẽ quay về snapshot sạch
4. Chạy lại:
   - `python eval_retrieval.py`
   - `python grading_run.py`
5. Nếu freshness chỉ fail do data mẫu cũ:
   - ghi rõ trong report rằng đây là static snapshot lab data, không phải production lag

Ví dụ mitigation đã dùng:

- run xấu: `python etl_pipeline.py run --run-id inject-bad-seq --no-refund-fix --skip-validate`
- run phục hồi: `python etl_pipeline.py run --run-id codex-good-submit`

---

## Prevention

Các guardrail đã thêm sau fix:

- allowlist mở rộng cho `access_control_sop`
- clean rule loại annual leave stale của HR 2025 theo nội dung, không chỉ theo ngày
- sanitize noisy prefix trước dedupe
- normalize `exported_at` về ISO datetime
- expectation `required_doc_coverage`
- expectation `exported_at_iso_datetime`

Việc nên làm tiếp nếu mở rộng lab:

- đưa cutoff/version mapping ra config thay vì hard-code trong rule
- tách evaluation slice theo source để dễ khoanh vùng hơn
- thêm alert tự động khi `freshness_check=FAIL` nhiều run liên tiếp
