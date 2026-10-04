# Báo cáo test Hongguo qua Railway — 04/10/2026

## Kết luận

Đã triển khai thành công API Hongguo trên Railway và tải thật đủ **99/99 tập**
phim `亿万斯年`, series `7686533063710346265`, về máy Windows.
Kết quả không phải chỉ kiểm tra có link: mỗi tập đã được tải, giải mã, remux,
probe và decode toàn bộ hình/tiếng trước khi ghi nhận thành công.

| Hạng mục | Kết quả |
| --- | --- |
| API | https://hqadr-production.up.railway.app |
| Healthcheck | HTTP 200, status=ok trước và sau test |
| Danh sách/model | 99/99 tập, không thiếu stream |
| Tải mới | 99 file trong 590.38 giây (~9 phút 50 giây) |
| Chất lượng | Tất cả 1080x1920, HEVC + AAC |
| Dung lượng | 720930792 bytes (~687.5 MiB) |
| Toàn vẹn | 99 SHA-256 khác nhau, khớp manifest, không lỗi |
| Decode độc lập thêm | Tập 1 và 99 đều exit=0 |
| Chạy lại | 99 file được dùng lại, tải mới 0, mất 3.94 giây |
| Kiểm thử tự động | 164 test desktop + 11 test service đều qua |

## File tải và báo cáo

- Video: `D:\phuduc\test_hq_dl\test-output\railway-hongguo\亿万斯年\Tập 001.mp4`
  đến `Tập 099.mp4`.
- CLI download: `D:\phuduc\test_hq_dl\test-output\railway-download-report.json`.
- Audit: `D:\phuduc\test_hq_dl\test-output\railway-manifest-audit.json`.
- Resume: `D:\phuduc\test_hq_dl\test-output\railway-resume-report.json`.
- Ảnh deployment: `D:\phuduc\test_hq_dl\test-output\railway-active.jpg`.

## Đã cấu hình gì?

Server nằm tại `D:\phuduc\hq_java`, đã đẩy lên repo `dukz2003/hq_adr`.
Railway Variables lưu token riêng và guest profile ổn định (không nằm trong Git).
Java 21 và Python nằm trong Docker; signer chỉ nghe nội bộ.
API private có giới hạn 60 request/phút, hàng đợi tối đa 4; một replica.
HTTP 401 khi thiếu token, 422 khi ID sai, /sign không được expose (404).

`.env` riêng của `C:\Users\IT\Documents\GitHub\tool_video_tts_stt` đã lưu
HONGGUO_SERVICE_URL, HONGGUO_SERVICE_TOKEN và HONGGUO_DOWNLOAD_WORKERS=2.
Không có Java signer chạy trên máy khách trong test cloud. Video đi trực tiếp
từ CDN về máy; Railway chỉ xử lý ký và dữ liệu/link, không lưu/chuyển video.

Khởi động lại backend/ứng dụng để đọc cấu hình mới. Khi chọn tải full trong GUI,
đặt giới hạn số tập ít nhất 99 (mặc định GUI vẫn là 50).

## Giới hạn

- Đây là một lần test đầy đủ thành công, không chứng minh uptime/tải nhiều user
  lâu dài hoặc tất cả phim đều được phép tải.
- Chưa nâng cấp trả phí; dịch vụ đang dùng credit Trial hữu hạn của Railway.
  Hết credit/bị hạn chế mạng/tài nguyên thì cần xử lý hoặc chuyển VPS.
- Hongguo có thể đổi API/chữ ký/quyền/CDN. Không xoay ID để né giới hạn, không
  cam kết vượt xác minh hoặc truy cập nội dung bị khóa.
- `.env` máy dev không tự đi theo EXE. Máy khác cần cấu hình API/credential hợp
  lệ; Java không cần trên client ở remote mode, nhưng Python/FFmpeg vẫn cần.
- Token dùng chung chỉ cho thử nghiệm riêng, không nhúng vào EXE phát hành công
  khai. Cần xác thực/cấp quyền theo user trước khi phân phối rộng.
- Trước phát hành, kiểm tra quyền phân phối bộ ký upstream theo assets/NOTICE.md.
- Dashboard báo Auto deploy unavailable: push Git chưa đảm bảo tự cập nhật cloud.
  Kiểm tra/manual cập nhật upstream và deployment khi đổi logic.

Hướng chuyển VPS và xử lý lỗi: README.md, docs/railway-deployment.md và tài liệu
Hongguo trong dự án desktop. Token, guest IDs, chữ ký, khóa và CDN URL không được
ghi vào báo cáo công khai.
