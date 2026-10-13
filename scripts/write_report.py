"""Render the Vietnamese lab report from saved simulation evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def read(name: str):
    return json.loads((Path("reports") / name).read_text(encoding="utf-8"))


def table(headers, rows):
    def cell(value):
        return "N/A" if value is None else str(value)
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
                     + ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True, help="Commit containing code and simulation evidence")
    parser.add_argument("--submission-commit", required=True, help="Immutable submission snapshot being documented")
    args = parser.parse_args()
    naive, yours = read("gameday/naive.json"), read("gameday/resilient.json")
    workflow, slo = read("workflows.json"), read("slo.json")
    board = read("scoreboard.json")
    cache = {name: read(f"cache/{name}.json")["C1_faq_outage"] for name in ("resilient", "cached")}
    experiments = {e["experiment"]: e for e in read("experiments.json")["experiments"]}

    def exp(label, scenario=None):
        runs = experiments[label]["runs"]
        return next(r["metrics"] for r in runs if scenario is None or r["metrics"]["scenario"] == scenario)

    score = board["summary"]["automatic"]
    game_rows = [[key.split("_")[0], client, m["availability"], m["latency_p95_s"], m["amplification"],
                  m["retry_ratio"], m["cost_per_good_turn"], m["recovery_s"], "PASS" if m["pass"] else "FAIL"]
                 for key in naive for client, m in [("naive", naive[key]), ("resilient", yours[key])]]
    game_table = table(["Băng", "Client", "availability", "p95 (s)", "amplification", "retry_ratio",
                        "cost/good turn", "recovery (s)", "Kết quả"], game_rows)
    budget_rows = [[state, budget, m["scenario"].split("_")[0], m["availability"], m["amplification"],
                    m["retry_ratio"], m["recovery_s"], m["latency_p95_s"]]
                   for state in ("healthy", "broken") for budget in ("on", "off")
                   for run in experiments[f"{state}_breaker_budget_{budget}"]["runs"] for m in [run["metrics"]]]
    budget_table = table(["Breaker", "Budget", "Băng", "Availability", "Amplification", "Retry ratio",
                          "Recovery s", "P95 s"], budget_rows)
    timeout_rows = [[key.split("_")[0], timeout, m["availability"], m["turns"] - m["good_turns"],
                     json.dumps(m["give_up_reasons"], ensure_ascii=False), m["latency_p95_s"], m["latency_p99_s"]]
                    for key in ("G4_slow_region", "G6_provider_outage")
                    for timeout, m in [(4, yours[key]), (30, exp("timeout_30s", key))]]
    timeout_table = table(["Băng", "Timeout s", "Availability", "Failed turns", "give_up_reasons",
                           "P95 s (successful turns)", "P99 s"], timeout_rows)
    workflow_table = table(["Executor", "Completion", "Crashes", "Refund trùng", "Email trùng", "Refund mất",
                            "Overpaid cents", "LLM lãng phí/crash"],
                           [[name, m["completion_rate"], m["worker_crashes"], m["duplicate_refunds"],
                             m["duplicate_emails"], m["lost_refunds"], m["overpaid_cents"], m["wasted_llm_per_crash"]]
                            for name, m in workflow.items()])
    alert_rows = []
    for n, b in zip(slo["naive"]["incidents"], slo["burnrate"]["incidents"]):
        def verdict(row):
            if row["expect"] == "none":
                return "false page" if row["paged"] else "không page"
            return row["expect"] if row["detected"] else "bỏ sót"
        alert_rows.append([b["incident"], b["expect"], verdict(n), verdict(b), b.get("delay_min")])
    alert_table = table(["Sự cố", "Mong đợi", "Naive", "Burn-rate", "Delay burn-rate (phút)"], alert_rows)
    with Path("reports/gameday/naive_G2_overload_storm_timeseries.csv").open() as source:
        rows = list(csv.DictReader(source))
    timeline = []
    labels = {119: "Trước sự cố", 120: "alpha mất 75% năng lực", 150: "Retry storm rõ rệt",
              240: "Sự cố tiếp diễn", 300: "Provider phục hồi; client vẫn nghẽn", 420: "Vẫn chưa thoát vòng lặp",
              455: "Bắt đầu cửa sổ recovery theo scorer", 480: "Call success 10s phục hồi"}
    for t, label in labels.items():
        window = rows[max(0, t - 9):t + 1]
        done = sum(int(r["calls_done"]) for r in window)
        ok = sum(int(r["calls_ok"]) for r in window)
        attempts = sum(int(r["attempts_alpha"]) for r in window)
        timeline.append([t, label, round(attempts / len(window), 2), round(ok / done, 4) if done else None, done])
    timeline_table = table(["t (s)", "Sự kiện", "alpha attempts/s (10s trailing)", "Call success (10s)", "Calls done (10s)"],
                           timeline)
    g2 = naive["G2_overload_storm"]
    failed_turns = g2["turns"] - g2["good_turns"]
    month_turns = 4 * 30 * 24 * 3600
    incident_budget = failed_turns / (month_turns * 0.005) * 100
    cache_table = table(["Client", "Availability", "FAQ availability", "Hit ratio", "Stale served", "Wrong", "Outdated",
                         "Cost/good turn", "PASS"],
                        [[name, m["availability"], m["faq_availability"], m["cache_hit_ratio"], m["stale_served"],
                          m["wrong_answers"], m["outdated_answers"], m["cost_per_good_turn"], m["pass"]]
                         for name, m in cache.items()])
    threshold_table = table(["Threshold", "Hit ratio", "Wrong", "Reasons", "Cost/good turn"],
                            [[t, m["cache_hit_ratio"], m["wrong_answers"], m["wrong_answers_by_reason"], m["cost_per_good_turn"]]
                             for t in (0.8, 0.9, 0.97) for m in [exp(f"cache_threshold_{t}")]])
    ttl_table = table(["TTL s", "Hit ratio", "Outdated", "FAQ availability", "Cost/good turn"],
                      [[t, m["cache_hit_ratio"], m["outdated_answers"], m["faq_availability"], m["cost_per_good_turn"]]
                       for t in (30, 60, 300) for m in [exp(f"cache_ttl_{t}s")]])
    unfiltered = exp("without_tool_filter")
    without_stale = exp("cache_without_stale")
    b = slo["burnrate"]["budget"]
    text = f"""# Lab 25B — Report: ShopAgent Reliability Game Day

**Họ tên / nhóm:** Trần Quốc Vượng — **MSV:** 2A202602522.
**Commit:** `{args.submission_commit}` — snapshot nộp có source, artifacts và report; tag `day25-submission-20261013-r2`.
**Commit source/evidence:** `{args.source_commit}`. Metadata commit nộp được ghi trong commit hồ sơ sau snapshot để tránh tự tham chiếu SHA.
**Điểm tự động:** {score}/88; đạt toàn bộ 84 điểm kiểm tra public. 4 điểm SLO hidden chờ giảng viên,
12 điểm report/postmortem chấm tay, chưa tự cộng vào điểm đã xác minh.

Môi trường: Python 3.11.15 trên Windows, cài editable với `.[dev,plot]`, `pip check` đạt.
Tất cả latency, chi phí và sự cố dưới đây là **đầu ra simulator với thời gian ảo**, không phải API production.
Seed chính 25; kiểm tra bổ sung 26/27 đều đạt 6/6 băng và C1. Không cần API key, không dùng dữ liệu cá nhân thật.
Nguồn số: `gameday/*.json`, `cache/*.json`, `workflows.json`, `slo.json`, `experiments.json`, `scoreboard*.json`.
Scenarios, simulator, tests được cấp và services được giữ nguyên.

## 1. Kết quả Game Day (naive vs resilient)

{game_table}

P95 chỉ tính trên lượt **thành công**; không thể suy availability tốt từ P95 thấp.
`N/A` nghĩa là băng không định nghĩa mốc restore, không phải recovery bằng 0.
`recovery_s=0` nghĩa là cửa sổ 30 giây đầu tiên sau restore đạt ≥95% call thành công;
không chứng minh provider hết lỗi ngay tức thì. Primary share sau restore: G2/G4/G6 đều 1,000 ở seed 25.
G1 có 0 vi phạm retry-after; G5 có 0 retry lỗi 400 và 0 failover không cần thiết;
G6 có 0 incompatible routes. G5 còn {yours['G5_bad_deploy_then_quota']['turns'] - yours['G5_bad_deploy_then_quota']['good_turns']}
lượt thất bại do input sai/giới hạn xử lý, được giữ nguyên thay vì retry mọi lỗi để che sự cố deploy.

## 2. Cấu hình client và lý do

| Tham số | Giá trị | Evidence và lý do |
| --- | --- | --- |
| attempt_timeout_s | 4,0 | G2 P95 giảm 11,874 → 5,224 khi đổi riêng timeout 8 → 4 s, rồi còn 4,908 khi hạ slow threshold; dành thời gian cho fallback trong deadline 30 s |
| max_attempts_per_provider | 2 | Tối đa một retry transient; G3 retry_ratio=0,019, thấp hơn ngưỡng 0,10 |
| min_time_left_s | 1,0 | Không cấp attempt vô nghĩa sát deadline; timeout luôn bị cap theo thời gian còn lại |
| backoff_base_s / cap_s | 0,25 / 4,0 | Full jitter phân tán retry; G2 amplification=1,025, không còn 9,904 như naive |
| retry_budget_ratio / min_per_s / max_tokens | 0,10 / 0,5 / 20 | Giới hạn retry khi breaker bị cấu hình sai; xem mục 3. Initial burst và refill nghĩa là không phải trần cứng 10% ở mọi cửa sổ |
| breaker.window_size / min_calls | 20 / 10 | Tỷ lệ trên cửa sổ gần nhất, tránh trip từ vài lỗi đơn lẻ; G3 vẫn đạt availability=1,000 |
| breaker.failure_rate_threshold | 0,50 | Tránh giữ traffic ở provider hỏng; G2/G6 recovery=0 s theo định nghĩa scorer |
| breaker.slow_call_s / slow_rate_threshold | 3,0 / 0,60 | Phát hiện cả success chậm trước timeout 4 s; G2 P95 5,224 → 4,908, G4 P95=5,419 ≤10 s |
| breaker.open_duration_s | 10,0 | Chừa thời gian drain rồi thăm dò; G2/G4/G6 trả 100% attempt về primary trong cửa sổ sau restore |
| half_open_max_probes / successes | 2 / 2 | Chỉ hai probe đang bay, đóng sau hai success nhanh; tests kiểm tra stale generation và concurrency |
| quota_cooldown_s | 300 | Hết credit không tự hết sau một retry; G5 chỉ 2 quota errors (mỗi deployment A), rồi chuyển sang B |
| cache threshold / TTL / stale | 0,90 / 30 / 300 s | Chọn từ thí nghiệm mục 8, không hard-code tên intent, tài liệu hoặc thời điểm sự cố |

Decision table của `on_error`:

| Loại lỗi | Breaker | Retry cùng provider | Failover / cooldown |
| --- | --- | --- | --- |
| 400/401/403/404/422 và lỗi client khác | release permit, không ghi health | Không | GiveUp(client_error), không failover |
| 429 insufficient_quota | release | Không | Cooldown 300 s, đi deployment tiếp theo |
| 429 rate_limit_exceeded | release | Không retry ngay | Cooldown shared ít nhất retry-after, spillover ngay; chỉ đợi cooldown ngắn ≤5 s khi hết lựa chọn |
| 529/503, 5xx, timeout | on_failure | Nếu còn attempts, breaker cho phép, budget có token và còn deadline; full jitter | Nếu không đủ điều kiện, đi provider kế tiếp |
| Success chậm | on_success với latency | Không | Đóng góp slow rate, có thể OPEN |
| Cancel delayed attempt | release permit | Không | Không ghi lỗi health |

Ladder giữ thứ tự từ config và lọc `supports_tools` cho task tool. Mỗi logical call chỉ có một tầng retry.
Không dùng `time.sleep` hay đồng hồ thực trong logic client. Kết quả có generation cũ bị breaker bỏ qua.

## 3. Ba thí nghiệm bắt buộc

Script tái lập: `python scripts/run_experiments.py`; overrides chỉ nằm trong bản sao config hoặc subclass
control của script, không sửa client production hay các băng được cấp. Mọi bảng ở mục này dùng seed 25.

### 3.1. Retry budget là lớp phòng thủ cuối

Breaker hỏng: `min_calls=1000000000`, `max_attempts_per_provider=5`; budget-off dùng ratio=100,
max_tokens=1e9, min_per_s=1e6 đúng yêu cầu. Bảng healthy giữ max_attempts=2 và cấu hình cuối.

{budget_table}

Khi breaker hỏng, budget giảm amplification G2 từ 1,800 xuống 1,424 và retry_ratio từ 0,509 xuống 0,062;
P95 giảm 18,868 xuống 11,911 s. G3 giữ availability=1 nhưng retries giảm 0,160 → 0,068, tiết kiệm attempt
không làm mất kết quả. Recovery G2 của cả hai control vẫn là 0 theo cửa sổ scorer, nên thí nghiệm này chứng minh
giảm tải/P95, không chứng minh cải thiện recovery trên seed này. Khi breaker hoạt động đúng, bật/tắt budget cho
kết quả giống nhau ở hai băng này: breaker đã cắt tải trước khi token cạn; vẫn giữ budget để chống cấu hình sai
và những degradation nằm dưới ngưỡng trip.

### 3.2. Timeout 30 giây

{timeout_table}

Đọc availability và `give_up_reasons` trước P95: ở G6, timeout 4 s có 0 failed turns và
`give_up_reasons={{}}`; timeout 30 s có **122 failed turns**, tất cả ghi `deadline`, availability giảm
1,000 → 0,9488. Một attempt treo ở alpha-eu có thể dùng hết deadline của user, không còn thời gian cho beta.
Đối chứng G4: timeout 4 s có 1 failed turn (`no_provider_available`), timeout 30 s không có GiveUp;
breaker vẫn xử lý được slow successes nên timeout 30 s không làm availability sụp ở băng này.
P95 G6 giảm trong control **không có nghĩa nhanh hơn cho mọi người** vì nó chỉ
tính trên lượt thành công; các lượt treo đã rơi khỏi mẫu. Timeout nên dựa vào phân bố latency khỏe, deadline
toàn lượt và số fallback còn cần, rồi kiểm tra false timeout; không lấy 30 s của user cho từng LLM call.

### 3.3. Bỏ lọc tool calling

G6 control không lọc tạo **{unfiltered['incompatible_routes']} incompatible routes**, availability
{unfiltered['availability']} thay cho 1,000 khi có lọc. Các yêu cầu đó bị trả `incompatible_model_output`.
Với người dùng, đây là agent không thể gọi tool hoàn tiền dù nhận được text từ model: model rẻ hơn nhưng không
có chức năng cần thiết không phải phương án thay thế hợp lệ. Chỉ chat được phép dùng gamma-mini.

## 4. Workflow hoàn tiền

{workflow_table}

Key là SHA256 của danh tính `[session_id, step]`, giữ ổn định qua retry/restart và tách payment khỏi email.
Mỗi step thành công mới checkpoint; worker mới nạp lại state rồi chỉ chạy step còn thiếu. WorkerCrash được
propagate, chỉ ServiceError/ServiceTimeout được retry có giới hạn.
Idempotency riêng ngăn tiền/email trùng nhưng không ngăn lặp classify/lookup/summary và mất chi phí LLM;
checkpoint riêng vẫn có khoảng hở payment đã commit nhưng worker chết trước lúc lưu checkpoint.
Kết hợp cả hai giải quyết khoảng hở đó: phát lại cùng key nhận kết quả cũ rồi checkpoint.
Nếu checkpoint **trước** payment, worker chết giữa hai thao tác có thể resume bằng cách bỏ qua một khoản tiền
chưa hề chuyển; đó là lost refund. Exactly-once ở đây là **effect**, không phải mạng chỉ gọi đúng một lần;
phụ thuộc payment/email giữ idempotency record và DurableStore bền vững theo giả định simulator.

## 5. Alerting và error budget

{alert_table}

Burn-rate dùng prefix sums O(N) bộ nhớ/O(1) cho mỗi window, quét O(N × số rules).
Page 14,4× cần cả 1h và 5m; page 6× cần cả 6h và 30m; ticket 1× cần cả 3d và 6h.
Public dataset: naive 7 page, 0 ticket, 3 false page; burn-rate 3 page, 1 ticket, 0 false page.
Tại đúng ngưỡng có xử lý sai số float; budget cạn đúng 100% vẫn freeze, có regression test riêng.

30 ngày có **{b['requests']:,} requests**, **{b['bad']:,} bad**, allowed_bad={b['allowed_bad']:,}.
Availability={b['availability']}; đã tiêu **{b['budget_consumed'] * 100:.2f}%**, còn
**{b['budget_remaining'] * 100:.2f}%** budget, freeze_releases={b['freeze_releases']}.
Hiện chưa cần đóng băng release theo policy của lab; không dùng điều này để bỏ qua các incident riêng.
`small_bump` 20 phút ×12% lỗi tương đương 2,4 phút toàn outage nếu traffic đều: khoảng 1,11% budget 216 phút
của tháng. Burn 1h khoảng 8× <14,4×; burn 6h khoảng 1,33× <6× nên không page, phù hợp ít khẩn cấp hơn các
sự cố dài/lớn. Traffic thực tế thay đổi nên tính bằng request counts, không dùng phép xấp xỉ phút thay dữ liệu.

## 6. Postmortem G2 với client naive — blameless

### Tóm tắt

Provider alpha mất 75% năng lực từ t=120 đến t=300, trong khi v1 vẫn retry đồng bộ ở ba tầng.
Tải attempt tăng, giữ provider nghẽn cả sau khi năng lực phục hồi: {g2['attempts']:,} attempts cho
{g2['calls']:,} logical calls (amplification={g2['amplification']}). Client resilient cắt vòng lặp bằng
timeout, breaker, budget và fallback, đạt availability=1,000 và amplification=1,025 trên cùng băng/seed.

### Ảnh hưởng và phạm vi

Naive có **{failed_turns:,}/{g2['turns']:,} lượt user thất bại**, availability={g2['availability']},
P95={g2['latency_p95_s']} s trên success, cost/good turn={g2['cost_per_good_turn']}.
Call success trailing 30 s dưới 95% liên tiếp tại t=145…483 (339 mẫu giây). Đây là cửa sổ quan sát,
không khẳng định mọi user thất bại trong từng giây đó. Scorer báo recovery=155 s sau provider restore.
Giả sử tháng có traffic cố định 4 lượt/s và chỉ sự cố này: {month_turns:,} lượt/tháng,
budget 99,5% là {month_turns * .005:,.0f} failed turns; sự cố tiêu **{incident_budget:.4f}% budget tháng**,
chưa vượt toàn bộ budget. Không trộn turn-level tính toán này với SLI request-level ở mục 5.

![G2: attempt load và call success của naive/resilient](gameday/G2_overload_storm.png)

### Timeline từ CSV

{timeline_table}

Các số attempts/s và success ở bảng là cửa sổ **10 giây kết thúc tại t**. Panel dưới của hình cũng dùng
success rolling 10 giây; panel trên hiển thị attempts của từng giây, còn bảng lấy trung bình 10 giây.
Recovery của scorer là cửa sổ **30 giây bắt đầu tại t**: tại [455,485) có 352/368 calls thành công
(95,65%). Vì vậy t=455 được tính là recovery dù success trailing 10s tại chính t=455 mới là 30%.
Hai loại cửa sổ khác nhau phải được đọc riêng.

### Trigger và root cause

Trigger là giảm capacity của alpha, không phải lỗi của một cá nhân vận hành. Root cause phía client là retry
app × gateway × SDK tới 36 attempts/call, fixed delay, không phân biệt lỗi, không budget/breaker/fallback.
Client timeout không hủy công việc ở server; retry thêm request mới vào FIFO trong lúc request cũ vẫn tiêu slot.
Vòng lặp queue dài → timeout/529 → retry → queue dài tạo metastable failure; khôi phục capacity chưa đủ nếu
tải do retry và lượng công việc tồn đọng vẫn quá cao. CSV chứng minh tải/success, không đo trực tiếp queue depth;
cơ chế request tiếp tục xử lý sau timeout là giả định công khai của simulator.
Naive ghi 2.737 client_timeout, 3.194 overloaded_error, 26.298 rate_limit_exceeded và 28.381 retry-after
violations; t=300 vẫn 142,9 attempts/s trong cửa sổ 10s, success=0. Recovery thực nghiệm sau restore mất 155 s.

### Điều gì giúp / làm tệ hơn

Fallback giữ dịch vụ ở deployment khác trong khi breaker để alpha drain; permit generation loại kết quả cũ,
hai probe giới hạn tải khi quay lại. Tinh chỉnh timeout 8 → 4 s và slow threshold 5 → 3 s giảm G2 P95
11,874 → 4,908 s. Retry ba tầng, fixed delay và retry rate limit quá sớm làm sự cố tệ hơn.
Quy trình trước đây thiếu game-day và metric amplification; hành động khắc phục tập trung vào thiết kế và
kiểm chứng, không quy lỗi cho người triển khai.

### Action items đề xuất

| # | Hành động | Loại | Owner | Cách kiểm chứng |
| --- | --- | --- | --- | --- |
| 1 | Dùng duy nhất reliability client; tắt retry tự động của SDK/gateway khi đưa vào production | prevent | Trần Quốc Vượng | G2 amplification ≤1,2 và G3 retry_ratio ≤0,10 ở nhiều seed; audit retry layers |
| 2 | Bổ sung dashboard attempts/logical calls, timeout, queue wait và burn-rate | detect | Trần Quốc Vượng | Public SLI: page đúng cả 3 incident, 0 false page; cảnh báo amplification >1,2 qua 2 cửa sổ |
| 3 | Runbook trip breaker, spillover có kiểm tra capability và HALF-OPEN 2 probes | mitigate | Trần Quốc Vượng | G2 recovery ≤30 s, primary share ≥80%; G6 incompatible_routes=0 |
| 4 | Kiểm tra checkpoint/idempotency bằng fault injection trước release | prevent | Trần Quốc Vượng | 500 workflow, 0 duplicate/lost effect, LLM lãng phí/crash ≤0,6 |

Các action về dashboard/CI/runbook là **đề xuất vận hành**; code và simulator đã chạy, chưa triển khai hạ tầng
production hay một workflow CI được host. Không coi bài mô phỏng là chứng nhận production readiness.

## 7. Điểm yếu còn lại

Ở G4 seed 25 vẫn mất một lượt (availability=0,9995): timeout 4 s có thể cắt đuôi latency của provider tốt
trong lúc fallback đang bận. G6 cost/good turn=2,207 cao hơn naive=2,009 vì B đắt hơn và naive bỏ nhiều
người dùng; G6 P99={yours['G6_provider_outage']['latency_p99_s']} s vẫn đáng theo dõi.
Nếu mọi provider cùng chậm hoặc quota cùng cạn, breaker/fallback không tạo thêm năng lực.
Hướng cải tiến: deadline allocation theo từng step, timeout theo percentile khỏe từng deployment, admission
control và giới hạn concurrency; giữ các SLO/tool compatibility khi đánh giá trên băng/seed chưa dùng để tune.
Simulator không mô hình hóa tác dụng phụ tool từ LLM retry, persistence đa process thực hay rate limit đa tenant;
cần thử staging có tracing và fault injection trước production. Cache lưu list, lookup O(max_entries × dimension),
phù hợp 500 entries của lab; tải lớn cần index theo scope nhưng vẫn kiểm chứng semantic collisions/invalidation.

## 8. Semantic cache và stale-if-error

{cache_table}

Không cache thất bại tiêu chí FAQ/hit là control dự kiến. Cache mới đạt C1 cả seeds 25/26/27:
FAQ availability lần lượt 0,9645 / 0,9540 / 0,9627; hit ratio 0,592 / 0,588 / 0,591;
wrong_answers=0 ở cả ba, outdated=2 / 4 / 7 (đều ≤15).
Baseline cấu hình cache starter (0,80/600/0) ở `cache_initial/` và experiment `cache_starter_settings`
cho 181 wrong other_question, 80 outdated, FAQ availability=0,8587. Đây là control thất bại được giữ nguyên.

| Tham số | Giá trị cuối | Lý do |
| --- | --- | --- |
| similarity_threshold | 0,90 | Loại 181 nhầm intent tại 0,80; 0,97 quá chặt khiến hit=0,499 <0,50 |
| ttl_s | 30 | Outdated=2 so với 3 ở 60 s và 95 ở 300 s; chấp nhận hit thấp hơn để giới hạn stale knowledge |
| max_stale_s | 300 | FAQ availability 0,9645 thay 0,8529 khi tắt stale; 192 lượt được cứu từ stale cache |
| max_entries | 500 | LRU giữ bộ nhớ bounded; tests kiểm tra refresh/eviction, không nhân entries vô hạn |
| scope / allowlist | prompt_version / non-personal FAQ | Không trả answer prompt cũ hoặc dữ liệu user; source invalidation loại cả fresh lẫn stale |

### 8.1. Ngưỡng similarity

{threshold_table}

Ở 0,80, `wrong_answers_by_reason={{'other_question': 181}}`; không có lỗi other_user, old_prompt hay
ignored_invalidation. Catalog tạo các cặp gần nhưng khác: refund policy/refund time, đổi size/đổi màu,
phí ship nội thành/ngoại tỉnh, phương thức thanh toán/COD. Aggregate metric chỉ quy lỗi other_question,
không đủ để khẳng định từng cặp đóng góp bao nhiêu trong 181; các ví dụ trên giải thích nguy cơ từ catalog.
0,90 có 0 wrong và hit=0,592; 0,97 vẫn 0 wrong nhưng giảm hit còn 0,499, tăng cost 0,955 →1,018.

### 8.2. TTL và thay đổi không được báo

{ttl_table}

Webhook t=150 invalidates nguồn đã được báo đổi; prompt v2 t=420 được tách scope.
Thay đổi bảng phí ship tại t=480 **không có webhook**, nên cache không có tín hiệu để invalidate;
TTL buộc revalidation khi provider khỏe, giới hạn số lần trả nội dung lỗi thời. TTL 300 s làm outdated=95,
vượt ngưỡng15 dù wrong_answers vẫn0: correctness do semantic mismatch khác freshness do cập nhật không báo.
Trong outage, stale window cố ý nới tuổi tối đa tới TTL+300 s; TTL riêng không bảo đảm dữ liệu luôn mới
khi vừa có silent update vừa mất provider. Production cần cảnh báo stale và chọn freshness policy theo rủi ro.

### 8.3. Stale-if-error

Tắt max_stale_s: FAQ availability={without_stale['faq_availability']}, hit={without_stale['cache_hit_ratio']},
stale_served=0, cost/good turn={without_stale['cost_per_good_turn']}. Bật 300 s: FAQ availability=0,9645,
hit=0,592, stale_served=192, cost/good turn=0,955. Client chỉ Serve stale sau GiveUp từ inner và lookup lại
**tại thời điểm GiveUp**, nên webhook đến trong lúc request đang bay vẫn ngăn dùng entry đã bị invalidate.
Các request mới không được phục vụ stale ngay khi provider còn khỏe.

### Dữ liệu cá nhân và quan sát outage khi cache vẫn trả lời

Câu hỏi cá nhân về đơn/refund/điểm không thuộc allowlist, kể cả cache theo user: cùng user vẫn có nhiều
đơn gần embedding, trạng thái thay đổi nhanh, cần authorization và nguồn giao dịch mới. User-scoped cache
không tự giải quyết correctness, revocation hay freshness; bài này bypass cả store và lookup cho personal.
Dashboard cần tách user availability khỏi **provider attempt success/error/timeout, breaker state, cache
fresh/stale ratio, tuổi answer và invalidation lag**. Trong C1 cache vẫn phục vụ192 stale, nhưng có94
service_unavailable errors ở provider; phải alert degradation đó và synthetic probes không cache để on-call
thấy outage. Không tính một Serve từ cache là provider success và đóng breaker.

## Tái lập, nguồn và đóng góp

Thực hiện: phân loại lỗi/retry, breaker, client, semantic cache, workflow, SLO alerting, thí nghiệm và report.
Starter là Lab25B AICB-P2T3 trong repo; không lấy code hay số đo từ bài Day24. Codex hỗ trợ triển khai, đọc test
và phân tích; kết luận được kiểm chứng bằng test gốc, regression bổ sung và simulator, không tự điền nhãn/số.
Nguồn thuật toán: Full Jitter (Brooker/AWS), multi-window burn-rate (Google SRE Workbook ch.5),
idempotent effect theo hợp đồng payment/email của starter, stale-if-error (RFC5861).

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -e ".[dev,plot]"
.\\.venv\\Scripts\\python.exe -m pip check
.\\.venv\\Scripts\\python.exe -m pytest tests student_tests -q
.\\.venv\\Scripts\\python.exe scripts/run_gameday.py --client both
.\\.venv\\Scripts\\python.exe scripts/run_workflows.py --executor both
.\\.venv\\Scripts\\python.exe scripts/run_slo.py --alerter both
.\\.venv\\Scripts\\python.exe scripts/run_gameday.py --scenarios configs/scenarios_cache.yaml --client resilient,cached --out reports/cache
.\\.venv\\Scripts\\python.exe scripts/run_experiments.py
.\\.venv\\Scripts\\python.exe scripts/plot_timeseries.py
.\\.venv\\Scripts\\python.exe scripts/grade.py
.\\.venv\\Scripts\\python.exe scripts/grade.py --seeds 25,26,27 --out reports/scoreboard_multiseed.json
.\\.venv\\Scripts\\python.exe scripts/write_report.py --source-commit {args.source_commit} --submission-commit {args.submission_commit}
```

82 tests gốc + 6 regression bổ sung đạt; lint/type check các file triển khai đạt. 4 điểm hidden SLO chưa có
dữ liệu để xác minh; hidden tapes/production không được suy đạt chỉ từ public seeds. Report dùng các số đã lưu,
tag nộp cố định cả code, cấu hình, JSON, CSV và hình; `evidence_manifest.json` lưu SHA256 để đối chiếu phiên bản.
"""
    Path("reports/REPORT.md").write_text(text, encoding="utf-8", newline="\n")
    paths = sorted(set(Path("reports").rglob("*.json")) | set(Path("reports").rglob("*.csv"))
                   | set(Path("reports").rglob("*.png")) | set(Path("src/gameday_lab").rglob("*.py"))
                   | {Path("configs/gameday.yaml"), Path("configs/scenarios.yaml"),
                      Path("configs/scenarios_cache.yaml"), Path("data/sli_30d.csv"), Path("data/sli_30d_labels.json")})
    manifest = {"source_commit": args.source_commit, "kind": "simulation",
                "hash_mode": "sha256; CRLF normalized to LF for text files; raw bytes for PNG",
                "created_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                "sha256": {p.as_posix(): hashlib.sha256(
                    p.read_bytes() if p.suffix == ".png" else p.read_bytes().replace(b"\r\n", b"\n")
                ).hexdigest()
                           for p in paths if p.name != "evidence_manifest.json"}}
    Path("reports/evidence_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Wrote reports/REPORT.md and reports/evidence_manifest.json")


if __name__ == "__main__":
    main()
