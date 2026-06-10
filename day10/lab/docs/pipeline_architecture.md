# Kiến trúc pipeline — Lab Day 10

**Nhóm:** _______________  
**Cập nhật:** 2026-06-10

---

## 1. Sơ đồ luồng (bắt buộc có 1 diagram: Mermaid / ASCII)

```
raw export CSV
  -> ingest by etl_pipeline.py
  -> clean in transform/cleaning_rules.py
  -> quarantine bad rows to artifacts/quarantine/
  -> validate in quality/expectations.py
  -> embed cleaned snapshot to Chroma day10_kb
  -> serve retrieval for Day 10 eval / Day 09-style helpdesk queries
```

**Điểm đo observability trong repo hiện tại**

- `run_id` được sinh ở `etl_pipeline.py run` và ghi vào log + manifest.
- `raw_records`, `cleaned_records`, `quarantine_records` được log ngay sau bước clean.
- `quarantine` được ghi ra `artifacts/quarantine/quarantine_<run_id>.csv`.
- `freshness` được đo sau publish từ `latest_exported_at` trong manifest.

**Run tốt tham chiếu**

- `run_id=codex-good-submit`
- `raw_records=247`
- `cleaned_records=32`
- `quarantine_records=215`
- `manifest=artifacts/manifests/manifest_codex-good-submit.json`

---

## 2. Ranh giới trách nhiệm

| Thành phần | Input | Output | Owner nhóm |
|------------|-------|--------|--------------|
| Ingest | `data/raw/policy_export_dirty.csv` | danh sách row raw | Ingestion Owner |
| Transform | row raw + allowlist/rules | cleaned rows + quarantine rows | Cleaning Owner |
| Quality | cleaned rows | expectation results + halt/no-halt | Quality Owner |
| Embed | cleaned CSV | Chroma collection `day10_kb` | Embed Owner |
| Monitor | manifest publish | `PASS/WARN/FAIL` freshness | Monitoring Owner |

---

## 3. Idempotency & rerun

Pipeline embed theo snapshot publish:

- `chunk_id` được sinh ổn định từ `doc_id + chunk_text + seq`.
- Khi rerun, Chroma `upsert(ids=chunk_id)` nên không phình duplicate vector cho cùng snapshot.
- Trước khi upsert, pipeline lấy danh sách id cũ và `delete()` các id không còn trong cleaned hiện tại.
- Vì vậy index sau publish phản ánh đúng cleaned snapshot của run mới nhất, không giữ vector stale.

Ví dụ:

- `inject-bad-seq` có `embed_upsert count=32`
- `codex-good-submit` có `embed_prune_removed=1`, rồi `embed_upsert count=32`

Điều này chứng minh rerun không chỉ idempotent mà còn có prune stale ids.

---

## 4. Liên hệ Day 09

Day 10 đứng trước Day 09 trong chuỗi giá trị dữ liệu:

- Day 09 tập trung supervisor/worker và retrieval orchestration.
- Day 10 đảm bảo dữ liệu feed vào retrieval đã được clean, validate và publish theo snapshot có `run_id`.
- Cùng domain CS + IT Helpdesk, nhưng Day 10 dùng export CSV bẩn để mô phỏng lớp ingestion thật từ nhiều hệ thống.
- Sau khi embed xong vào Chroma `day10_kb`, retrieval test của Day 10 có thể được xem như phiên bản "data-ready" cho các agent Day 09 đọc đúng version hơn.

---

## 5. Rủi ro đã biết

- `freshness_check=FAIL` trên data mẫu là hợp lý vì `latest_exported_at=2026-04-10T00:00:00` cũ hơn SLA 24 giờ.
- Rule versioning HR hiện vẫn hard-code logic theo nội dung "bản HR 2025"; nếu domain mở rộng nên đưa mapping/version cutoff ra contract hoặc config.
- Cleaning hiện có một số normalization theo phrasing đặc thù (`policy_refund_v4`, `sla_p1_2026`); nếu schema nguồn đổi mạnh thì cần cập nhật rule.
