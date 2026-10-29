#!/bin/bash
# Cài Creative Tracker trên máy Mac — chạy một lần, chạy lại bao nhiêu lần cũng được.
#   bash cai-dat.sh
# Không dùng sudo. Thiếu thứ gì thì script dừng và in đúng việc cần làm.
# Máy Intel (Mac đời 2019 trở về trước): không cần Homebrew — Python lấy từ bộ cài chính thức python.org.

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

CHIP=$(uname -m)   # arm64 = chip Apple (M1, M2…), x86_64 = chip Intel
PY_INTEL=3.13.17   # bản Python có bộ cài chính thức cho Mac Intel (python.org không còn bộ cài cho 3.12)

buoc "1/5  Máy Mac"
if [ "$(uname)" != "Darwin" ]; then loi "Script này chỉ dành cho macOS."; dung; fi
MACOS=$(sw_vers -productVersion 2>/dev/null)
if [ "$CHIP" = "x86_64" ]; then TEN_CHIP="chip Intel"; else TEN_CHIP="chip Apple"; fi
# Trình duyệt ẩn (Chromium của Playwright) chỉ có bản cho macOS 14 Sonoma trở lên, cả chip Apple lẫn Intel.
if [ "${MACOS%%.*}" -lt 14 ] 2>/dev/null; then
  loi "macOS $MACOS ($TEN_CHIP) quá cũ — tool cần macOS 14 Sonoma trở lên."
  echo "    Cập nhật: menu  → Cài đặt hệ thống (System Settings) → Cài đặt chung → Cập nhật phần mềm."
  echo "    Mac Intel đời 2018–2019 lên được Sonoma 14 hoặc mới hơn. Cập nhật xong chạy lại: bash cai-dat.sh"
  dung
fi
ok "macOS $MACOS ($TEN_CHIP)"

buoc "2/5  Homebrew (trình cài phần mềm)"
if [ "$CHIP" = "x86_64" ]; then
  ok "Máy Intel: không cần Homebrew (Homebrew đã ngừng hỗ trợ Mac Intel; Python lấy từ python.org)"
elif command -v brew >/dev/null 2>&1; then
  ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"
else
  loi "Chưa có Homebrew. Dán lệnh sau vào Terminal, Enter, nhập mật khẩu máy khi được hỏi:"
  echo '      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  echo "    Cài xong, ĐÓNG Terminal, mở lại rồi chạy lại: bash cai-dat.sh"
  dung
fi

buoc "3/5  Python 3.11 trở lên"
tim_python() {
  for c in python3.13 python3.12 python3.11 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/3.13/bin/python3; do
    p=$(command -v "$c" 2>/dev/null) || continue
    "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null && { echo "$p"; return 0; }
  done
  return 1
}
PY=$(tim_python)
if [ -z "$PY" ] && [ "$CHIP" = "x86_64" ]; then
  pkg="$HOME/Downloads/python-$PY_INTEL-macos11.pkg"
  chu_y "Chưa có Python 3.11+. Đang tải bộ cài chính thức Python $PY_INTEL (~70 MB) về thư mục Downloads…"
  curl -fL --progress-bar -o "$pkg" "https://www.python.org/ftp/python/$PY_INTEL/python-$PY_INTEL-macos11.pkg" \
    || { loi "Tải không được — kiểm mạng rồi chạy lại."; dung; }
  open "$pkg"
  loi "Bộ cài Python vừa mở ra: bấm Continue / Agree / Install, nhập mật khẩu máy, chờ tới chữ \"The installation was completed\"."
  echo "    Xong thì ĐÓNG Terminal, mở lại rồi chạy lại: bash cai-dat.sh"
  dung
fi
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

# Python cài từ python.org chưa có sẵn chứng chỉ HTTPS ⇒ tải ảnh/video báo CERTIFICATE_VERIFY_FAILED.
kiem_https() { .venv/bin/python -c "import urllib.request; urllib.request.urlopen('https://www.facebook.com/', timeout=15)" 2>&1; }
if kiem_https | grep -q CERTIFICATE_VERIFY_FAILED; then
  v=$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  cc="/Applications/Python $v/Install Certificates.command"
  [ -f "$cc" ] && { chu_y "Python chưa có chứng chỉ HTTPS — đang cài (chạy \"$cc\")…"; bash "$cc" >/dev/null 2>&1; }
  if kiem_https | grep -q CERTIFICATE_VERIFY_FAILED; then
    loi "Python chưa có chứng chỉ HTTPS. Mở Finder → Applications → Python $v → nhấp đúp \"Install Certificates.command\", rồi chạy lại script."
    dung
  fi
  ok "Đã cài chứng chỉ HTTPS cho Python"
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
