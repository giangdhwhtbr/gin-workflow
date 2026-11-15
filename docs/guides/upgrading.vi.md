# Nâng cấp lên 3.1 { #upgrading-to-31 }

Phiên bản 3.1 là mốc chuẩn có một con số chung cho cả bộ: gin, gin-qa, gin-orchestrator và gin-ba đều là 3.1.0. Đây cũng là phiên bản đầu tiên đọc `.ginrc`, file ghim phiên bản gin thấp nhất mà một project cần. Danh sách đầy đủ các thay đổi nằm trong [nhật ký thay đổi](../changelog.md#310-2026-11-15).

Một team nâng cấp theo thứ tự sau, và thứ tự này quan trọng:

1. Mọi member cập nhật gin trên máy của mình.
2. Chỉ sau đó lead mới chạy `gin setup update --approve` trong project và commit kết quả.
3. Từ lúc đó, member có gin cũ hơn bản ghim sẽ bị từ chối.

Gin 3.0 từ chối một cấu hình ở schema 2.10 (`configuration validation failed at schema_version: '2.10' is not one of [...]`) và không đọc `.ginrc`. Lead chạy bước 2 trước sẽ khóa mọi member còn dùng 3.0.

## Cập nhật một máy { #update-a-machine }

Cập nhật gin trên từng máy, dù dùng harness nào. Chạy một trong hai cách sau.

Từ một bản clone của repository này:

```bash
git pull
./install.sh --platform all
```

Hoặc dùng launcher, vốn clone `master` rồi chạy `install.sh`:

```bash
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform all
```

Thêm `--plugin all` để cập nhật cả các tiện ích mở rộng, hoặc `--plugin gin-qa`, `--plugin gin-ba`, `--plugin gin-orchestrator` cho từng cái. Trên Windows, chạy `install.ps1` như [hướng dẫn Windows](windows.md) mô tả.

Plugin cài từ marketplace được cập nhật qua harness của nó, và cài từ marketplace không cài các CLI, nên vẫn phải chạy installer. Trên Claude Code, chạy `claude plugin update gin@gin-workflow-marketplace` rồi khởi động lại Claude Code. Trên Codex, harness cập nhật plugin; `codex plugin --help` không có lệnh nào cập nhật plugin tại chỗ.

Kiểm tra kết quả:

```bash
gin version
```

Lệnh in ra phiên bản đã cài, bản ghim của project đang đứng, `compatible: yes` hoặc `no`, và phiên bản của gin-qa và gin-orchestrator khi tìm thấy. `gin --version` in ra `gin 3.1.0`. `gin setup doctor` cũng báo gin-qa hoặc gin-orchestrator có phiên bản khác gin; cài lại tiện ích đó bằng `./install.sh --plugin <name>`.

## Cập nhật một project { #update-a-project }

Lead làm việc này một lần cho mỗi project, sau khi mọi member đã cập nhật gin:

1. Chạy `gin setup update` để xem đề xuất, rồi `gin setup update --approve`. Lệnh migrate cấu hình lên schema 2.10 và ghi `.ginrc` với phiên bản đã cài. Lệnh ghi `.ginrc` cả khi không có migration nào đến hạn.
2. Chạy `gin hooks install` trong bản clone thiếu git hook. `gin setup doctor` báo những hook này.
3. Commit `.agent-workflow/config.yaml` và `.ginrc`, rồi báo cho team rằng pull request cần gin 3.1.0 trở lên.

Trong workspace, chỉ làm ở parent. Các child và worktree tìm thấy `.ginrc` của parent. [Tham chiếu cấu hình](../reference/config.md#ginrc) mô tả định dạng file và nơi gin tìm nó. Project không có `.ginrc` thì không bị kiểm tra gì, và `gin setup doctor` báo tình trạng này.

## Member bị từ chối { #a-member-who-is-refused }

Giả sử project ghim `3.2.0` và gin của bạn là 3.1.0. Khi đó mọi lệnh `gin` đọc project đều dừng và thoát với mã 2, kể cả `gin hooks run`. Vì vậy hook git commit và push thất bại trong project đó cho đến khi bạn cập nhật gin. Member vẫn dùng 3.0 không nhận được thông báo này. Gin 3.0 bỏ qua `.ginrc` và thất bại ở schema cấu hình, đó là lý do mọi member phải cập nhật trước. Thông báo như sau:

```text
error: gin 3.1.0 is older than this project needs (3.2.0, /path/to/project/.ginrc); update gin: https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/
```

Còn hai thông báo khác. Gin có major version mới hơn bản ghim sẽ báo `upgrade the project with gin setup update --approve`, và các lệnh `gin setup` vẫn chạy để lead nâng cấp. `.ginrc` không phải một phiên bản `X.Y.Z` sẽ báo `<path> must hold one version X.Y.Z`. [Tham chiếu CLI](../reference/cli.md) liệt kê cả ba.

Trên Claude Code, file hooks do `install.sh` hoặc `install.ps1` tạo còn chạy `gin version --hook` khi bắt đầu phiên. Khi đó agent thấy cùng thông báo, theo sau là `Tell the user before any other work.` Plugin Claude Code chỉ cài từ marketplace không có hook này, các harness khác cũng không; chúng hiện thông báo từ chối ở lệnh `gin` đầu tiên.

Để hết bị từ chối, [cập nhật máy của bạn](#update-a-machine), rồi chạy `gin version` và kiểm tra `compatible: yes`.

## Những gì thay đổi ở 3.1 { #what-changes-at-31 }

Nhật ký thay đổi liệt kê toàn bộ trong [ghi chú nâng cấp](../changelog.md#upgrade-notes). Cần xử lý những điểm sau:

- Gin cũ hơn 3.1 bỏ qua `.ginrc`, nên mọi member phải lên 3.1 một lần trước khi bản ghim bảo vệ được ai.
- Cấu hình chuyển sang schema 2.10, bỏ khóa `notifications`.
- `verify.run_at` mặc định là `push` ở rigor `easy` và `standard`: một track chỉ chạy test của phần nó thay đổi, và bộ test đầy đủ chạy một lần trước khi push. Để giữ hành vi cũ, chạy `gin setup configure --set verify.run_at=track --approve`.
- Đừng bật thiết lập team của 3.1, như `team.host: gitea` hoặc `codecommit`, trước khi mọi member đã cập nhật.
- Cài lại từng tiện ích đang dùng để gin-qa, gin-orchestrator và gin-ba khớp với gin.
