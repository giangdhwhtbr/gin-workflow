# Công cụ khuyến nghị { #recommended-tools }

gin-workflow chạy chỉ với [các dependency bắt buộc](https://github.com/giangdhwhtbr/gin-workflow/blob/master/README.md#dependencies). Các công cụ dưới đây là tùy chọn, và mỗi phần của workflow đều có phương án dự phòng khi không có chúng.

## CodeGraph { #codegraph }

[CodeGraph](https://github.com/colbymchenry/codegraph) lập chỉ mục một repository thành một đồ thị cục bộ gồm symbol, call edge, và file. Một lệnh `codegraph explore "<symbols or question>"` trả về mã nguồn liên quan và các đường gọi giữa chúng, thay cho vòng lặp grep và đọc file. Các agent của gin-workflow dùng nó khi repository có chỉ mục `.codegraph/` và dự phòng bằng grep và đọc file trong các trường hợp khác.

### Cài đặt { #install }

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
# Windows (PowerShell)
irm https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.ps1 | iex
# or, with Node
npm i -g @colbymchenry/codegraph
```

Kiểm tra bằng `codegraph --version`.

### Cấu hình { #configure }

- Lập chỉ mục mỗi repository một lần bằng `codegraph init` ở gốc của nó. Trên repository brownfield hoặc legacy, `/gin:setup` đề nghị chạy giúp bạn. Chỉ mục nằm trong `.codegraph/`. Thêm `.codegraph/` vào `.gitignore` của repository; nếu không, git sẽ liệt kê thư mục này là chưa được theo dõi.
- Tùy chọn, `codegraph install` thêm các MCP tool của CodeGraph vào Claude Code, Codex, và các agent khác được hỗ trợ; một lần chạy toàn cục bao phủ mọi dự án. Các skill của gin-workflow gọi CLI `codegraph`, nên MCP server không bắt buộc. Nó thêm một file watcher giữ chỉ mục luôn mới trong khi bạn chỉnh sửa.

### gin-workflow dùng nó ở đâu { #where-gin-workflow-uses-it }

| Ở đâu | Cách dùng |
|---|---|
| Mọi stage của vòng đời | tra cứu symbol, test, và knowledge bằng `codegraph explore` trước khi grep |
| Các agent `agent-researcher`, `developer`, `docs-writer` | tra cứu code liên quan bằng `codegraph explore` |
| Agent `code-reviewer` | tra cứu caller; chạy `codegraph impact` / `codegraph callers` trên các public symbol đã đổi |
| `/gin:tech-doc` | `codegraph files` cho cấu trúc, `codegraph explore` cho các subsystem |
| `/gin:setup` | đề nghị `codegraph init`, hoặc gợi ý cài CodeGraph |
| `gin setup doctor` | báo CodeGraph đã được cài chưa và chỉ mục có cũ hơn `HEAD` không (khi đó chạy `codegraph sync`) |

### Hạn chế đã biết: worktree { #known-limitation-worktrees }

Một git worktree không có `.codegraph/` riêng, nên các agent làm việc trong đó dự phòng bằng grep và đọc file. Chỉ mục của main checkout không được dùng ở đó vì nó phản ánh một branch khác. Để dùng CodeGraph trong một worktree, chạy `codegraph init` bên trong nó, và `codegraph uninit -f` trước khi xóa worktree: một `.codegraph/` chưa được theo dõi làm `git worktree remove` thất bại.

## Các công cụ tùy chọn khác { #other-optional-tools }

| Công cụ | Dùng cho | Cách thiết lập |
|---|---|---|
| Codex CLI (`codex`), Antigravity CLI (`agy`), hoặc OpenCode (`opencode`) bên cạnh main harness của bạn | worker routing, với extension gin-orchestrator (nó gửi các track tới harness khác) | cài CLI và `./install.sh --plugin gin-orchestrator`, rồi chạy `/gin-orchestrator:providers` |
| GitHub CLI (`gh`) hoặc GitLab CLI (`glab`) | [chế độ team](team.md) | trình quản lý gói của bạn, rồi `gh auth login` hoặc `glab auth login` |
| Node với `@playwright/test` 1.49 trở lên | [spec end-to-end của QA](qa.md) | `npm i -D @playwright/test` và `npx playwright install` trong repository ứng dụng |
