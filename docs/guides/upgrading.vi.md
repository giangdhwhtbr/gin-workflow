# Nâng cấp lên 3.1 { #upgrading-to-31 }

Phiên bản 3.1 đưa cả bộ về một số phiên bản chung: gin, gin-qa, gin-orchestrator và gin-ba đều là 3.1.0. Đây cũng là phiên bản đầu tiên đọc `.ginrc`, file ghim phiên bản gin thấp nhất mà một project cần. Danh sách đầy đủ các thay đổi nằm trong [nhật ký thay đổi](../changelog.md#310-2026-11-15).

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

Lần chạy mặc định cập nhật gin và làm mới các tiện ích đã cài: gin-qa khi installer đã cài launcher của nó, và gin-ba khi `~/.claude/skills/gin-ba` tồn tại. `--plugin all` cài gin và mọi tiện ích. `--plugin gin-qa` hoặc `--plugin gin-ba` chỉ cài đúng tiện ích đó và không cập nhật gin, nên chạy sau lần chạy mặc định. Trên Windows, chạy `install.ps1` như [hướng dẫn Windows](windows.md) mô tả.

Plugin cài từ marketplace được cập nhật qua harness của nó, và cài từ marketplace không cài các CLI, nên vẫn phải chạy installer. Trên Claude Code, chạy `claude plugin update gin@gin-workflow-marketplace` rồi khởi động lại Claude Code. Codex không có lệnh nào cập nhật plugin tại chỗ; `codex plugin marketplace upgrade` làm mới marketplace, và installer cập nhật các CLI.

Kiểm tra kết quả:

```bash
gin version
```

Lệnh in ra phiên bản đã cài, bản ghim của project hiện tại, `compatible: yes` hoặc `no`, và phiên bản của gin-qa khi tìm thấy. `gin --version` in ra `gin 3.1.0`. `gin setup doctor` cũng báo gin-qa có phiên bản khác gin; cài lại tiện ích đó bằng `./install.sh --plugin <name>`.

## Cập nhật một project { #update-a-project }

Lead làm việc này một lần cho mỗi project, sau khi mọi member đã cập nhật gin:

1. Chạy `gin setup update` để xem đề xuất, rồi `gin setup update --approve`. Lệnh migrate cấu hình lên schema 2.11 và ghi `.ginrc` với phiên bản đã cài. Lệnh ghi `.ginrc` cả khi không có migration nào đến hạn.
2. Commit `.agent-workflow/config.yaml` và `.ginrc`, rồi báo cho team rằng pull request cần phiên bản gin ghi trong `.ginrc`. Bản ghim là phiên bản lead đã cài, và một lần `gin setup update --approve` sau đó nâng nó lên phiên bản đang cài lúc ấy.

Trong workspace, chỉ làm ở parent. Các child và worktree tìm thấy `.ginrc` của parent. [Tham chiếu cấu hình](../reference/config.md#ginrc) mô tả định dạng file và nơi gin tìm nó. Project không có `.ginrc` thì không bị kiểm tra gì, và `gin setup doctor` báo tình trạng này.

## Member bị từ chối { #a-member-who-is-refused }

Giả sử project ghim `3.2.0` và gin của bạn là 3.1.0. Khi đó mọi lệnh `gin` đọc project đều dừng và thoát với mã 2, kể cả `gin hooks run`. Vì vậy hook git commit và push thất bại trong project đó cho đến khi bạn cập nhật gin. Member vẫn dùng 3.0 không nhận được thông báo này. Gin 3.0 bỏ qua `.ginrc` và thất bại ở schema cấu hình, đó là lý do mọi member phải cập nhật trước. Member thấy `configuration validation failed at schema_version: '2.10'` thì cập nhật máy như mô tả ở trên. Thông báo từ chối như sau:

```text
error: gin 3.1.0 is older than this project needs (3.2.0, /path/to/project/.ginrc); update gin: https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/
```

Còn hai thông báo khác. Gin có major version mới hơn bản ghim sẽ báo `upgrade the project with gin setup update --approve`, và các lệnh `gin setup` vẫn chạy để lead nâng cấp. `.ginrc` không phải một phiên bản `X.Y.Z` sẽ báo `<path> must hold one version X.Y.Z`. [Tham chiếu CLI](../reference/cli.md) liệt kê cả ba.

Trên Claude Code, file hooks do `install.sh` hoặc `install.ps1` tạo còn chạy `gin version --hook` khi bắt đầu phiên. Khi đó agent thấy cùng thông báo, theo sau là `Tell the user before any other work.` Plugin Claude Code chỉ cài từ marketplace không có hook này, các harness khác cũng không; chúng hiện thông báo từ chối ở lệnh `gin` đầu tiên.

Để hết bị từ chối, [cập nhật máy của bạn](#update-a-machine), rồi chạy `gin version` và kiểm tra `compatible: yes`.

## Nâng cấp qua nhiều phiên bản { #upgrading-across-several-versions }

Một project có thể nhảy qua nhiều phiên bản trong một lần nâng cấp. Mọi member cập nhật gin lên phiên bản mới nhất trước. Sau đó lead đọc các mục bên dưới cho từng phiên bản cao hơn phiên bản hiện tại của project, từ cũ đến mới, và làm các bước của chúng.

Một lần `gin setup update --approve` chuyển cấu hình qua mọi bước schema đến schema hiện tại, nên chỉ chạy nó một lần, sau các bước thủ công. Lệnh này cũng nâng `.ginrc` lên phiên bản đã cài. Những bước nó không làm là các bước thủ công: xóa `usage:` ở 3.4, và commit lịch sử chạy của gin-qa ở 3.5.

Ví dụ, một project đang ở 3.2 chuyển lên 3.5:

1. Mọi member cập nhật gin lên 3.5.
2. Lead xóa `usage:` khỏi `.agent-workflow/config.yaml` và xóa `.agent-workflow/usage-prices.yaml` nếu có ([3.4](#what-changes-at-34)).
3. Lead chạy `gin setup update`, đọc đề xuất, rồi chạy `gin setup update --approve`. Lệnh này chuyển schema 2.10 sang 2.11 ([3.3](#what-changes-at-33)) và ghi `.ginrc` 3.5.0.
4. Lead commit `.agent-workflow/config.yaml` và `.ginrc`.

## Những gì thay đổi ở 3.1 { #what-changes-at-31 }

Nhật ký thay đổi liệt kê toàn bộ trong [ghi chú nâng cấp](../changelog.md#upgrade-notes). Cần xử lý những điểm sau:

- Gin cũ hơn 3.1 bỏ qua `.ginrc`, nên mọi member phải lên 3.1 một lần trước khi bản ghim bảo vệ được ai.
- Cấu hình chuyển sang schema 2.10, bỏ khóa `notifications`.
- Các điểm còn lại, như mặc định của `verify.run_at`, thiết lập team và việc cài lại tiện ích, nằm trong [ghi chú nâng cấp](../changelog.md#upgrade-notes).

## Những gì thay đổi ở 3.3 { #what-changes-at-33 }

gin 3.3 chạy mọi stage trong harness bạn đã mở và gỡ extension gin-orchestrator. Mỗi lần chạy `./install.sh` xóa launcher mà nó đã cài và các thư mục plugin của những harness được chọn. Nó giữ lại một launcher không do nó cài, kèm cảnh báo, và chạy thử (dry run) không xóa gì. Các khóa cấu hình `orchestrator`, `provider_mode` và `routing.review.independence` đi cùng, cũng như `gin setup models`, `--probe` và `--provider`. Lead làm việc này một lần cho mỗi project, sau khi mọi member đã cập nhật gin:

```bash
gin setup update --to-version 2.11 --approve
```

Project bỏ qua bước này vẫn chạy được, và `gin state` cảnh báo một lần. Lệnh cập nhật sao lưu rồi xóa `.agent-workflow/orchestrator.local.yaml`, và `gin setup rollback --backup <dir>` khôi phục nó. Review luôn là một session hoặc subagent mới của cùng harness. Việc gì chạy ở đâu tùy theo harness.

| Bước | Claude Code, Antigravity | Codex, OpenCode, Copilot |
|---|---|---|
| Thực thi một track | subagent native `gin:developer` | session tự implement track và ghi `in_session` lên bead |
| Review | subagent native `gin:code-reviewer` | dừng để bạn mở một session mới; chỉ tự review khi có `allow_self_review_fallback` |
| Research trong `discuss` và `plan`; scout, writer và reviewer trong `tech-doc` | subagent native | lần lượt từng việc trong session |

Nhật ký thay đổi liệt kê phần còn lại trong [ghi chú nâng cấp](../changelog.md#330-2026-11-21). [Providers](../concepts/providers.md) mô tả các role, model và review.

## Những gì thay đổi ở 3.4 { #what-changes-at-34 }

gin 3.4 bỏ việc theo dõi AI usage. Schema cấu hình vẫn là 2.11, và `gin setup update` không xóa các khóa cũ, nên lead xóa chúng bằng tay:

- Xóa `usage:` khỏi `.agent-workflow/config.yaml`. Đến khi xóa, `gin state` và `gin setup doctor` báo rằng khóa này bị bỏ qua.
- Xóa `.agent-workflow/usage-prices.yaml` nếu có. Không còn gì đọc file này.

`gin usage` và skill `report` đã bị gỡ; khi cài vào project, bản skill của gin bị xóa và skill `report` của gin-qa được giữ. `ai_usage` đã lưu trên bead vẫn còn. Nhật ký thay đổi liệt kê phần còn lại trong [ghi chú nâng cấp](../changelog.md#340-2026-11-21).

## Những gì thay đổi ở 3.5 { #what-changes-at-35 }

gin 3.5 không cần bước cấu hình nào. Cập nhật gin trên mỗi máy; chỉ nâng `.ginrc` khi project cần 3.5.

- Kết quả gin-qa đầu tiên ghi bằng 3.5 tạo thư mục `runs` cạnh thư mục case (`qa/runs` theo mặc định) và thêm một dòng `merge=union` vào `.gitattributes`. Commit cả hai cùng các case file. Xem [lịch sử chạy](qa.md#run-history).
- `gin attach` cần Beads và chạy với store `git-ref` mà không cần cấu hình nào khác. Mục [`attachments`](../reference/config.md#attachments) (tùy chọn) chọn store khác; store `s3` cần `python3 -m pip install boto3`.
- Một track bead do orchestrate tạo trước 3.5 có thể mang label `export:` của epic, khi đó `bd ship <capability>` từ chối. Gỡ label khỏi track bằng `gin task update <track> --remove-label export:<capability>`.

Nhật ký thay đổi liệt kê phần còn lại trong [ghi chú nâng cấp](../changelog.md#350-2026-11-22).
