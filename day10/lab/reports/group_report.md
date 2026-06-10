# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** ___________  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| ___ | Ingestion / Raw Owner | ___ |
| ___ | Cleaning & Quality Owner | ___ |
| ___ | Embed & Idempotency Owner | ___ |
| ___ | Monitoring / Docs Owner | ___ |

**Ngày nộp:** 2026-06-10  
**Repo:** `E:\VINAI\2A202600890_PhanQuocAnh_Day10\day10\lab`  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Pipeline của nhóm xử lý một snapshot CSV bẩn `data/raw/policy_export_dirty.csv` mô phỏng export từ nhiều hệ thống nguồn trong domain CS + IT Helpdesk. `etl_pipeline.py` đọc toàn bộ raw rows, áp dụng cleaning rules trong `transform/cleaning_rules.py`, đẩy các record lỗi vào `artifacts/quarantine/`, sau đó chạy expectation suite trong `quality/expectations.py`. Nếu expectation pass, cleaned snapshot sẽ được embed vào Chroma collection `day10_kb`. Sau publish, pipeline ghi manifest chứa `run_id`, số record raw/clean/quarantine, đường dẫn cleaned CSV và metadata của collection. `run_id` được nhìn thấy ngay đầu file log `artifacts/logs/run_<run_id>.log`, đồng thời lặp lại trong manifest và metadata embed. Run tốt cuối cùng dùng để nộp là `codex-good-submit`, với `raw_records=247`, `cleaned_records=32`, `quarantine_records=215`.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

`python etl_pipeline.py run`

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| `sanitize_noisy_prefix` | noisy prefix không bị gom dedupe | `duplicate_chunk_text=63` trong run tốt do nhiều chunk bị chuẩn hoá về cùng nội dung | `artifacts/quarantine/quarantine_codex-good-submit.csv` |
| `stale_hr_policy_content` | baseline cũ còn lọt annual leave bản HR 2025 | `stale_hr_policy_content=25`, expectation HR pass | `artifacts/logs/run_codex-good-submit.log` |
| `normalize_exported_at_iso` | `exported_at` dạng slash tồn tại trong raw | `exported_at_iso_datetime` pass với `bad_exported_at_rows=0` | `artifacts/logs/run_codex-good-submit.log` |
| `required_doc_coverage` | baseline không bảo vệ `access_control_sop` | pass với `missing_docs=[]` | `artifacts/logs/run_codex-good-submit.log` |
| `refund_no_stale_14d_window` | inject có chunk stale refund | `inject-bad-seq` fail `violations=1`, run tốt pass | `run_inject-bad-seq.log`, `run_codex-good-submit.log` |

**Rule chính (baseline + mở rộng):**

- mở rộng allowlist để nhận `access_control_sop`
- sanitize prefix nhiễu như `Nội dung không rõ ràng:` và `!!!`
- normalize `effective_date` và `exported_at`
- loại annual leave stale của HR 2025 theo nội dung chứ không chỉ theo ngày
- chuẩn hoá một số chunk `sla_p1_2026` và `policy_refund_v4` về phrasing canonical để retrieval ổn định hơn
- dedupe sau khi sanitize/normalize để cleaned snapshot gọn và nhất quán

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

Run `inject-bad-seq` cố ý tắt refund fix bằng `--no-refund-fix --skip-validate`. Khi đó expectation `refund_no_stale_14d_window` fail với `violations=1`, nhưng pipeline vẫn embed để đo ảnh hưởng xấu ở retrieval. Sau đó nhóm rerun `codex-good-submit`, expectation này trở lại `OK` và `after_fix_eval.csv` không còn `hits_forbidden`.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Nhóm dùng đúng cơ chế README gợi ý:

`python etl_pipeline.py run --run-id inject-bad-seq --no-refund-fix --skip-validate`

Inject này mô phỏng tình huống data pipeline bỏ qua bước sửa stale refund window. Record bẩn vẫn được embed để xem liệu retrieval có giữ lại context cấm trong top-k hay không. Đây là cách kiểm tra rất đúng tinh thần Day 10: không nhìn mỗi câu trả lời bề mặt, mà nhìn cả context được đưa vào retrieval.

**Kết quả định lượng (từ CSV / bảng):**

Kết quả xấu nằm ở `artifacts/eval/after_inject_bad.csv`. Với câu `q_refund_window`, file eval cho `contains_expected=yes` nhưng `hits_forbidden=yes`, nghĩa là top-k vẫn còn chunk stale chứa cửa sổ hoàn tiền cũ. Sau khi publish lại snapshot tốt bằng `codex-good-submit`, `artifacts/eval/after_fix_eval.csv` cho cùng câu hỏi kết quả `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`. Ngoài ra file `grading_run.jsonl` của run tốt pass toàn bộ 10 câu `gq_d10_01` đến `gq_d10_10`, bao gồm hai câu khó nhất là `gq_d10_09` (HR version conflict) và `gq_d10_10` (`access_control_sop` allowlist). Điều này cho thấy cleaning không chỉ làm pipeline “chạy được”, mà thực sự cải thiện chất lượng knowledge được đưa vào retrieval.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

Nhóm giữ `sla_hours=24` trong contract và dùng `monitoring/freshness_check.py` để đọc `latest_exported_at` từ manifest publish. Với run tốt `codex-good-submit`, freshness ra `FAIL` vì `latest_exported_at=2026-04-10T00:00:00` trong khi ngày chạy lab là 2026-06-10. Đây không phải bug của code, mà là tín hiệu đúng cho thấy snapshot lab data đã cũ so với SLA 24 giờ. Theo đúng FAQ trong `SCORING.md`, nhóm diễn giải FAIL này là “snapshot stale but pipeline healthy”: pipeline vẫn clean/validate/embed đúng, nhưng input data intentionally old. Điều này cũng cho thấy runbook cần phân biệt data freshness với pipeline correctness.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Có. Day 10 dùng cùng domain CS + IT Helpdesk như Day 09, nhưng tập trung sửa upstream data quality trước khi worker retrieval đọc vào vector store. Nhóm tách collection `day10_kb` để dễ quan sát before/after và tránh lẫn với artifact Day 09. Về mặt kiến trúc, output của Day 10 là một snapshot knowledge sạch hơn mà retrieval worker của Day 09 có thể dùng thay cho collection cũ.

---

## 6. Rủi ro còn lại & việc chưa làm

- cutoff/version logic của HR vẫn đang được encode trong cleaning rule, chưa externalize hoàn toàn sang config
- freshness hiện mới đo ở boundary publish, chưa có ingest watermark riêng
- report cá nhân và tên thành viên thực tế cần nhóm tự điền trước khi nộp
