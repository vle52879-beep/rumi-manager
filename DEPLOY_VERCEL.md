# Deploy RUMI 5.5 lên Vercel

Sau khi chạy SQL v5.5 trên Supabase, chép mã vào repository đang kết nối Vercel:

```bash
rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v5.5-SECURITY-ATTENDANCE/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 5.5 security and smart attendance"
git push
```

Chờ Vercel báo `Ready`, sau đó tải cứng bằng `Command + Shift + R`.
