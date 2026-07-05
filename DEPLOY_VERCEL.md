# Deploy RUMI 6.0 lên Vercel

Bản 6.0 giữ nguyên cấu hình Vercel và Supabase của bản đang chạy.

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v6.0-PREMIUM-UI.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.0-PREMIUM-UI/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 6.0 premium motion UI"
git push
```

Không chạy SQL mới. Chờ Vercel `Ready`, sau đó tải lại bằng `Command + Shift + R`.
