# Hướng dẫn cài đặt Creative Tracker (cho người không biết code)

Làm **một lần** trên máy Mac, mất khoảng **10–20 phút** (phần lớn là chờ tải). Bạn chỉ cần copy–dán đúng từng lệnh dưới đây.

> Cài xong rồi? Xem **[Hướng dẫn sử dụng](HUONG-DAN-SU-DUNG.md)**.

---

## Bước 1 — Mở Terminal

Terminal là ô gõ lệnh có sẵn trên mọi máy Mac.

1. Bấm **⌘ Command + Space** (mở Spotlight).
2. Gõ `Terminal`, bấm **Enter**.
3. Một cửa sổ chữ hiện ra, dòng cuối kiểu `tenmay@MacBook ~ %`. Đây là nơi bạn dán lệnh.

**Cách dán một lệnh:** copy lệnh trong khung xám → bấm vào cửa sổ Terminal → **⌘ Command + V** → **Enter**.

## Bước 2 — Cài Homebrew (trình cài phần mềm cho Mac)

Kiểm xem máy đã có chưa:
```bash
brew --version
```
- Ra dòng `Homebrew 4.x.x` hoặc mới hơn → **đã có, sang Bước 3**.
- Ra `command not found: brew` → dán lệnh cài chính thức của Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- Máy hỏi **Password**: gõ mật khẩu đăng nhập máy Mac rồi **Enter**. Lúc gõ, màn hình **không hiện gì**, đó là bình thường.
- Máy hỏi `Press RETURN to continue`: bấm **Enter**.
- Có thể máy đòi cài **Command Line Tools** (có kèm `git`): bấm **Install** trong cửa sổ hiện ra.
- Cuối cùng Homebrew in mục **Next steps** với 2–3 dòng lệnh bắt đầu bằng `echo` và `eval`. **Copy–dán đúng các dòng đó** rồi Enter.
- **Đóng Terminal, mở lại** (⌘ + Q rồi làm lại Bước 1). Gõ lại `brew --version` → phải ra `Homebrew …`.

## Bước 3 — Lấy tool về máy

Chọn **một** trong hai cách.

### Cách A — Tải file ZIP (dễ nhất)
1. Mở trang repo trên GitHub (bạn phải đăng nhập GitHub và đã được mời vào repo).
2. Bấm nút xanh **Code** → **Download ZIP**.
3. Mở thư mục **Downloads**, nhấp đúp file ZIP để giải nén → được thư mục `creative-tracker-adlibrary-main`.
4. Kéo thư mục đó vào thư mục **Documents** (hoặc chỗ bạn muốn để lâu dài).
5. Bỏ "khoá" của macOS cho file tải từ mạng. Trong Terminal gõ `xattr -dr com.apple.quarantine ` (**có dấu cách ở cuối**), **kéo thả thư mục tool vào cửa sổ Terminal**, rồi Enter:
   ```bash
   xattr -dr com.apple.quarantine ~/Documents/creative-tracker-adlibrary-main
   ```
   Không in gì là đúng.

### Cách B — Dùng git (để cập nhật bản mới dễ hơn)
```bash
brew install gh
gh auth login
```
Chọn `GitHub.com` → `HTTPS` → `Login with a web browser`, làm theo hướng dẫn trên trình duyệt. Sau đó:
```bash
cd ~/Documents
gh repo clone namhd-SG/creative-tracker-adlibrary
```
Đúng: in `Cloning into 'creative-tracker-adlibrary'…` và không có chữ `error`.

## Bước 4 — Đi vào thư mục tool trong Terminal

Gõ `cd ` (**có dấu cách**), **kéo thả thư mục tool vào cửa sổ Terminal**, rồi Enter. Ví dụ:
```bash
cd ~/Documents/creative-tracker-adlibrary
```
Kiểm:
```bash
ls
```
Đúng: thấy các tên `cai-dat.sh`, `mo-tool.command`, `README.md`…

## Bước 5 — Cài (một lệnh)

```bash
bash cai-dat.sh
```

Script tự làm hết: kiểm máy Mac, kiểm Homebrew, cài **Python** nếu thiếu, cài tool vào thư mục riêng `.venv`, tải **trình duyệt ẩn** (~150 MB) dùng để đọc Ad Library. Lần đầu mất vài phút. **Kết quả đúng:**

```
1/5  Máy Mac
  ✓ macOS 15.x
2/5  Homebrew (trình cài phần mềm)
  ✓ Homebrew 4.x
3/5  Python 3.11 trở lên
  ✓ Python 3.12.x (/opt/homebrew/bin/python3.12)
4/5  Cài tool vào thư mục .venv …
  ✓ .venv sẵn sàng
  ✓ Đã cài Creative Tracker (lệnh ctal chạy được)
5/5  Trình duyệt ẩn để đọc Ad Library (~150 MB, chỉ tải lần đầu)
  ✓ Trình duyệt đã sẵn sàng

✓ Cài xong. Mở tool: nhấp đúp file mo-tool.command trong thư mục này
```

Có dòng **✗** thì làm đúng việc ghi trên dòng đó, rồi chạy lại `bash cai-dat.sh`. Chạy lại bao nhiêu lần cũng không sao.

## Bước 6 — Mở tool

**Nhấp đúp file `mo-tool.command`** trong thư mục tool (dùng Finder).

- Một cửa sổ Terminal mở ra, ghi `Creative Tracker đang chạy: http://127.0.0.1:8770`.
- Trình duyệt tự mở trang **http://127.0.0.1:8770**. Không tự mở thì copy địa chỉ đó dán vào Chrome/Safari.
- **Để cửa sổ Terminal đó mở** suốt lúc dùng tool. Đóng nó là tool tắt.

**macOS báo "không thể mở vì nhà phát triển không xác định" / "Apple không thể kiểm tra…"** (chỉ gặp lần đầu):
- **Chuột phải** (hoặc Control + bấm) vào `mo-tool.command` → **Open (Mở)** → **Open (Mở)**. Từ lần sau nhấp đúp bình thường.
- Vẫn bị chặn: vào **System Settings → Privacy & Security**, kéo xuống, bấm **Open Anyway (Vẫn mở)**.
- Hoặc gõ trong Terminal (ở thư mục tool): `xattr -d com.apple.quarantine mo-tool.command`

Không nhấp đúp được? Trong Terminal (ở thư mục tool) gõ: `./mo-tool.command`

## Bước 7 — Lần sau mở lại, tắt, cập nhật

| Muốn | Làm |
|---|---|
| **Mở lại tool** | Nhấp đúp `mo-tool.command`. Nếu tool đang mở sẵn, file này chỉ mở lại trang web, không chạy thêm bản thứ hai. |
| **Tắt tool** | Bấm vào cửa sổ Terminal của tool → **Control + C**. Hoặc đóng cửa sổ đó. |
| **Cập nhật bản mới (cách B, git)** | Tắt tool. Mở Terminal ở thư mục tool: `git pull` rồi `bash cai-dat.sh`. |
| **Cập nhật bản mới (cách A, ZIP)** | Tải ZIP mới (Bước 3), giải nén ra thư mục mới. **Chép sang thư mục mới**: thư mục `data` (dữ liệu đã quét) và file `doi_thu.csv` (danh sách đối thủ). Chạy `bash cai-dat.sh` trong thư mục mới. |

Dữ liệu của bạn chỉ nằm trên máy: `data/` (ảnh, cơ sở dữ liệu) và `doi_thu.csv`.

---

## Lỗi thường gặp — thấy chữ X thì làm Y

| Thấy | Làm |
|---|---|
| `command not found: brew` | Chưa cài Homebrew, hoặc chưa chạy 2–3 dòng **Next steps** của Homebrew. Làm lại Bước 2, rồi **đóng và mở lại Terminal**. |
| `zsh: command not found: ctal` | Bạn gõ `ctal` trực tiếp. Hãy dùng `./mo-tool.command`, hoặc `.venv/bin/ctal …` trong thư mục tool. |
| `bash: cai-dat.sh: No such file or directory` | Terminal chưa đứng trong thư mục tool. Làm lại Bước 4 (gõ `cd ` rồi kéo thả thư mục vào). |
| `✗ Chưa có Python 3.11+…` / cài Python lỗi | Chạy `brew install python@3.12`, đóng–mở lại Terminal, chạy lại `bash cai-dat.sh`. |
| Python sai bản (script báo Python quá cũ) | Python có sẵn của macOS là bản cũ 3.9, tool không dùng được. Script tự cài bản mới qua Homebrew; gặp lỗi thì làm như dòng trên. |
| `✗ Tải trình duyệt không được` / trang báo lỗi `Executable doesn't exist … playwright install` | Mạng bị ngắt lúc tải. Chạy lại `bash cai-dat.sh`. |
| Nhấp đúp `mo-tool.command` bị chặn ("nhà phát triển không xác định") | Chuột phải → Open → Open (xem Bước 6). |
| Nhấp đúp `mo-tool.command` thì mở bằng TextEdit / báo `Permission denied` | Trong Terminal ở thư mục tool: `chmod +x mo-tool.command`, rồi nhấp đúp lại. |
| `✗ Cổng 8770 đang bị một chương trình khác dùng` | Mở bằng cổng khác: trong Terminal ở thư mục tool gõ `CONG=8771 ./mo-tool.command`, rồi vào http://127.0.0.1:8771 |
| Trang web trắng / "Không kết nối được" (This site can't be reached) | Cửa sổ Terminal của tool đã bị đóng. Nhấp đúp lại `mo-tool.command`. |
| `✗ Chưa cài` khi nhấp đúp `mo-tool.command` | Chưa chạy Bước 5: `bash cai-dat.sh`. |
| Quét báo `⚠ lỗi: Facebook đòi đăng nhập` | Facebook tạm chặn vì quét quá dày. Chờ vài giờ rồi quét lại; tool cố ý không vượt rào. |
