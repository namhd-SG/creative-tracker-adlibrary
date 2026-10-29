#!/bin/bash
# Cài Creative Tracker trên máy Mac — chạy một lần, chạy lại bao nhiêu lần cũng được.
#   bash cai-dat.sh
# Không dùng sudo. Thiếu Homebrew thì script dừng và in đúng lệnh cần chạy.

set -u
cd "$(dirname "$0")" || exit 1

XANH=$'\033[32m'; DO=$'\033[31m'; VANG=$'\033[33m'; DAM=$'\033[1m'; HET=$'\033[0m'
ok()   { echo "  ${XANH}✓${HET} $*"; }
loi()  { echo "  ${DO}✗${HET} $*"; }
chu_y(){ echo "  ${VANG}!${HET} $*"; }
buoc() { echo; echo "${DAM}$*${HET}"; }
dung() { echo; echo "${DO}${DAM}Chưa cài xong.${HET} Làm theo dòng ✗ ở trên rồi chạy lại: ${DAM}bash cai-dat.sh${HET}"; exit 1; }

# Homebrew nằm ở 2 chỗ tuỳ loại chip; Terminal mới mở có thể chưa biết đường dẫn.
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  [ -x "$b" ] && eval "$("$b" shellenv)" && break
done

buoc "1/5  Máy Mac"
if [ "$(uname)" = "Darwin" ]; then ok "macOS $(sw_vers -productVersion 2>/dev/null)"; else loi "Script này chỉ dành cho macOS."; dung; fi

buoc "2/5  Homebrew (trình cài phần mềm)"
if command -v brew >/dev/null 2>&1; then
  ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"
else
  loi "Chưa có Homebrew. Dán lệnh sau vào Terminal, Enter, nhập mật khẩu máy khi được hỏi:"
  echo '      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  echo "    Cài xong, ĐÓNG Terminal, mở lại rồi chạy lại: bash cai-dat.sh"
  dung
fi

buoc "3/5  Python 3.11 trở lên"
tim_python() {
  for c in python3.13 python3.12 python3.11 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    p=$(command -v "$c" 2>/dev/null) || continue
    "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null && { echo "$p"; return 0; }
  done
  return 1
}
PY=$(tim_python)
if [ -z "$PY" ]; then
  chu_y "Chưa có Python 3.11+ (Python sẵn của macOS là bản cũ). Đang cài python@3.12 bằng Homebrew…"
  brew install python@3.12 || { loi "Cài Python không được (xem dòng lỗi ở trên)."; dung; }
  PY=$(tim_python) || { loi "Đã cài nhưng chưa tìm thấy Python 3.11+. Đóng Terminal, mở lại rồi chạy lại."; dung; }
fi
ok "$("$PY" --version) ($PY)"

buoc "4/5  Cài tool vào thư mục .venv (chỉ trong thư mục này, không đụng phần còn lại của máy)"
if [ -x .venv/bin/python ] && ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  chu_y ".venv cũ dùng Python quá cũ — tạo lại"; rm -rf .venv
fi
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || { loi "Không tạo được .venv"; dung; }
fi
ok ".venv sẵn sàng"
.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1
if .venv/bin/python -m pip install --quiet -e . ; then
  ok "Đã cài Creative Tracker ($(.venv/bin/ctal --help >/dev/null 2>&1 && echo 'lệnh ctal chạy được'))"
else
  loi "Cài gói không được — thường do mất mạng giữa chừng. Kiểm mạng rồi chạy lại."; dung
fi

buoc "5/5  Trình duyệt ẩn để đọc Ad Library (~150 MB, chỉ tải lần đầu)"
if .venv/bin/python -m playwright install chromium; then
  ok "Trình duyệt đã sẵn sàng"
else
  loi "Tải trình duyệt không được — kiểm mạng rồi chạy lại."; dung
fi
chmod +x mo-tool.command 2>/dev/null

echo
echo "${XANH}${DAM}✓ Cài xong.${HET} Mở tool: nhấp đúp file ${DAM}mo-tool.command${HET} trong thư mục này"
echo "  (hoặc gõ: ./mo-tool.command). Trình duyệt sẽ mở http://127.0.0.1:8770"
