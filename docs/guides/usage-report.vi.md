# Báo cáo mức sử dụng AI { #ai-usage-report }

`gin usage` báo cáo công việc AI trên một bead hoặc một epic tốn bao nhiêu và diễn ra thế nào. Nó đọc các log harness có sẵn trên máy đã làm việc và hiển thị token cùng chi phí ước tính theo từng model và từng stage của vòng đời, bên cạnh các tín hiệu chất lượng. Nó chỉ đọc file cục bộ và cần Beads.

## Những gì được đo { #what-is-measured }

| Nguồn | Đọc từ | Ghi chú |
|---|---|---|
| Claude Code | `~/.claude/projects/<repo slug>*/**/*.jsonl` | gồm cả subagent; mỗi message được đếm một lần |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | usage theo từng lượt |
| Antigravity | không được đo | chưa có reader |
| OpenCode | không được đo | chưa có reader |

`CLAUDE_CONFIG_DIR` và `CODEX_HOME` ghi đè vị trí của log. Chỉ các con số và trường định tuyến được đọc (model, số token, thời gian, thư mục làm việc, branch); văn bản prompt và response không bao giờ được đọc hay lưu. Thư mục log bị thiếu hiển thị là `not_found`, và các dòng không đọc được được đếm trong `skipped_lines`.

Các tín hiệu chất lượng đến từ Beads và review ledger:

- `reopens`: số lần bead đi từ đóng trở lại mở;
- `bugs`: các bug được tạo với liên kết `discovered-from` tới bead;
- `review_cycles`, `rejections`, và `findings` theo mức độ nghiêm trọng, từ review ledger của bead;
- `waivers`: các gate bị miễn trong workflow của bead.

## Khi nào nó chạy { #when-it-runs }

`execute` chạy `gin usage collect --bead <epic> --best-effort` sau mỗi lần worker trả về và `--bead <track>` trước khi đóng từng track, và `ship` chạy nó cho epic trước khi đóng. Bạn có thể tự chạy bất cứ lúc nào, từ main checkout hoặc bất kỳ worktree nào của nó; nó tính lại bản tóm tắt từ đầu, nên chạy hai lần cho cùng một kết quả. Với `--best-effort`, một lỗi trở thành cảnh báo và không bao giờ chặn việc đóng một bead.

## Mức sử dụng được quy cho ai { #how-usage-is-attributed }

1. Công việc trong một worktree của repository được quy cho track bead có khoảng thời gian từ claim tới close chứa nó: stage `review` khi review ledger của bead cho thấy một review đang diễn ra, còn lại là `execute`.
2. Công việc ở gốc repository được quy cho workflow của gate kế tiếp được ghi sau nó, với stage của gate đó: `discuss` trước `requirement-confirmed`, `plan` trước `plan-approved`, `orchestrate`, `verify`, `quick`, hoặc `ship`.
3. Khi bạn collect một epic, công việc ở gốc sau khi track cuối của nó đóng và trước khi epic đóng được tính là `ship` của epic đó, miễn là không có workflow nào khác ghi một gate sau khi track đó đóng.
4. Mọi thứ còn lại là `unattributed`; việc collect một epic cũng lưu mức sử dụng unattributed nằm trong khoảng thời gian của nó để báo cáo hiển thị.

Bản tóm tắt được lưu trong metadata của bead dưới tên `ai_usage` (chỉ số tổng hợp), và bản tóm tắt của một epic cũng tổng hợp các track của nó.

## Giá { #prices }

Chi phí là ước tính theo USD trên mỗi triệu token. Plugin đi kèm một catalog, `workflow_core/usage_prices_default.yaml`, được kiểm tra ngày 2026-11-01 với các trang của nhà cung cấp nêu trong từng dòng. Nó dùng giá tier chuẩn, cache write 5 phút của Anthropic, cache write của OpenAI bằng 1,25 lần input, và cache write của Google bằng 0 (Google tính phí lưu cache theo giờ).

`.agent-workflow/usage-prices.yaml` ghi đè một dòng catalog theo model id và thêm các model mà catalog thiếu. Commit file để nhóm dùng chung một danh sách là một quy ước của nhóm, không phải hành vi của công cụ:

```yaml
prices:
  <model id>: {input: 3.0, output: 15.0, cache_read: 0.3, cache_write: 3.75}
```

Một model id không có dòng khớp chính xác sẽ lấy dòng dài nhất mà khóa của nó được mở rộng bằng `-`: `claude-sonnet-4-5-20250929` được tính giá như `claude-sonnet-4-5`. Không có kiểu so khớp mờ nào khác.

Mỗi model trong báo cáo mang một `price_source`: `default` (catalog), `repo` (file của bạn) hoặc `none`. Một model có `none` không bao giờ bị đoán: chi phí của nó hiển thị `-` và nó được liệt kê dưới `unpriced`.

Giá thay đổi và catalog chỉ là sự tiện lợi, không phải nguồn tính tiền.

## Ngân sách { #budget }

Đặt `usage.budget_usd` trong `.agent-workflow/config.yaml` để cho mỗi epic một trần chi tiêu tính bằng USD:

```yaml
usage:
  budget_usd: 25
```

`usage collect --bead <epic>` khi đó lưu `budget: {budget_usd, cost, status}` vào bản tóm tắt của epic và in trạng thái:

| Trạng thái | Khi nào |
|---|---|
| `ok` | chi phí dưới 80% ngân sách |
| `warn` | chi phí từ 80% tới 120% |
| `stop` | chi phí bằng hoặc vượt 120%; biên này bù cho sai số của việc quy theo khoảng thời gian |
| `unenforceable` | một model đã dùng không có giá; đầu ra nêu các model và `.agent-workflow/usage-prices.yaml` |

Bản tóm tắt của một track không có khối budget; ngân sách thuộc về epic.

Ở `stop`, `gin routes dispatch` cho epic in `{"status": "over_budget", ...}`, không dispatch gì, và thoát với mã 3. Nâng `usage.budget_usd` cho phép lần dispatch kế tiếp tiến hành mà không cần collect lại. `unenforceable` không bao giờ dừng một lần dispatch.

## Đọc báo cáo { #reading-it }

```bash
gin usage report --epic <epic>
gin usage report --since 2026-10-01 --format json
```

Hoặc hỏi `/report`. Báo cáo văn bản liệt kê chi phí của từng bead, tổng theo model (token theo loại) và theo stage, các model chưa có giá, mức sử dụng unattributed, và các bead đã đóng nhưng chưa bao giờ được collect (`not collected`). `--format json` trả về đầy đủ các bản tóm tắt cho công cụ của riêng bạn.

Khi các tổng số chỉ mang tính một phần, báo cáo văn bản thêm dòng `partial: <reasons>` sau dòng tổng số, và JSON thêm `partial` cùng `partial_reasons`:

- `children_not_merged`: một epic và một child trực tiếp đều có bản tóm tắt;
- `not_collected`: một bead trong phạm vi chưa có bản tóm tắt;
- `unattributed`: số token unattributed lớn hơn không;
- `log_sources`: một lượt quét log không sạch hoặc bỏ qua các dòng không đọc được;
- `stale`: một epic được thu thập trước thời điểm đóng mới nhất của các child trực tiếp;
- `unpriced`: một model trong phạm vi thiếu giá.

## Giới hạn { #limits }

- Công việc trên Antigravity và OpenCode không được đếm.
- Hai session cùng làm việc ở gốc repository cùng lúc không thể phân biệt: công việc ở gốc được quy cho gate kế tiếp, kể cả khi session kia ghi nó.
- Stage `review` bao trùm toàn bộ thời gian một review được mở, kể cả thời gian người triển khai làm việc khác trong lúc chờ.
- Các session có thư mục làm việc nằm ngoài repository và các worktree của nó không được đếm.

Xem [`gin usage`](../reference/cli.md#gin-usage) cho các tùy chọn và exit code.
