# Dùng gin-workflow trên Windows { #using-gin-workflow-on-windows }

Hướng dẫn này bao gồm việc cài đặt native, cấu hình, và sử dụng hằng ngày `gin-workflow` trên Windows 10 và Windows 11.

## Điều kiện tiên quyết { #prerequisites }

### PowerShell 7 { #powershell-7 }
`install.ps1` yêu cầu PowerShell 7 (`#requires -Version 7.0`), nên hãy cài `pwsh` thay vì Windows PowerShell 5.1:
```powershell
winget install Microsoft.PowerShell
```

### Python 3.11 { #python-311 }

Cài Python 3.11 trở lên từ python.org hoặc bằng winget. Các rule check import `tomllib`, vốn có từ 3.11, và `setup preset` cùng `setup doctor` nạp chúng. Launcher shim chạy `py -3` khi launcher `py` tồn tại và `python` trong các trường hợp khác, nên một trong hai phải nằm trên `PATH`:
```powershell
winget install Python.Python.3.12
```
Cài PyYAML, thứ mà CLI cần để đọc cấu hình của nó, cho interpreter mà shim chạy (`python -m pip install pyyaml` khi không có `py`):
```powershell
py -3 -m pip install pyyaml
```

### Git for Windows { #git-for-windows }
Cài Git:
```powershell
winget install Git.Git
```

## Cấu hình môi trường { #environment-configuration }

### Developer Mode { #developer-mode }

Chỉ `install.ps1 -Link` tạo symbolic link. Tạo chúng mà không có quyền administrator đòi hỏi Developer Mode. Nếu không có nó, `-Link` in một cảnh báo và sao chép file thay thế:
1. Mở **Windows Settings** (`Win + I`).
2. Vào **System**, rồi **For developers**.
3. Chuyển **Developer Mode** sang **On**.

### Execution policy { #execution-policy }
Cho phép chạy script cục bộ trong PowerShell:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Line ending { #line-endings }
`.gitattributes` của repository đặt `LF` cho các file trong repository và `CRLF` cho `*.ps1`, `*.bat`, và `*.cmd`. Để ngăn Git chuyển đổi line ending trên toàn cục:
```powershell
git config --global core.autocrlf false
```

## Cài đặt { #installation }

Chạy `install.ps1` từ gốc của repository `gin-workflow` đã clone:

### Cài cho mọi nền tảng (Claude, Antigravity, Copilot, Codex, OpenCode) { #install-for-all-platforms-claude-antigravity-copilot-codex-opencode }
```powershell
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform all
```

### Cài cho một nền tảng { #install-for-one-platform }
```powershell
# For Claude Code
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform claude

# For Antigravity
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform antigravity

# For GitHub Copilot CLI
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform copilot
```

### Cài vào repository hiện tại { #install-into-the-current-repository }
```powershell
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Project .
```

### PATH { #path }
Trình cài đặt thêm `%USERPROFILE%\.local\bin` vào `PATH` của người dùng một lần. Mở một terminal mới để nhận thay đổi. Truyền `-NoModifyPath` để giữ nguyên `PATH`; khi đó trình cài đặt in ra thư mục cần thêm. `-Uninstall` gỡ mục đó.

## Theo dõi task { #task-tracking }

`gin-workflow` hỗ trợ hai backend theo dõi task:

1. Markdown, là lựa chọn mặc định. Nó không cần công cụ nào thêm và lưu task và epic dưới dạng `.planning/tasks/*.md`. `/gin-workflow:setup` hỏi bạn dùng backend nào và đề xuất Markdown theo mặc định.
2. Beads (`bd`). Cài các binary `bd` và `dolt` cho Windows và đặt chúng trên `PATH`.

Skill `beads-migration` chuyển `.beads` sang `~/gin-beads/<repo>` và liên kết ngược lại bằng một symlink, đó là cách repository gin-workflow giữ cơ sở dữ liệu của nó. Trên Windows, hãy dùng junction thay thế, `cmd /c mklink /J .beads %USERPROFILE%\gin-beads\<repo>`, hoặc một bản sao thông thường của thư mục.

## Dùng hằng ngày { #daily-use }

Bên trong AI harness của bạn (Claude Code, Antigravity, và các harness khác), dùng các slash command:

- `/gin-workflow:setup`: khởi tạo `.agent-workflow/config.yaml`.
- `/gin-workflow:discuss`: khám phá requirement và viết spec.
- `/gin-workflow:plan`: biến spec thành plan triển khai.
- `/gin-workflow:orchestrate`: tạo worktree và khởi tạo task.
- `/gin-workflow:execute`: triển khai thay đổi và xác minh bằng test.
- `/gin-workflow:review`: chạy các chu kỳ review độc lập.
- `/gin-workflow:ship`: đóng task và merge.

Từ một terminal PowerShell, gọi trực tiếp CLI:
```powershell
# Check current workflow state
gin-workflow state

# Record a gate
gin-workflow record requirement-confirmed --evidence "docs/specs/my-feature.md" --actor user

# Query tasks
gin-workflow task list
```

## Xác minh việc cài đặt { #verifying-the-installation }

Chạy smoke test để kiểm tra việc cài đặt, các launcher, và CLI:

```powershell
pwsh -ExecutionPolicy Bypass -File .\tests\install_smoke_test.ps1
```

Một lần chạy thành công thoát với mã 0.
CI chạy cùng smoke test này trên `windows-latest` cho mỗi push và pull request.

## Xử lý sự cố { #troubleshooting }

### `PermissionError: [WinError 32]` hoặc `[WinError 5]` { #permissionerror-winerror-32-or-winerror-5 }

`gin-workflow` thử lại các khóa file và việc thay thế file nguyên tử trên Windows. Nếu Windows Defender hoặc phần mềm diệt virus khác làm các lần chạy test chậm đi, hãy thêm một ngoại lệ thư mục cho thư mục `.planning/worktrees/` của repository trong Windows Security.

### `EventPersistenceError: cannot lock ...: file locking requires POSIX or Windows advisory file locking` { #eventpersistenceerror-cannot-lock-file-locking-requires-posix-or-windows-advisory-file-locking }

Chạy một bản build CPython có cung cấp module thư viện chuẩn `msvcrt`.

### `OSError: [WinError 1314]` khi tạo symlink { #oserror-winerror-1314-when-creating-a-symlink }

Bật Developer Mode trong Windows Settings, hoặc chạy PowerShell với quyền Administrator. Chỉ `install.ps1 -Link` tạo symlink; khi không tạo được, nó sao chép file và in một cảnh báo.

### `argument cannot be passed safely through cmd.exe` { #argument-cannot-be-passed-safely-through-cmdexe }

Các worker OpenCode và Antigravity truyền prompt dưới dạng đối số dòng lệnh. Khi CLI của chúng chỉ là một shim `.cmd`, gin-orchestrator chạy nó qua `cmd.exe`, vốn không thể mang dấu nháy kép, dấu phần trăm, hay ngắt dòng, hoặc một dòng lệnh dài hơn 8.191 ký tự. Worker khi đó thất bại với thông báo này trước khi nó bắt đầu. Hãy route các track đó tới một worker đọc prompt từ stdin, như Claude Code hoặc Codex.
