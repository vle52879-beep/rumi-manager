# Nâng cấp RUMI đang chạy lên 5.0

Không cần chạy SQL mới và không thay Environment Variables.

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v5.0-Vercel.zip
rsync -av --delete --exclude='.git' --exclude='.env' RUMI-Manager-Supabase-v5.0-Vercel/ RUMI-Manager-Supabase-v4.4-Vercel/
cd RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 5.0"
git push
```

Sau khi Vercel báo `Ready`, mở trang bằng cửa sổ ẩn danh hoặc nhấn `Command + Shift + R` để tránh cache cũ.
