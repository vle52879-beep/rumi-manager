# Deploy RUMI 5.3 lên Vercel

Project đã có sẵn:

- `api/index.py`: Python Function.
- `requirements.txt`: Flask.
- `.python-version`: Python 3.12.
- `vercel.json`: rewrite `/api/*`, `/login`, `/app`.
- `public/`: giao diện và tài nguyên tĩnh.

## Environment Variables

Giữ nguyên các biến đã cấu hình ở project Vercel hiện tại:

```env
RUMI_SUPABASE_URL=https://PROJECT.supabase.co
RUMI_SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
RUMI_ADMIN_USERNAME=admin
RUMI_ADMIN_PASSWORD=MAT_KHAU_RIENG
RUMI_ADMIN_NAME=Chủ cửa hàng RUMI
RUMI_ADMIN_RESET_ON_START=0
```

Không đưa secret key vào GitHub.

## Deploy

Chỉ cần `git push`; Vercel tự build và deploy nhánh `main`.
