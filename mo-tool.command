#!/bin/bash
# Mở Creative Tracker: nhấp đúp file này trong Finder (hoặc gõ ./mo-tool.command trong Terminal).
#
# macOS chặn không cho mở ("không thể mở vì nhà phát triển không xác định")?
#   Cách 1: chuột phải vào file → Open (Mở) → Open. Chỉ cần làm 1 lần.
#   Cách 2: trong Terminal: xattr -dr com.apple.quarantine <kéo thả thư mục tool vào đây>
#
# Để cửa sổ Terminal này mở suốt lúc dùng tool. Tắt tool: bấm Ctrl+C (hoặc đóng cửa sổ).
# Cổng khác: CONG=8771 ./mo-tool.command     Không tự mở trình duyệt: KHONG_MO_TRINH_DUYET=1 ./mo-tool.command

cd "$(dirname "$0")" || exit 1
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done

CONG="${CONG:-8770}"
URL="http://127.0.0.1:$CONG"
echo "=== Creative Tracker ==="

if [ ! -x .venv/bin/ctal ]; then
  echo "✗ Chưa cài. Mở Terminal trong thư mục này và chạy:  bash cai-dat.sh"
  read -r -p "Bấm Enter để đóng…" _; exit 1
fi

# Tool đã mở sẵn ở cổng này? Chỉ mở trình duyệt, không bật thêm một bản thứ hai.
if curl -s --max-time 2 "$URL/api/scan" | grep -q '"running"'; then
  echo "✓ Tool đang chạy sẵn ở $URL — mở trình duyệt."
  [ "${KHONG_MO_TRINH_DUYET:-0}" = "1" ] || open "$URL"
  exit 0
fi
if lsof -nP -iTCP:"$CONG" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "✗ Cổng $CONG đang bị một chương trình khác dùng."
  echo "  Mở Terminal trong thư mục này và chạy với cổng khác:  CONG=8771 ./mo-tool.command"
  read -r -p "Bấm Enter để đóng…" _; exit 1
fi

echo "Đang mở $URL … (để cửa sổ này mở; tắt tool bằng Ctrl+C)"
ARGS=(web --port "$CONG")
[ "${KHONG_MO_TRINH_DUYET:-0}" = "1" ] && ARGS+=(--no-open)
exec .venv/bin/ctal "${ARGS[@]}"
