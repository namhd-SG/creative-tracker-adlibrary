# Hướng dẫn cài đặt Creative Tracker (cho người không biết code)

Làm **một lần** trên máy Mac, mất khoảng **10–20 phút** (phần lớn là chờ tải). Bạn chỉ cần copy–dán đúng từng lệnh dưới đây.

> Cài xong rồi? Xem **[Hướng dẫn sử dụng](HUONG-DAN-SU-DUNG.md)**.

## Trước tiên — máy của bạn loại nào?

Bấm menu **** (góc trên trái) → **Giới thiệu về máy Mac này** (About This Mac):

| Dòng **Chip** / **Bộ xử lý** (Processor) | Loại máy | Làm |
|---|---|---|
| `Apple M1`, `M2`, `M3`… | chip Apple | làm đủ các bước dưới |
| `Intel Core i5`, `i7`… (Mac đời 2019 trở về trước) | chip Intel | **bỏ qua Bước 2** (không cần Homebrew); script tự tải Python ở Bước 5 |

Dòng **macOS** phải từ **14 (Sonoma)** trở lên — trình duyệt ẩn mà tool dùng không có bản cho macOS cũ hơn.
Máy đang ở 13 (Ventura) hoặc cũ hơn: menu  → **Cài đặt hệ thống** → **Cài đặt chung** → **Cập nhật phần mềm**, cập nhật lên Sonoma 14 hoặc mới hơn trước (Mac Intel đời 2018–2019 đều lên được). Cập nhật có thể mất 1 giờ.

---

## Bước 1 — Mở Terminal

Terminal là ô gõ lệnh có sẵn trên mọi máy Mac.

1. Bấm **⌘ Command + Space** (mở Spotlight).
2. Gõ `Terminal`, bấm **Enter**.
3. Một cửa sổ chữ hiện ra, dòng cuối kiểu `tenmay@MacBook ~ %`. Đây là nơi bạn dán lệnh.

**Cách dán một lệnh:** copy lệnh trong khung xám → bấm vào cửa sổ Terminal → **⌘ Command + V** → **Enter**.

## Bước 2 — Cài Homebrew (trình cài phần mềm cho Mac)

> **Máy Intel: bỏ qua bước này, sang Bước 3.** Homebrew đã ngừng hỗ trợ Mac Intel (không còn bản dựng sẵn, mọi thứ phải tự biên dịch rất lâu); tool không cần nó trên máy Intel.

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

### Cách B — Dùng git (để cập nhật bản mới dễ hơn; cần Homebrew ⇒ máy Intel dùng Cách A)
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

**Máy Intel — lần chạy đầu khác ở Bước 3/5:** chưa có Python thì script tự tải bộ cài chính thức **Python 3.13** (~70 MB, từ python.org) về thư mục Downloads và mở nó ra. Bấm **Continue** → **Continue** → **Agree** → **Install**, nhập mật khẩu máy, chờ chữ *The installation was completed*, bấm **Close**. Sau đó **đóng Terminal, mở lại** (Bước 1 và Bước 4) và chạy lại `bash cai-dat.sh`. Lần này sẽ ra:

```
1/5  Máy Mac
  ✓ macOS 14.x (chip Intel)
2/5  Homebrew (trình cài phần mềm)
  ✓ Máy Intel: không cần Homebrew (Homebrew đã ngừng hỗ trợ Mac Intel; Python lấy từ python.org)
3/5  Python 3.11 trở lên
  ✓ Python 3.13.x (/usr/local/bin/python3.13)
…
```

Nếu script báo thiếu chứng chỉ HTTPS, nó tự chạy `Install Certificates.command` của Python; vẫn báo thì làm như bảng lỗi bên dưới.

**Máy Intel (ví dụ MacBook 2019 i5) chậm hơn bao nhiêu?** *Ước tính, chưa đo trên máy Intel thật:* cài lâu hơn vài phút (chủ yếu là tải Python + trình duyệt ẩn, phụ thuộc mạng). Lúc dùng, việc quét chủ yếu là **chờ Facebook trả dữ liệu** nên chậm hơn không đáng kể — trên máy chip Apple, quét 5 page nhỏ mất ~4 phút; máy i5 có thể chậm hơn khoảng 1,5 lần ở phần mở trình duyệt và lướt trang.

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
| `command not found: brew` | Máy **Intel**: bình thường, không cần Homebrew — chạy thẳng `bash cai-dat.sh`. Máy **chip Apple**: chưa cài Homebrew, hoặc chưa chạy 2–3 dòng **Next steps** của Homebrew. Làm lại Bước 2, rồi **đóng và mở lại Terminal**. Đã cài mà vẫn báo: dán `eval "$(/opt/homebrew/bin/brew shellenv)"`. |
| `✗ macOS 13.x … quá cũ — tool cần macOS 14 Sonoma trở lên` | Cập nhật macOS (xem mục *Trước tiên* ở đầu trang), rồi chạy lại `bash cai-dat.sh`. |
| `✗ Bộ cài Python vừa mở ra…` (máy Intel) | Làm hết bộ cài Python (Install, nhập mật khẩu máy), **đóng–mở lại Terminal**, chạy lại `bash cai-dat.sh`. Lỡ đóng bộ cài: mở thư mục **Downloads**, nhấp đúp `python-3.13.17-macos11.pkg`. |
| `✗ Python chưa có chứng chỉ HTTPS` / lúc dùng báo `CERTIFICATE_VERIFY_FAILED` | Finder → **Applications** → thư mục **Python 3.13** → nhấp đúp **Install Certificates.command**, chờ chữ `update complete`, rồi chạy lại `bash cai-dat.sh`. |
| `zsh: command not found: ctal` | Bạn gõ `ctal` trực tiếp. Hãy dùng `./mo-tool.command`, hoặc `.venv/bin/ctal …` trong thư mục tool. |
| `bash: cai-dat.sh: No such file or directory` | Terminal chưa đứng trong thư mục tool. Làm lại Bước 4 (gõ `cd ` rồi kéo thả thư mục vào). |
| `✗ Chưa có Python 3.11+…` / cài Python lỗi (máy chip Apple) | Chạy `brew install python@3.12`, đóng–mở lại Terminal, chạy lại `bash cai-dat.sh`. |
| Python sai bản (script báo Python quá cũ) | Python có sẵn của macOS là bản cũ 3.9, tool không dùng được. Script tự cài bản mới qua Homebrew; gặp lỗi thì làm như dòng trên. |
| `✗ Tải trình duyệt không được` / trang báo lỗi `Executable doesn't exist … playwright install` | Mạng bị ngắt lúc tải. Chạy lại `bash cai-dat.sh`. |
| Nhấp đúp `mo-tool.command` bị chặn ("nhà phát triển không xác định") | Chuột phải → Open → Open (xem Bước 6). |
| Nhấp đúp `mo-tool.command` thì mở bằng TextEdit / báo `Permission denied` | Trong Terminal ở thư mục tool: `chmod +x mo-tool.command`, rồi nhấp đúp lại. |
| `✗ Cổng 8770 đang bị một chương trình khác dùng` | Mở bằng cổng khác: trong Terminal ở thư mục tool gõ `CONG=8771 ./mo-tool.command`, rồi vào http://127.0.0.1:8771 |
| Trang web trắng / "Không kết nối được" (This site can't be reached) | Cửa sổ Terminal của tool đã bị đóng. Nhấp đúp lại `mo-tool.command`. |
| `✗ Chưa cài` khi nhấp đúp `mo-tool.command` | Chưa chạy Bước 5: `bash cai-dat.sh`. |
| Quét báo `⚠ lỗi: Facebook đòi đăng nhập` | Facebook tạm chặn vì quét quá dày. Chờ vài giờ rồi quét lại; tool cố ý không vượt rào. |
