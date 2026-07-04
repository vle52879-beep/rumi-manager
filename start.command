#!/bin/zsh
cd "$(dirname "$0")"
clear
if [ ! -f .env ]; then
  echo "Chưa có file .env."
  echo "Chạy: cp .env.example .env"
  echo "Sau đó điền URL và SECRET KEY MỚI của Supabase."
  echo
  read "?Nhấn Enter để đóng..."
  exit 1
fi
python3 server.py
status=$?
echo
if [ $status -ne 0 ]; then
  echo "RUMI dừng với mã lỗi $status."
  read "?Nhấn Enter để đóng..."
fi
