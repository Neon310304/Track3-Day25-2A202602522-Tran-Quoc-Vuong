# Phiên bản nộp Lab 25B

- Họ tên: Trần Quốc Vượng — MSSV: 2A202602522.
- Repo: https://github.com/Neon310304/Track3-Day25-2A202602522-Tran-Quoc-Vuong
- Phiên bản nộp đầy đủ: tag `day25-submission-20261013-r2`.
- Commit nộp đầy đủ: `277ac146590e5aca38d1412bbf83a421251ac1bd`.
- Mở đúng phiên bản: https://github.com/Neon310304/Track3-Day25-2A202602522-Tran-Quoc-Vuong/tree/277ac146590e5aca38d1412bbf83a421251ac1bd
- Report: `reports/REPORT.md`; kết quả tự chấm: `reports/scoreboard.json`.

Phiên bản này có toàn bộ source, cấu hình, JSON, CSV, hình postmortem, report và manifest.
Source/evidence được tạo ở commit `2f8dd8c600b80e3875f409f29c2547abc8a5991c`.
Tag nộp cố định source, cấu hình, artifacts và report đã đối chiếu rubric.
Report ghi rõ `give_up_reasons` trong thí nghiệm timeout và phạm vi thời gian của hình/timeline G2.
Commit hồ sơ sau snapshot chỉ chuẩn hóa dòng `Họ tên / nhóm` và ghi `Commit` nộp trong report trên `main`;
không thay source, artifacts, số đo hoặc nội dung phân tích trong snapshot/tag nộp.

Đã xác minh: 82 tests gốc + 6 regression bổ sung đạt; G1–G6 và C1 đạt cả seed
25/26/27; workflow/SLO public đạt; verifier offline 0 lỗi. Git archive của commit nộp
có đủ artifacts và 57 source/evidence hashes khớp (text chuẩn hóa CRLF → LF).
Không sửa simulator/tests/scenarios/services/data được cấp. Không chứa `.env` hoặc virtualenv.
Kiểm tra tái lập từ Git archive của commit nộp: tạo virtualenv mới, cài `pip install -e ".[dev]"`,
`pip check` đạt và chạy grader gốc đạt 84/88; toàn bộ `scoreboard.json` khớp evidence đã commit.
Repo public đúng tên, nhánh mặc định `main`, kiểm tra HTTP 200 khi không đăng nhập.

Điểm tự chấm **84/88**: đủ 84 điểm public; 4 điểm hidden SLO và 12 điểm report
do giảng viên chấm. Không tự khai đã đạt dữ liệu ẩn hoặc đã nộp qua kênh lớp.
Lab mô phỏng, không cần API key hay Docker.
