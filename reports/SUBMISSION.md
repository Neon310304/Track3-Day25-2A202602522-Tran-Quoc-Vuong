# Phiên bản nộp Lab 25B

- Họ tên: Trần Quốc Vượng — MSSV: 2A202602522.
- Repo: https://github.com/Neon310304/Track3-Day25-2A202602522-Tran-Quoc-Vuong
- Commit nộp đầy đủ: `59f74bc21d56b1f3c42f70752445e9de5a8fc883`.
- Tag: `day25-submission-20261013`.
- Mở đúng phiên bản: https://github.com/Neon310304/Track3-Day25-2A202602522-Tran-Quoc-Vuong/tree/59f74bc21d56b1f3c42f70752445e9de5a8fc883
- Report: `reports/REPORT.md`; kết quả tự chấm: `reports/scoreboard.json`.

Phiên bản này có toàn bộ source, cấu hình, JSON, CSV, hình postmortem, report và manifest.
Source/evidence được tạo ở commit `2f8dd8c600b80e3875f409f29c2547abc8a5991c`, sau đó
commit nộp bổ sung report có tham chiếu SHA nguồn. Commit hồ sơ chứa file này chỉ ghi
lại revision nộp, không thay source, số đo hoặc report trong tag.

Đã xác minh: 82 tests gốc + 6 regression bổ sung đạt; G1–G6 và C1 đạt cả seed
25/26/27; workflow/SLO public đạt; verifier offline 0 lỗi. Git archive của commit nộp
có đủ artifacts và 57 source/evidence hashes khớp (text chuẩn hóa CRLF → LF).
Không sửa simulator/tests/scenarios/services/data được cấp. Không chứa `.env` hoặc virtualenv.

Điểm tự chấm **84/88**: đủ 84 điểm public; 4 điểm hidden SLO và 12 điểm report
do giảng viên chấm. Không tự khai đã đạt dữ liệu ẩn hoặc đã nộp qua kênh lớp.
Lab mô phỏng, không cần API key hay Docker.
