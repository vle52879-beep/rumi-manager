# Sửa lỗi Vercel: functions không khớp thư mục api

Bản v4.4 khai báo `functions.app.py` trong `vercel.json`. Cấu hình này khiến Vercel yêu cầu hàm nằm trong thư mục `api/` và dừng build.

Bản v4.5 bỏ khai báo `functions`. Vercel tự nhận `app.py` và biến Flask `app` thông qua Python runtime.

## Cập nhật repository hiện tại

Thay file `vercel.json` bằng file trong bản này, rồi chạy:

```bash
git add vercel.json VERSION.txt
git commit -m "Fix Vercel Flask entrypoint"
git push
```

Vercel sẽ tự redeploy.
