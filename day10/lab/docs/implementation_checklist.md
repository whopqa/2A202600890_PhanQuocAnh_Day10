# Implementation Checklist — Day 10 Lab

Tài liệu này chuyển yêu cầu trong [README](../README.md) thành checklist thực thi theo đúng logic repo hiện tại.
Mục tiêu là giúp bạn đi từ trạng thái baseline đang lỗi đến trạng thái:

- `python etl_pipeline.py run` exit `0`
- đủ dữ liệu cho toàn bộ `grading_questions.json`
- có before/after evidence cho retrieval
- hoàn thành docs, contract, runbook và report theo rubric Day 10

---

## 1. Hiểu đích cuối cùng của lab

### Việc cần làm

- Đọc `day10/lab/README.md`
- Đọc `day10/lab/SCORING.md`
- Đọc `day10/lab/data/grading_questions.json`

### Tại sao làm bước này

- Lab Day 10 không chấm riêng chuyện "pipeline có chạy" mà chấm cả chất lượng dữ liệu feeding vào vector store.
- Nếu chỉ sửa để pipeline không halt mà không quan tâm grading coverage, bạn vẫn có thể trượt các câu khó như HR version conflict hoặc access control.

### Liên quan tới logic repo hiện tại

- `etl_pipeline.py` đang chỉ là entrypoint orchestration cho `ingest -> clean -> validate -> embed`.
- `grading_run.py` mới là file phản ánh trực tiếp liệu cleaned data đã đủ để phục vụ retrieval hay chưa.
- `SCORING.md` nói rõ hai điểm khó nhất là:
  - HR version conflict
  - `access_control_sop` allowlist

### Liên hệ kiến thức Day 10

- Đây chính là tinh thần "debug data trước khi debug model".
- Day 10 nhấn mạnh 5 trụ observability; ở lab này bạn sẽ chạm trực tiếp vào:
  - freshness
  - volume
  - schema
  - lineage qua `run_id`

### Lệnh nên chạy

```bash
cd day10/lab
python etl_pipeline.py run
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

---

## 2. Chụp baseline trước khi sửa

### Việc cần làm

- Chạy pipeline baseline và lưu log
- Ghi lại số lượng:
  - `raw_records`
  - `cleaned_records`
  - `quarantine_records`
  - expectation nào fail

### Tại sao làm bước này

- Bạn cần mốc "trước khi sửa" để chứng minh từng rule mới có tác động thật.
- Rubric Day 10 chống trivial change, nên mọi rule/expectation mới cần gắn với số liệu hoặc artifact cụ thể.

### Liên quan tới logic repo hiện tại

- `etl_pipeline.py` đã log đủ các chỉ số quan trọng và ghi vào `artifacts/logs/`.
- Baseline hiện tại đang halt vì expectation HR.

### Liên hệ kiến thức Day 10

- Đây là bước quan sát volume/error signals trước khi sửa transform.
- Nó tương ứng với thứ tự debug trong README:
  - freshness/version
  - volume/errors
  - schema/contract
  - lineage/run_id

### Lệnh nên chạy

```bash
cd day10/lab
python etl_pipeline.py run
```

### Kết quả baseline bạn nên kỳ vọng

```text
raw_records=247
cleaned_records=40
quarantine_records=207
expectation[hr_leave_no_stale_10d_annual] FAIL
PIPELINE_HALT
```

---

## 3. Phân tích coverage của raw data

### Việc cần làm

- Liệt kê toàn bộ `doc_id` trong raw CSV
- Đếm số record theo `doc_id`
- So sánh với allowlist trong `transform/cleaning_rules.py`
- So sánh tiếp với `expect_top1_doc_id` trong `grading_questions.json`

### Tại sao làm bước này

- Đây là cách xác định nguồn nào hợp lệ nhưng đang bị pipeline bỏ qua.
- Đó là bug dạng "data missing from ingest path", rất điển hình trong ETL.

### Liên quan tới logic repo hiện tại

- `ALLOWED_DOC_IDS` hiện chỉ chứa:
  - `policy_refund_v4`
  - `sla_p1_2026`
  - `it_helpdesk_faq`
  - `hr_leave_policy`
- Nhưng grading cần thêm `access_control_sop`.

### Liên hệ kiến thức Day 10

- Đây là phần source mapping và contract thinking:
  - nguồn nào là canonical
  - nguồn nào phải được publish
  - nguồn nào cần quarantine

### Lệnh nên chạy

```powershell
$rows = Import-Csv 'data/raw/policy_export_dirty.csv'
$rows | Group-Object doc_id | Sort-Object Name | ForEach-Object {
  '{0},{1}' -f $_.Name, $_.Count
}
```

### Kết luận bạn cần rút ra

- `access_control_sop` là nguồn hợp lệ vì:
  - có file canonical trong `data/docs/access_control_sop.txt`
  - xuất hiện trong README
  - được yêu cầu làm top-1 trong grading
- `invalid_doc_*`, `legacy_*` không phải nguồn canonical của bài, nên nên tiếp tục quarantine.

---

## 4. Sửa allowlist và contract để pipeline nhận đúng nguồn

### Việc cần làm

- Thêm `access_control_sop` vào:
  - `transform/cleaning_rules.py`
  - `contracts/data_contract.yaml`
- Thêm nó vào phần source map trong `docs/data_contract.md`

### Tại sao làm bước này

- Nếu không cho phép nguồn này đi qua clean và embed, câu `gq_d10_10` sẽ không thể pass.

### Liên quan tới logic repo hiện tại

- `clean_rows()` quarantine mọi dòng có `doc_id` không nằm trong `ALLOWED_DOC_IDS`.
- `grading_run.py` kiểm tra `top1_doc_matches`, nên không chỉ cần có dữ liệu đúng mà còn cần đúng doc được embed.

### Liên hệ kiến thức Day 10

- Đây là ví dụ thực tế của schema governance và data contract:
  - contract phải khớp pipeline
  - pipeline phải khớp retrieval requirement

### Code nên sửa

```python
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)
```

```yaml
canonical_sources:
  - path: "data/docs/access_control_sop.txt"
    doc_id: "access_control_sop"

allowed_doc_ids:
  - access_control_sop
```

### Cách verify

```powershell
python etl_pipeline.py run
Import-Csv artifacts/quarantine/*.csv | Where-Object { $_.doc_id -eq 'access_control_sop' }
```

Kết quả mong đợi:

- `access_control_sop` không còn bị quarantine vì `unknown_doc_id`
- các dòng xấu của nó chỉ bị quarantine vì lý do hợp lệ như `missing_chunk_text`

---

## 5. Sửa rule stale HR theo nội dung, không chỉ theo ngày

### Việc cần làm

- Bổ sung cleaning rule để loại bỏ các chunk `hr_leave_policy` mang nội dung cũ của HR 2025
- Không chỉ dựa vào `effective_date`
- Dùng thêm tín hiệu nội dung, ví dụ:
  - chứa `bản HR 2025`
  - hoặc câu dưới 3 năm kinh nghiệm = `10 ngày phép năm`

### Tại sao làm bước này

- Raw data đang có anomaly kiểu "export mới nhưng nội dung cũ".
- Đây là failure mode rất sát thực tế doanh nghiệp: timestamp mới không đảm bảo semantic version mới.

### Liên quan tới logic repo hiện tại

- Baseline hiện chỉ có rule:
  - quarantine `hr_leave_policy` nếu `effective_date < 2026-01-01`
- Nhưng raw vẫn chứa các dòng kiểu:
  - `Nhân viên dưới 3 năm kinh nghiệm được 10 ngày phép năm (bản HR 2025).`
  - với `effective_date = 2026-...`
- Vì vậy dữ liệu stale lọt vào cleaned, làm expectation hiện tại fail.

### Liên hệ kiến thức Day 10

- Đây là phần versioning và semantic data quality.
- Day 10 không chỉ nói đến schema error mà còn nói đến stale knowledge trong pipeline.

### Code nên thêm

```python
def _is_stale_hr_annual_leave(text: str) -> bool:
    t = _norm_text(text)
    if "bản hr 2025" in t:
        return True
    if "dưới 3 năm kinh nghiệm" in t and "10 ngày phép năm" in t:
        return True
    return False
```

```python
if doc_id == "hr_leave_policy" and _is_stale_hr_annual_leave(text):
    quarantine.append(
        {
            **raw,
            "reason": "stale_hr_policy_content",
            "effective_date_normalized": eff_norm,
        }
    )
    continue
```

### Cách verify

```powershell
python etl_pipeline.py run
rg -n "10 ngày phép năm|bản HR 2025" artifacts/cleaned
```

Kết quả mong đợi:

- cleaned không còn annual leave bản cũ
- cleaned vẫn giữ lại `Nghỉ ốm: 10 ngày/năm có trả lương`

---

## 6. Sửa expectation HR để đúng business rule hơn

### Việc cần làm

- Thay expectation đang check quá rộng bằng check đúng nghĩa vụ nghiệp vụ:
  - không còn annual leave cũ của HR 2025
  - vẫn cho phép sick leave 10 ngày

### Tại sao làm bước này

- Một expectation tốt phải phân biệt được dữ liệu sai với dữ liệu hợp lệ trông hơi giống nhau.
- Nếu expectation quá rộng, pipeline sẽ halt sai và làm bạn mất điểm dù clean logic gần đúng.

### Liên quan tới logic repo hiện tại

- `quality/expectations.py` hiện fail nếu `chunk_text` chứa `10 ngày phép năm`.
- Điều này đang đúng một phần, nhưng chưa biểu diễn rõ luật nghiệp vụ.

### Liên hệ kiến thức Day 10

- Đây là "data quality as code":
  - expectation phải phản ánh business rule
  - không chỉ là regex đơn giản

### Code nên sửa

```python
bad_hr_annual = [
    r
    for r in cleaned_rows
    if r.get("doc_id") == "hr_leave_policy"
    and "dưới 3 năm kinh nghiệm" in (r.get("chunk_text") or "").lower()
    and "10 ngày phép năm" in (r.get("chunk_text") or "").lower()
]
```

Hoặc chặt hơn:

```python
bad_hr_annual = [
    r
    for r in cleaned_rows
    if r.get("doc_id") == "hr_leave_policy"
    and (
        "bản hr 2025" in (r.get("chunk_text") or "").lower()
        or (
            "dưới 3 năm kinh nghiệm" in (r.get("chunk_text") or "").lower()
            and "10 ngày phép năm" in (r.get("chunk_text") or "").lower()
        )
    )
]
```

### Cách verify

```bash
python etl_pipeline.py run
```

Kết quả mong đợi:

- expectation HR pass
- sick leave 10 ngày vẫn còn dùng được cho retrieval

---

## 7. Thêm 3 cleaning rule mới có tác động đo được

### Việc cần làm

- Chọn tối thiểu 3 rule mới ngoài baseline
- Ưu tiên những rule có ảnh hưởng rõ trên:
  - `cleaned_records`
  - `quarantine_records`
  - expectation results
  - eval results

### Gợi ý rule 1: bỏ prefix nhiễu trước dedupe

#### Tại sao

- Raw có nhiều dòng kiểu:
  - `Nội dung không rõ ràng: ...`
  - `!!!...`
- Nếu không normalize trước, dedupe theo text sẽ kém hiệu quả và retrieval có thể lấy chunk nhiễu làm top-1.

#### Liên quan repo

- Baseline dedupe đang dùng `_norm_text(text)` nhưng chưa strip noise prefix.

#### Code gợi ý

```python
def _sanitize_chunk_text(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^Nội dung không rõ ràng:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^!+\s*", "", s)
    return " ".join(s.split())
```

Sau đó áp dụng trước mọi logic dedupe và stale detection:

```python
text = _sanitize_chunk_text(raw.get("chunk_text", ""))
```

### Gợi ý rule 2: validate `exported_at`

#### Tại sao

- Raw có `exported_at` dạng `2026/04/11T00:00:00`.
- Contract yêu cầu `exported_at` là datetime; nếu để giá trị bẩn đi qua, freshness logic và downstream audit sẽ khó tin cậy.

#### Liên quan repo

- `cleaning_rules.py` hiện normalize `effective_date` nhưng chưa kiểm `exported_at`.
- `freshness_check.py` dựa vào manifest `latest_exported_at`, nên timestamp xấu có thể làm monitor sai.

#### Code gợi ý

```python
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_YMD_SLASH_DATETIME = re.compile(r"^(\d{4})/(\d{2})/(\d{2})T(\d{2}):(\d{2}):(\d{2})$")

def _normalize_exported_at(raw: str) -> tuple[str, str]:
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
```

### Gợi ý rule 3: quarantine chunk chỉ còn noise sau sanitize

#### Tại sao

- Có các dòng như `Nội dung không rõ ràng: ` hoặc chuỗi rỗng.
- Sau sanitize chúng thực chất không còn nội dung business.

#### Liên quan repo

- Baseline mới check `if not text`, nhưng nếu sanitize mới làm text rỗng thì cần check lại sau sanitize.

#### Code gợi ý

```python
if not text:
    quarantine.append({**raw, "reason": "missing_chunk_text_after_sanitize"})
    continue
```

### Cách ghi vào report

- Rule mới phải có metric impact cụ thể, ví dụ:
  - `duplicate_chunk_text` tăng sau khi sanitize prefix
  - `invalid_exported_at_format` xuất hiện khi inject
  - `cleaned_records` giảm vì stale HR bị loại đúng hơn

---

## 8. Thêm 2 expectation mới đúng tinh thần observability

### Việc cần làm

- Thêm tối thiểu 2 expectation mới
- Một expectation nên kiểm coverage tài liệu cần cho grading
- Một expectation nên kiểm timestamp/schema quan trọng

### Gợi ý expectation 1: đủ doc coverage cho grading

#### Tại sao

- Nếu pipeline vô tình bỏ một doc canonical, retrieval sẽ sai dù các row còn lại hoàn toàn hợp lệ.

#### Liên quan repo

- Đây là đúng failure mode của `access_control_sop`.

#### Code gợi ý

```python
required_docs = {
    "policy_refund_v4",
    "sla_p1_2026",
    "it_helpdesk_faq",
    "hr_leave_policy",
    "access_control_sop",
}
present_docs = {r.get("doc_id", "") for r in cleaned_rows}
missing_docs = sorted(required_docs - present_docs)
results.append(
    ExpectationResult(
        "required_doc_coverage",
        len(missing_docs) == 0,
        "halt",
        f"missing_docs={missing_docs}",
    )
)
```

### Gợi ý expectation 2: `exported_at` phải parse được

#### Tại sao

- Freshness chỉ đáng tin khi timestamp publish/export nhất quán.

#### Liên quan repo

- `freshness_check.py` đang parse ISO timestamp; expectation này giúp fail sớm trước khi monitor đọc manifest.

#### Code gợi ý

```python
exported_bad = [
    r for r in cleaned_rows
    if "T" not in (r.get("exported_at") or "")
]
results.append(
    ExpectationResult(
        "exported_at_datetime_like",
        len(exported_bad) == 0,
        "halt",
        f"bad_exported_at_rows={len(exported_bad)}",
    )
)
```

### Liên hệ kiến thức Day 10

- Đây là cách biến observability rule thành code chạy trong pipeline thay vì đợi lỗi ra production mới thấy.

---

## 9. Rerun pipeline đến khi exit 0

### Việc cần làm

- Chạy lại pipeline sau từng đợt sửa
- Kiểm tra:
  - file cleaned
  - file quarantine
  - expectation log
  - manifest

### Tại sao làm bước này

- ETL repair là vòng lặp:
  - observe
  - patch rule
  - validate
  - rerun

### Liên quan repo hiện tại

- `etl_pipeline.py` đã viết sẵn cleaned CSV, quarantine CSV, manifest và log.
- Bạn không cần tự dựng framework khác; chỉ cần dùng artifact sẵn có.

### Liên hệ kiến thức Day 10

- Đây là pattern orchestration + idempotent rerun.
- Pipeline tốt phải rerun được mà không làm index phình vì `cmd_embed_internal()` đã `upsert` theo `chunk_id` và prune stale ids.

### Lệnh nên chạy

```bash
python etl_pipeline.py run
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json
```

### Định nghĩa xong bước này

- `python etl_pipeline.py run` trả về exit code `0`
- log có `PIPELINE_OK`
- expectation halt không còn fail

---

## 10. Chạy eval retrieval để chứng minh data fix có ý nghĩa

### Việc cần làm

- Chạy eval sau bản fix tốt
- Chạy inject corruption theo đúng README
- So sánh before/after

### Tại sao làm bước này

- Lab này không chỉ yêu cầu clean data đúng, mà còn yêu cầu chứng minh data quality ảnh hưởng trực tiếp đến retrieval quality.

### Liên quan repo hiện tại

- `eval_retrieval.py` kiểm:
  - `contains_expected`
  - `hits_forbidden`
  - `top1_doc_expected`
- `grading_run.py` là bản grading chính thức 10 câu.

### Liên hệ kiến thức Day 10

- Đây là phần "before-after evidence" của observability loop:
  - phát hiện lỗi dữ liệu
  - sửa pipeline
  - chứng minh downstream cải thiện

### Lệnh nên chạy

```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv

python etl_pipeline.py run
python eval_retrieval.py --out artifacts/eval/after_fix_eval.csv
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

### Điều cần kiểm

- refund:
  - sau inject có thể dính `14 ngày`
  - sau fix phải hết `14 ngày`
- HR:
  - phải ra `12 ngày` cho annual leave dưới 3 năm
  - không dính annual leave `10 ngày`
- access:
  - top-1 của `gq_d10_10` phải là `access_control_sop`

---

## 11. Điền data contract và docs theo artifact thật

### Việc cần làm

- Điền `contracts/data_contract.yaml`
  - `owner_team`
  - `alert_channel`
  - `canonical_sources`
  - `allowed_doc_ids`
- Điền:
  - `docs/pipeline_architecture.md`
  - `docs/data_contract.md`
  - `docs/runbook.md`
  - `docs/quality_report_template.md` theo run thật
  - `reports/group_report.md`

### Tại sao làm bước này

- Đây là phần deliverable bắt buộc chứ không phải phụ lục.
- Nếu code đúng nhưng docs trống, bài vẫn thiếu điểm đáng kể.

### Liên quan repo hiện tại

- Các file docs trong repo đều là template chờ điền.
- Chúng phải phản ánh artifact thật trong `artifacts/`, không được ghi chung chung.

### Liên hệ kiến thức Day 10

- Day 10 coi data system là một sản phẩm vận hành:
  - phải có owner
  - phải có SLA
  - phải có runbook
  - phải có incident evidence

### Nội dung tối thiểu nên ghi

- `pipeline_architecture.md`
  - luồng raw -> clean -> validate -> embed -> serve
  - chỗ sinh `run_id`
  - chỗ sinh quarantine
  - chỗ freshness đo
- `data_contract.md`
  - source map ít nhất 2 nguồn
  - failure mode
  - metric/alert
- `runbook.md`
  - symptom: agent trả lời `14 ngày` hoặc annual leave sai
  - detection: expectation fail, grading fail, `hits_forbidden=yes`
  - diagnosis: kiểm manifest, quarantine, eval
  - mitigation: rerun clean pipeline
  - prevention: thêm expectation/rule

---

## 12. Checklist chốt bài trước khi nộp

- `python etl_pipeline.py run` exit `0`
- `python grading_run.py --out artifacts/eval/grading_run.jsonl` chạy thành công
- `artifacts/eval/grading_run.jsonl` có đủ 10 dòng
- `gq_d10_09` pass:
  - `contains_expected=true`
  - `hits_forbidden=false`
  - `top1_doc_matches=true`
- `gq_d10_10` pass:
  - `contains_expected=true`
  - `hits_forbidden=false`
  - `top1_doc_matches=true`
- có 2 file eval so sánh inject vs fixed
- docs đã điền bằng artifact thật
- group report có bảng `metric_impact`

---

## 13. Thứ tự làm nhanh nhất nếu bạn muốn tối ưu thời gian

1. Chạy baseline và chụp log.
2. Thêm `access_control_sop` vào allowlist + contract.
3. Sửa stale HR theo nội dung.
4. Sửa expectation HR cho đúng business rule.
5. Thêm 3 cleaning rule mới có metric impact.
6. Thêm 2 expectation mới.
7. Rerun đến khi `etl_pipeline.py run` exit `0`.
8. Chạy inject bad + eval before/after.
9. Chạy grading chính thức.
10. Điền docs/report bằng số liệu và `run_id` thật.

---

## 14. Gợi ý phân vai nếu làm nhóm

- Ingestion Owner:
  - phân tích raw CSV
  - doc_id coverage
  - manifest/log
- Cleaning/Quality Owner:
  - `transform/cleaning_rules.py`
  - `quality/expectations.py`
  - quarantine evidence
- Embed Owner:
  - rerun pipeline
  - eval/grading
  - kiểm idempotent/prune
- Monitoring/Docs Owner:
  - freshness
  - contract
  - runbook
  - report

---

## 15. Điểm mấu chốt cần nhớ

- Bug lớn nhất hiện tại không chỉ là pipeline halt, mà là halt sai kiểu business:
  - rule HR chưa đủ semantic
- Gap lớn nhất với grading là coverage:
  - thiếu `access_control_sop` trong allowlist
- Điểm Day 10 không nằm ở việc thêm nhiều rule thật nhanh, mà ở chỗ:
  - rule có tác động đo được
  - expectation phản ánh business rule
  - fix dữ liệu tạo ra cải thiện retrieval có bằng chứng
