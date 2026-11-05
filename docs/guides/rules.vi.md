# Rule pack { #rule-packs }

Rule pack là các checklist ngắn mà agent tuân theo khi viết code và reviewer kiểm tra khi review. `gin-workflow rules --files <paths>` chọn các pack áp dụng cho các file trong phạm vi; `execute` đưa đầu ra cho agent `developer`, `/quick` làm theo nó, và `review` đưa nó vào làm checklist của reviewer.

## Các pack { #packs }

| Pack | Tier | Áp dụng cho | Được bật |
|---|---|---|---|
| `core` | core | mọi file | luôn luôn, trừ khi bị tắt |
| `lean` | core | mọi file | luôn luôn, trừ khi bị tắt |
| `docs` | core | `*.md` | luôn luôn, trừ khi bị tắt; nạp khi một file Markdown nằm trong phạm vi |
| `typescript` | language | `*.ts`, `*.tsx`, `*.mts`, `*.cts` | qua `rules.packs` |
| `python` | language | `*.py` | qua `rules.packs` |
| `react` | framework (cần `typescript`) | `*.tsx`, `*.jsx` | qua `rules.packs` |
| `nextjs` | framework (cần `react`) | `app/`, `pages/`, `middleware.ts` | qua `rules.packs` |
| `node-api` | framework | `*.ts`, `*.js` và các biến thể | qua `rules.packs` |
| `fastapi` | framework (cần `python`) | `*.py` | qua `rules.packs` |

Setup đề xuất các pack language và framework từ những gì nó phát hiện (dependency, `tsconfig.json`, `pyproject.toml`). `core` bao gồm phạm vi, secret, xử lý lỗi, kiểm tra đầu vào, test hành vi, tái sử dụng, đặt tên, và hàm đơn mục đích. `lean` yêu cầu lời giải đúng ngắn nhất. Nó nói hãy tái sử dụng những gì đã có, ưu tiên thư viện chuẩn, nền tảng, và các dependency đã cài, và không thêm gì mang tính suy đoán. Nó không bao giờ cho phép cắt bỏ validation, xử lý lỗi, bảo mật, accessibility, hay các test cần thiết. Ý tưởng của nó đến từ [ponytail](https://github.com/dietrichgebert/ponytail) (MIT). `docs` kiểm tra rằng Markdown khớp với code, gọi những thực hành mà code không cưỡng chế là quy ước, và giữ mỗi sự kiện trên một trang. Nó cũng kiểm tra văn phong: heading viết hoa kiểu câu, câu ngắn, và không có dấu gạch ngang, mục danh sách mở đầu bằng nhãn in đậm, hay emoji. Ý tưởng của nó đến từ [technical-writer](https://github.com/riekelt/technical-writer) (MIT).

## Cấu hình { #configure }

```yaml
rules:
  packs: [typescript, react]   # add packs
  disabled: [lean]             # turn a pack off, including core, lean, or docs
```

Các pack riêng của dự án nằm ở `.agent-workflow/rules/<id>.md` và được ưu tiên hơn pack của plugin. `gin-workflow rules --list` hiển thị mọi pack đang bật cùng kích thước và số rule của chúng.

## Định dạng { #format }

Một pack là Markdown có frontmatter (`id`, `tier`, các glob `applies_to`, tùy chọn `requires`, `detect`, `tool_checks`) và một bullet cho mỗi rule:

```markdown
- [critical] `scope`: Change only files in the task scope; report needed changes elsewhere instead of making them.
```

- Mức tác động là `critical`, `high`, hoặc `medium` (mặc định). Anchor ổn định, và phát hiện trích dẫn chúng dưới dạng `<pack>#<anchor>`.
- Chỉ các bullet trước `## Why` được đưa vào; `## Why` giải thích từng rule trong một dòng và không bao giờ được gửi đi.
- Rule chỉ bao gồm những gì linter và type checker không cưỡng chế được. Các rule cưỡng chế được nằm trong `tool_checks`, mà setup báo cáo dưới dạng cấu hình lint hoặc type được đề xuất (setup không bao giờ sửa các config đó).
- Phần thân pack giữ dưới 1.500 ký tự (`core` và `lean` dưới 1.000).

## Độ ưu tiên và ngân sách { #precedence-and-budget }

Pack của dự án thắng framework, rồi language, rồi core. Các rule cho một task bị giới hạn ở 4.000 ký tự: vượt giới hạn, các bullet `medium` rồi `high` bị cắt bớt, bắt đầu từ độ ưu tiên thấp nhất. Rule `critical` không bao giờ bị cắt.

## Review chấm điểm phát hiện thế nào { #how-review-grades-findings }

Reviewer kiểm tra các rule `critical` và `high` trước và trích dẫn vi phạm dưới dạng `<pack>#<anchor>`. Một vi phạm `critical` được ghi ở mức `IMPORTANT` trở lên. Các phát hiện `lean` được chấm theo mức tác động: một rule lean `high` ở `IMPORTANT`, các rule khác ở `MINOR`; phát hiện nêu rõ cần cắt gì và thay bằng gì. Một sự đơn giản hóa được đánh dấu bằng comment `simplified:` (nêu giới hạn và đường nâng cấp của nó) thì không bị gắn cờ.

## Bảo trì các pack { #maintaining-packs }

Thêm một rule khi cùng một sự chỉnh sửa đã cần hơn hai lần; xóa nó khi công cụ đã cưỡng chế nó hoặc nó đã lỗi thời, và nêu tên phần thay thế trong commit message.
