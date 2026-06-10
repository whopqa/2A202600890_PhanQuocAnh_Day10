# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Phan Quốc Anh  
**Vai trò:** Cleaning / Quality — sửa cleaning rules, expectation suite, và kiểm chứng bằng eval  
**Ngày nộp:** 2026-06-10  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `transform/cleaning_rules.py`
- `quality/expectations.py`
- `contracts/data_contract.yaml`
- một phần đối chiếu artifact trong `artifacts/eval/` và `artifacts/logs/`

Tôi phụ trách chính phần clean và quality. Công việc cụ thể của tôi là đọc raw CSV để tìm anomaly, mở rộng allowlist cho `access_control_sop`, thêm rule loại annual leave stale của HR 2025 theo nội dung, sanitize các prefix nhiễu như `Nội dung không rõ ràng:` và `!!!`, đồng thời thêm expectation mới để chặn thiếu coverage tài liệu và lỗi `exported_at`. Tôi cũng dùng `eval_retrieval.py` và `grading_run.py` để kiểm tra xem việc sửa data layer có thực sự cải thiện retrieval hay không.

**Kết nối với thành viên khác:**

Tôi bàn giao cleaned snapshot ổn định và expectation suite rõ ràng để phần embed chạy được trên collection `day10_kb`, sau đó nhóm dùng chung artifact để viết docs và report.

**Bằng chứng (commit / comment trong code):**

Bằng chứng trực tiếp là các thay đổi nằm trong `transform/cleaning_rules.py` và `quality/expectations.py`, cùng log run tốt `artifacts/logs/run_codex-good-submit.log`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định kỹ thuật quan trọng nhất của tôi là phân biệt rõ rule nào nên là `halt` và rule nào chỉ nên là `warn`. Tôi chọn các lỗi có thể làm retrieval trả lời sai kiến thức nghiệp vụ là `halt`, ví dụ `refund_no_stale_14d_window`, `hr_leave_no_stale_10d_annual`, `required_doc_coverage`, và `exported_at_iso_datetime`. Ngược lại, `chunk_min_length_8` chỉ để `warn` vì chunk ngắn chưa chắc làm sai toàn bộ pipeline. Lý do tôi chọn như vậy là Day 10 nhấn mạnh “data quality as code”: expectation phải phản ánh mức độ rủi ro thật của dữ liệu downstream. Nếu `access_control_sop` bị thiếu hoặc HR 2025 lọt vào cleaned thì agent Day 09 đọc đúng prompt vẫn có thể trả lời sai. Ở run tốt `codex-good-submit`, toàn bộ expectation `halt` đều `OK`, còn freshness vẫn `FAIL` vì snapshot lab data cũ, không phải vì pipeline lỗi.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Lỗi rõ nhất tôi xử lý là conflict version trong `hr_leave_policy`. Baseline ban đầu chỉ quarantine theo `effective_date < 2026-01-01`, nhưng raw CSV có nhiều dòng “Nhân viên dưới 3 năm kinh nghiệm được 10 ngày phép năm (bản HR 2025)” lại mang ngày `2026-...`, nên vẫn lọt vào cleaned. Triệu chứng là pipeline halt ở expectation HR. Sau khi tôi thêm rule `stale_hr_policy_content` trong `transform/cleaning_rules.py`, annual leave bản cũ bị loại theo nội dung thay vì chỉ theo ngày. Kết quả ở run tốt `codex-good-submit` cho thấy `expectation[hr_leave_no_stale_10d_annual] OK (halt) :: violations=0`. Đồng thời quarantine cũng ghi nhận rõ anomaly này với `stale_hr_policy_content=25`, giúp tôi chứng minh rule mới có tác động đo được chứ không phải thay đổi hình thức.

---

## 4. Bằng chứng trước / sau (80–120 từ)

Tôi dùng hai run để so sánh:

- Run xấu: `inject-bad-seq`
- Run tốt: `codex-good-submit`

Ở `artifacts/eval/after_inject_bad.csv`, câu `q_refund_window` có `contains_expected=yes` nhưng `hits_forbidden=yes`. Điều đó nghĩa là top-k vẫn còn chunk stale về refund window dù nhìn bề mặt có vẻ đúng. Sau khi rerun pipeline chuẩn, `artifacts/eval/after_fix_eval.csv` cho cùng câu hỏi kết quả là `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`. Ngoài ra file `artifacts/eval/grading_run.jsonl` của run tốt pass đủ 10 câu, trong đó `gq_d10_09` và `gq_d10_10` đều có `top1_doc_matches=true`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi muốn đưa rule versioning của HR ra config hoặc contract thay vì hard-code trong cleaning rule. Như vậy pipeline sẽ dễ bảo trì hơn khi policy đổi version mới, và nhóm có thể chứng minh tốt hơn phần “versioning không hard-code” trong rubric Distinction.
