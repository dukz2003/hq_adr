# Triển khai thử Railway — 04/10/2026

## Cấu hình hiện tại

- Repo host: https://github.com/dukz2003/hq_adr (public do chủ repo chuyển).
- Thư mục mã nguồn: `D:\phuduc\hq_java`.
- Project: https://railway.com/project/6283028e-ed47-43be-90ad-f871916aa03a
- Service: `hq_adr`, một replica, US West, gói Trial (chưa nâng cấp trả phí).
- API: https://hqadr-production.up.railway.app
- Java 21 + Python 3.11 trong Docker; Java signer chỉ nghe loopback.
- Variables: HQ_API_TOKEN, HQ_DEVICE_ID, HQ_IID, HQ_CDID,
  HQ_RATE_LIMIT_PER_MINUTE=60, HQ_MAX_PENDING=4, PORT=8080.
- Healthcheck `/healthz`, timeout 120s; restart On Failure, tối đa 3 lần.

Token và guest profile không được ghi trong tài liệu/Git. Chủ dự án đã xác nhận
lưu chúng trong Railway Variables. Token local nằm trong `.env` bị Git bỏ qua.
Giữ ba giá trị guest ổn định khi redeploy; không đổi ID khi bị rate limit.

Railway báo Deployment successful. Kiểm tra từ máy khách:

- `/healthz`: HTTP 200, status=ok.
- Gọi API danh sách tập không kèm token: HTTP 401.
- Probe với token hợp lệ: 99/99 tập và stream model, không thiếu tập.

## Ứng dụng desktop

Đã cấu hình `.env` riêng của `tool_video_tts_stt`:

```dotenv
HONGGUO_SERVICE_URL=https://hqadr-production.up.railway.app
HONGGUO_SERVICE_TOKEN=<giá trị riêng tư, không ghi tại đây>
```

Khởi động lại backend/app để đọc cấu hình. Không cần Java trên máy khách ở chế
độ remote. Python/FFmpeg vẫn cần vì video tải trực tiếp CDN về máy, giải mã,
remux và kiểm tra đầy đủ trên máy khách. Backend không fallback sang local nếu
server lỗi. Link có series_id hoặc ID số được hỗ trợ; share link rút gọn chưa có.

Thư mục test cloud: `D:\phuduc\test_hq_dl\test-output\railway-hongguo`.
Báo cáo CLI: `D:\phuduc\test_hq_dl\test-output\railway-download-report.json`.
Kết quả tải thực tế được ghi ở `docs/verification.md` khi chạy xong; không suy
ra tải thành công chỉ từ healthcheck/model availability.

## Những giới hạn trước khi phát hành EXE

- Token dùng chung chỉ cho thử nghiệm riêng. Không nhúng token vào EXE phát hành
  công khai; cần cấp quyền/token theo user để tránh bị trích xuất và lạm dụng.
- `.env` của máy dev không tự đi theo bộ cài: máy khác phải có cấu hình dịch vụ
  và credential được cấp hợp lệ. Chưa build/test installer trên máy sạch.
- Railway Trial/Free giới hạn credit/tài nguyên. Không cam kết miễn phí hoặc chạy
  ổn định dài hạn; không thay đổi gói trả phí trong lần thử này.
- Guest signature/API/IP/CDN có thể bị phía Hongguo thay đổi. Không cam kết tiếp
  tục tải đủ; xem lỗi 401/403/429/502/503 trong README và dùng quyền hợp lệ.
- [Railway Config-as-Code đã deprecated](https://docs.railway.com/config-as-code/reference).
  Cấu hình healthcheck/restart/port của service này đặt trực tiếp trong dashboard;
  không dựa vào `railway.toml` cho service mới.
- Dashboard hiện báo Auto deploy unavailable đối với repo thuộc GitHub khác tài
  khoản kết nối. Khi thay code: kiểm tra cập nhật upstream/manual deploy và xác
  nhận deployment mới; không coi push Git là bằng chứng code đã chạy trên cloud.
- Khi chuyển VPS: giữ nguyên Docker/service, đặt HTTPS reverse proxy và đổi
  HONGGUO_SERVICE_URL ở client; giữ credential/guest profile trong nơi riêng tư.
