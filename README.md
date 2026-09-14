# Windows AI Translation Input Tool (Gboard Translate for Windows)

Ứng dụng Windows chạy nền, cung cấp trải nghiệm dịch thuật tức thì tương tự tính năng **Translate của Gboard**:
* Gõ nội dung bằng Tiếng Việt (hoặc bất kỳ ngôn ngữ nào) trong bất kỳ ứng dụng nào: **Chrome, Edge, Discord, Zalo, Telegram, Messenger, Word, Notepad, VS Code, Slack, Skype...**
* Bôi đen văn bản và nhấn phím tắt toàn hệ thống (mặc định `Ctrl + Alt + T`).
* Ứng dụng tự động đọc văn bản, dịch sang ngôn ngữ đích thông qua AI (Google Gemini, OpenAI GPT-4o-mini, hoặc Google Translate đa tầng).
* Tự động thay thế nội dung cũ bằng nội dung đã dịch ngay tại vị trí con trỏ chuột.
* Tự động khôi phục nội dung clipboard ban đầu của người dùng.
* **Dịch hai chiều tự động**: gõ tiếng Việt ra tiếng Anh, gõ tiếng Anh ra tiếng Việt — cùng một phím tắt.
* **Xem trước kết quả** cạnh con trỏ trước khi thay chữ, kèm nút đổi ngôn ngữ và dịch lại.
* **Hồ sơ theo ứng dụng**: Discord thân mật, Outlook trang trọng, mỗi ứng dụng một cấu hình riêng.
* **Từ điển thuật ngữ**: tên thương hiệu và thuật ngữ nội bộ luôn giữ nguyên qua mọi lần dịch.
* **Dịch vùng màn hình bằng OCR** — đọc được cả chữ trong ảnh, game, hoặc ứng dụng không cho bôi đen.
* Hỗ trợ **56 ngôn ngữ**.
* Tích hợp khay hệ thống (System Tray), cửa sổ cài đặt đa năng (Settings), và lịch sử dịch thuật (History) với chế độ bảo mật Privacy Mode.

---

## Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt & Thiết lập](#2-cài-đặt--thiết-lập)
3. [Cấu hình API Keys](#3-cấu-hình-api-keys)
4. [Hướng dẫn sử dụng](#4-hướng-dẫn-sử-dụng)
5. [Cấu hình Phím tắt (Global Hotkeys)](#5-cấu-hình-phím-tắt-global-hotkeys)
6. [Các chế độ dịch](#6-các-chế-độ-dịch)
7. [Dịch hai chiều tự động](#7-dịch-hai-chiều-tự-động)
8. [Xem trước kết quả](#8-xem-trước-kết-quả)
9. [Hồ sơ theo ứng dụng](#9-hồ-sơ-theo-ứng-dụng)
10. [Từ điển thuật ngữ](#10-từ-điển-thuật-ngữ)
11. [Dịch vùng màn hình bằng OCR](#11-dịch-vùng-màn-hình-bằng-ocr)
12. [Chế độ bảo mật (Privacy Mode)](#12-chế-độ-bảo-mật-privacy-mode)
13. [Chạy Unit Tests](#13-chạy-unit-tests)
14. [Đóng gói thành file EXE (PyInstaller)](#14-đóng-gói-thành-file-exe-pyinstaller)
15. [Tạo bộ cài đặt Windows (Inno Setup)](#15-tạo-bộ-cài-đặt-windows-inno-setup)
16. [Kiến trúc kỹ thuật & Giới hạn](#16-kiến-trúc-kỹ-thuật--giới-hạn)

---

## 1. Yêu cầu hệ thống

* **Hệ điều hành**: Windows 10 / Windows 11 (64-bit).
* **Python**: Python 3.10 trở lên (khuyên dùng Python 3.12+).
* Không bắt buộc cài Python nếu sử dụng bản đóng gói sẵn `dist\AITranslator.exe`.

---

## 2. Cài đặt & Thiết lập

### Bước 1: Clone hoặc tải mã nguồn
```powershell
cd d:\Code\gbroad
```

### Bước 2: Cài đặt các thư viện phụ thuộc
```powershell
python -m pip install -r requirements.txt
```

Các thư viện chính bao gồm:
* `PySide6`: Giao diện đồ họa hiện đại và biểu tượng Khay hệ thống.
* `keyring`: Tích hợp Windows Credential Manager để mã hóa lưu trữ API Keys.
* `pywin32`: Thao tác trực tiếp với Windows Clipboard đa định dạng.
* `ctypes` (Win32 `RegisterHotKey`): Đăng ký phím tắt toàn hệ thống. Hệ điều hành giữ lại tổ hợp nên ứng dụng đang chạy phía trước không nhận được nó.
* `httpx`: Thực hiện các cuộc gọi REST API bất đồng bộ với timeout và retry.
* `python-dotenv`: Đọc cấu hình từ file môi trường `.env`.

---

## 3. Cấu hình API Keys

Ứng dụng hỗ trợ 3 Translation Providers:
1. **Google Translate**: **Hoạt động ngay lập tức không cần cấu hình API Key** nhờ cơ chế đa tầng (Google Cloud API v2 -> Google Single Endpoint -> Google Mobile Web Endpoint -> MyMemory Fallback).
2. **Google Gemini**: Dùng các mô hình như `gemini-2.5-flash`, `gemini-1.5-flash` cho chất lượng dịch vượt trội và khả năng viết lại (Rewrite).
3. **OpenAI**: Dùng các mô hình như `gpt-4o-mini`, `gpt-4o`.

### Cách 1: Thiết lập trực quan qua giao diện Settings (Khuyên dùng)
1. Nhấp đúp vào icon ứng dụng dưới **Khay hệ thống (System Tray)** hoặc chuột phải chọn **Settings**.
2. Chuyển sang tab **API Keys**.
3. Nhập `Gemini API Key` hoặc `OpenAI API Key`.
4. Nhấn **Save & Apply**. Khóa API sẽ được mã hóa an toàn trong **Windows Credential Manager** (`WinVaultKeyring`), không bị lưu dưới dạng plaintext trong bất kỳ file cấu hình nào!

### Cách 2: Thiết lập qua file `.env`
Sao chép `.env.example` thành `.env`:
```powershell
cp .env.example .env
```
Điền các giá trị:
```env
GEMINI_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-...
DEFAULT_PROVIDER=gemini
DEFAULT_TARGET_LANGUAGE=en
```

---

## 4. Hướng dẫn sử dụng

### Khởi chạy ứng dụng
```powershell
python main.py
```
Ứng dụng sẽ khởi động thu nhỏ dưới khay hệ thống (góc dưới bên phải màn hình Windows). Một thông báo nổi (Floating Toast) sẽ xuất hiện xác nhận ứng dụng đang chạy nền.

### Quy trình dịch văn bản (Gboard Experience)
1. Mở bất kỳ ứng dụng nào: Chrome, Discord, Telegram, Zalo, VS Code, Word, Notepad...
2. Nhập văn bản Tiếng Việt, ví dụ:
   > "Tôi đang học lập trình và muốn cải thiện tiếng Anh."
3. Bôi đen đoạn văn bản vừa nhập.
4. Nhấn tổ hợp phím tắt:
   ```text
   Ctrl + Alt + T
   ```
5. Ứng dụng hiển thị thông báo nổi `"Translating..."`, gọi AI dịch thuật, tự động xóa text cũ và thay thế bằng:
   > "I'm learning programming and want to improve my English."
6. Thông báo nổi chuyển sang màu xanh `"Translated → English"`, và nội dung clipboard ban đầu của bạn được phục hồi nguyên vẹn!

---

## 5. Cấu hình Phím tắt (Global Hotkeys)

Mặc định ứng dụng cung cấp các phím tắt toàn hệ thống sau:

| Phím tắt | Chức năng | Ngôn ngữ đích |
|---|---|---|
| `Ctrl + Alt + T` | Dịch văn bản đang chọn | Theo ngôn ngữ đã chọn trong Settings |
| `Ctrl + Alt + E` | Dịch nhanh sang Tiếng Anh | English (`en`) |
| `Ctrl + Alt + C` | Dịch nhanh sang Tiếng Trung | Chinese Simplified (`zh-CN`) |
| `Ctrl + Alt + J` | Dịch nhanh sang Tiếng Nhật | Japanese (`ja`) |
| `Ctrl + Alt + O` | Chọn vùng màn hình và dịch chữ trong đó (OCR) | Theo ngôn ngữ đã chọn |

Bạn có thể bật/tắt hoặc thay đổi các phím tắt này bất kỳ lúc nào trong **Settings -> Hotkeys**. Thay đổi sẽ có hiệu lực ngay lập tức mà không cần khởi động lại ứng dụng.

---

## 6. Các chế độ dịch

### Mode 1 — Translate Selected Text (Mặc định)
Bôi đen văn bản -> Nhấn `Ctrl + Alt + T` -> Thay thế trực tiếp tại chỗ.

### Mode 2 — Clipboard Translation (Dịch nội dung Clipboard)
Nếu người dùng nhấn phím tắt khi **không có văn bản nào được chọn**:
* Ứng dụng đọc nội dung đang có sẵn trong Clipboard.
* Tiến hành dịch sang ngôn ngữ đích.
* Ghi kết quả dịch vào Clipboard và hiển thị thông báo `"Translated → [Ngôn ngữ] (Copied to clipboard)"`.
* Không tự động paste để tránh chèn nhầm vị trí.

### Mode 3 — AI Rewrite / Polish (Viết lại & Trau chuốt văn phong)
Trong tab **Settings -> Translation**, chọn **Operation Mode: AI Rewrite / Polish** và chọn phong cách:
* **Natural**: Văn phong tự nhiên, trôi chảy như người bản xứ.
* **Formal**: Văn phong trang trọng, chuẩn mực cho công việc, email đối tác.
* **Casual**: Văn phong thân mật, trò chuyện hàng ngày.
* **Polish**: Sửa lỗi ngữ pháp, cải thiện độ mạch lạc và dùng từ chính xác.

---

## 7. Dịch hai chiều tự động

Mặc định đã bật. Ứng dụng nhìn vào nội dung để tự chọn chiều dịch:

* Bôi đen **"Tôi đang học lập trình"** → `Ctrl + Alt + T` → ra tiếng Anh.
* Bôi đen **"I am learning to code"** → `Ctrl + Alt + T` → ra tiếng Việt.

Không cần vào Settings đổi ngôn ngữ đích giữa chừng. Cặp ngôn ngữ đổi được trong
**Settings → Dịch thuật & AI → Dịch hai chiều tự động**.

Nhận diện dựa trên bộ dấu tiếng Việt và bảng mã chữ viết (Nhật, Hàn, Trung, Thái, Nga, Ả Rập...),
chạy cục bộ nên không tốn thêm một vòng gọi mạng nào. Các phím tắt gán cứng ngôn ngữ
(`Ctrl + Alt + E/C/J`) không bị ảnh hưởng.

---

## 8. Xem trước kết quả

Bật trong **Settings → Dịch thuật & AI → Xem trước kết quả**.

Thay vì thay chữ ngay, ứng dụng hiện một popup nhỏ ngay cạnh con trỏ:

* **Thay thế** — dán bản dịch đè lên đoạn đang bôi đen.
* **Chép** — chỉ chép vào clipboard, không đụng vào văn bản.
* **Đổi ngôn ngữ** — chọn ngôn ngữ khác trong danh sách, ứng dụng dịch lại ngay.

Popup không cướp tiêu điểm, nên con trỏ vẫn nằm nguyên trong ô nhập liệu.
Nếu bỏ qua, popup tự đóng và clipboard gốc được khôi phục.

---

## 9. Hồ sơ theo ứng dụng

Trong **Settings → Theo ứng dụng**, gán ngôn ngữ và văn phong riêng cho từng chương trình:

| Ứng dụng | Ngôn ngữ đích | Chế độ | Văn phong |
|---|---|---|---|
| `discord.exe` | Tiếng Anh | Dịch thuật | Thân mật |
| `outlook.exe` | Tiếng Anh | Viết lại | Trang trọng |

Nút **Thêm ứng dụng đang mở** tự điền tên file chạy của cửa sổ bạn vừa dùng.

Thứ tự ưu tiên, mạnh nhất trước: phím tắt gán cứng ngôn ngữ → hồ sơ ứng dụng →
dịch hai chiều tự động → cài đặt chung. Muốn một ứng dụng vẫn dùng dịch hai chiều tự động
thì để trống ô ngôn ngữ đích của hồ sơ đó.

---

## 10. Từ điển thuật ngữ

Trong **Settings → Thuật ngữ**. Dùng cho tên thương hiệu, tên sản phẩm, biệt danh,
thuật ngữ nội bộ — những từ mà mỗi lần dịch lại ra một kiểu khác nhau.

| Từ gốc | Dịch thành | Kết quả |
|---|---|---|
| `Zalo` | *(để trống)* | Luôn giữ nguyên `Zalo` |
| `deadline` | `hạn chót` | Luôn dịch thành `hạn chót` |

Cách hoạt động: từ được thay bằng một ký hiệu tạm trước khi gửi đi, rồi trả lại sau khi dịch xong.
Nhờ vậy nó hoạt động với **mọi provider**, kể cả Google Translate — chứ không chỉ với các
provider AI nhận được chỉ dẫn trong prompt.

---

## 11. Dịch vùng màn hình bằng OCR

Nhấn `Ctrl + Alt + O`, kéo chuột chọn một vùng màn hình bất kỳ. Ứng dụng đọc chữ trong vùng đó,
dịch, rồi chép kết quả vào clipboard.

Dùng được cho những chỗ không thể bôi đen: chữ trong ảnh, game toàn màn hình, Remote Desktop,
PDF quét, ứng dụng vẽ giao diện riêng.

OCR chạy bằng bộ nhận dạng có sẵn của Windows (`Windows.Media.Ocr`) — **hoàn toàn ngoại tuyến,
không tốn quota API nào**, mất khoảng 10 ms cho một vùng cỡ một đoạn văn.

> **Lưu ý về tiếng Việt**: Windows chỉ nhận dạng được những ngôn ngữ đã cài gói OCR.
> Nếu máy chỉ có tiếng Anh, chữ tiếng Việt sẽ bị đọc sai dấu (`Phát triển` → `Phät trién`).
> Cài thêm tại **Settings → Time & Language → Language & region** → chọn Tiếng Việt →
> **Language options** → bật **Optical character recognition**.

---

## 12. Chế độ bảo mật (Privacy Mode)

Khi bật **Privacy Mode** trong tab **Settings -> General**:
1. Toàn bộ lịch sử dịch thuật sẽ **không bao giờ được lưu vào cơ sở dữ liệu SQLite**.
2. Bộ nhớ đệm bản dịch bị tắt hoàn toàn — không giữ lại nội dung nào trong RAM.
3. Toàn bộ nội dung văn bản sẽ được che mờ khỏi file log hệ thống `logs/app.log`.
4. Khóa API luôn được bảo vệ bởi Windows Credential Manager.

---

## 13. Chạy Unit Tests

Ứng dụng đi kèm bộ test 97 bài, phủ cơ sở dữ liệu, clipboard, xử lý văn bản, phím tắt, nhận diện ngôn ngữ, từ điển thuật ngữ, hồ sơ ứng dụng, OCR và các API provider:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 14. Đóng gói thành file EXE (PyInstaller)

Để đóng gói thành một file thực thi duy nhất `dist\AITranslator.exe`:

Chạy file script tự động:
```powershell
.\build.bat
```
Hoặc chạy lệnh trực tiếp:
```powershell
pyinstaller --clean AITranslator.spec
```
Sau khi hoàn thành, file thực thi sẽ nằm tại:
```text
dist\AITranslator.exe
```
Người dùng có thể sao chép file này sang bất kỳ máy tính Windows nào và chạy trực tiếp mà không cần cài đặt Python!

---

## 15. Tạo bộ cài đặt Windows (Inno Setup)

Nếu máy tính đã cài **Inno Setup**:
1. Chuột phải vào file `installer.iss` chọn **Compile**, hoặc mở bằng Inno Setup Compiler và bấm **Run**.
2. File cài đặt sẽ được tạo ra tại thư mục gốc:
   ```text
   Output\AITranslator_Setup_v1.0.0.exe
   ```
Bộ cài đặt hỗ trợ:
* Tùy chọn tạo biểu tượng Desktop và Start Menu.
* Tùy chọn tự động chạy cùng Windows (`Start with Windows`).
* Trình gỡ cài đặt sạch sẽ (Uninstaller).

---

## 16. Kiến trúc kỹ thuật & Giới hạn

### Cấu trúc thư mục
```text
gbroad/
├── main.py                     # Khởi chạy ứng dụng, Single-Instance Lock, UI Signals
├── config.py                   # Quản lý cài đặt & Windows Credential Manager (keyring)
├── database.py                 # SQLite lưu trữ lịch sử & tìm kiếm toàn văn
│
├── core/
│   ├── translator.py           # Điều phối provider, retry exponential backoff, timeout 15s
│   ├── clipboard_manager.py    # Sao lưu đa định dạng (Unicode, DIB, HDROP) & giả lập Win32
│   ├── hotkey_manager.py       # Phím tắt toàn hệ thống qua Win32 RegisterHotKey
│   ├── language_detect.py      # Nhận diện ngôn ngữ cục bộ cho chế độ dịch hai chiều
│   ├── app_context.py          # Ứng dụng đang chạy phía trước & vị trí con trỏ nhập
│   ├── glossary.py             # Bảo vệ thuật ngữ bằng ký hiệu tạm
│   ├── ocr.py                  # Chụp vùng màn hình (GDI) + OCR ngoại tuyến của Windows
│   └── text_processor.py       # Bảo toàn khoảng trắng, nhận diện code block & định dạng
│
├── providers/
│   ├── base.py                 # TranslationProvider Interface & Exception classes
│   ├── http.py                 # httpx.Client dùng chung, giữ kết nối sống giữa các lần dịch
│   ├── google.py               # Google Translate đa tầng (v2 API, Single, Mobile, MyMemory)
│   ├── gemini.py               # Google Gemini generateContent REST API
│   └── openai.py               # OpenAI chat/completions REST API
│
├── ui/
│   ├── tray.py                 # Khay hệ thống và menu ngữ cảnh
│   ├── toast.py                # Thông báo nổi không cướp tiêu điểm (Focus-safe)
│   ├── preview_popup.py        # Popup xem trước cạnh con trỏ
│   ├── region_selector.py      # Lớp phủ kéo chọn vùng màn hình cho OCR
│   ├── settings_window.py      # Cửa sổ cấu hình tabbed
│   ├── history_window.py       # Cửa sổ tìm kiếm và quản lý lịch sử
│   └── resources.py            # Tạo icon vector độ phân giải cao bằng code
│
├── utils/
│   ├── logger.py               # Log xoay vòng với bộ lọc che giấu API keys & Privacy Mode
│   └── startup.py              # Đăng ký khởi động cùng Windows qua Registry
│
├── tests/                      # Bộ unit tests cho tất cả các module
├── assets/                     # Icon ứng dụng (icon.ico, icon.png)
├── requirements.txt
├── .env.example
├── README.md
├── build.bat
├── AITranslator.spec
└── installer.iss
```

### Các giải pháp giải quyết rủi ro kỹ thuật trên Windows:
1. **Tránh xung đột phím bổ trợ (Modifier Key Interference)**:
   Khi người dùng bấm `Ctrl + Shift + T`, họ có thể vẫn đang giữ phím vật lý `Shift`. Nếu ứng dụng phát lệnh `Ctrl + C` ngay lập tức, Windows sẽ nhận thành `Ctrl + Shift + C` (làm mở DevTools trên trình duyệt hoặc không hoạt động trên Discord). Ứng dụng giải quyết triệt để bằng cách dùng `ClipboardManager.release_modifier_keys()` để phát sự kiện nhả `Shift/Ctrl/Alt` trước khi gửi phím tắt giả lập.
2. **Phím tắt không lọt xuống ứng dụng đích (Hotkey Suppression)**:
   Một trình lắng nghe bàn phím chỉ *quan sát* phím mà không tiêu thụ nó, nên ứng dụng đang chạy phía trước vẫn nhận được tổ hợp: bấm `Ctrl + Shift + T` trong Chrome vừa dịch vừa mở lại tab vừa đóng. Ứng dụng dùng Win32 `RegisterHotKey` — hệ điều hành giữ lại tổ hợp và không chuyển tiếp cho ứng dụng nào khác. Mặc định cũng chuyển sang nhóm `Ctrl + Alt` để tránh các lệnh phổ biến của trình duyệt và IDE.
3. **Bảo toàn định dạng Clipboard**:
   Sử dụng Win32 API `EnumClipboardFormats` để sao lưu toàn bộ dữ liệu nhị phân của các định dạng đang có trước khi thực hiện thao tác thay thế, và phục hồi lại sau khi ứng dụng đích hoàn tất việc paste.
4. **Giới hạn đã biết**:
   * Một số ứng dụng có quyền quản trị cao hơn (Administrator / UAC Elevated) có thể chặn phím tắt gửi từ một tiến trình không có quyền Admin do cơ chế UIPI (User Interface Privilege Isolation) của Windows. Để khắc phục triệt để trên các ứng dụng này, hãy chạy `AITranslator.exe` với quyền **Run as Administrator**.
   * Các ứng dụng đặc thù sử dụng canvas vẽ giao diện riêng hoặc game toàn màn hình không có cơ chế copy bôi đen chuẩn Windows clipboard sẽ tự động kích hoạt **Mode 2 (Dịch clipboard)** thay vì Mode 1.
