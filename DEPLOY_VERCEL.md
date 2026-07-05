# Deploy RUMI 6.4.1 lên Vercel

Sau khi đã chạy SQL `SUPABASE_RUMI_V6_4_1_DOUBLE_SHIFT.sql`, ghi đè dự án đang kết nối Vercel rồi push:

```bash
cd ~/Downloads

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.4.1-DOUBLE-SHIFT/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel

git add -A
git commit -m "Upgrade RUMI 6.4.1 double shift and next week registration"
git push
```

Chờ Vercel báo **Ready**, sau đó tải lại cứng bằng `Command + Shift + R`.
