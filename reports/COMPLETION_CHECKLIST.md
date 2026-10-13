# Checklist Lab 25B

Trần Quốc Vượng — 2A202602522. Ngày thực hiện: 13/10/2026 (UTC+07:00).
Phiên bản nộp đủ source/evidence/report: tag `day25-submission-20261013-r2`.

- [x] Đọc README, rubric và các hợp đồng event/virtual time.
- [x] Part A: phân loại lỗi, full jitter, retry-after và token-bucket retry budget.
- [x] Part B: sliding window failure/slow rate, HALF-OPEN giới hạn probes, stale-generation protection.
- [x] Part C: một tầng retry, deadline, shared cooldown, fallback có lọc tool calling.
- [x] G1–G6 đều PASS trên các seed public 25, 26, 27; lưu JSON và CSV.
- [x] Part D: checkpoint sau thành công, stable idempotency key, resume sau crash;
  500/500 hoàn tất, không duplicate/lost refunds hoặc email, wasted LLM/crash=0,303 (seed 25).
- [x] Part E: prefix sums, ba rule burn-rate, error budget; public SLI có 0 false page.
- [x] Part G: cache theo prompt scope/non-personal, cosine threshold, TTL/stale window, LRU, invalidation.
- [x] Băng C1 PASS trên seed 25/26/27; wrong_answers=0, outdated_answers=2/4/7.
- [x] Part F: report đủ 8 mục; postmortem G2 có hình và ≥5 mốc timeline từ CSV.
- [x] Chạy thí nghiệm budget/breaker, timeout30, capability filter, threshold, TTL và stale-if-error;
  giữ control thất bại và số đo thật trong `experiments.json`.
- [x] 82 tests được cấp và 6 regression bổ sung đạt; không sửa test được cấp.
- [x] Lint/type check các module triển khai và dependency check đạt.
- [x] `scoreboard.json`: 84/88; 4 điểm hidden SLO chưa có dữ liệu để xác minh,
  12 điểm report chấm tay chưa được tự cộng.
- [x] Simulator/scenarios/services/naive clients/data giữ nguyên; chỉ tune client/cache trong world config.
- [x] Source, JSON, CSV, hình và report được đóng gói; `.venv`, cache và `.env` không đưa vào Git.

Lab mô phỏng độc lập, không cần API key hay Docker. Số liệu không được trình bày như đo từ API production.
Repo được chuẩn bị để người học nộp theo kênh của lớp; chưa khai đã nộp Day25.
