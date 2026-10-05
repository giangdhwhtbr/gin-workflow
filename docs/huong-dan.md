# Hướng dẫn nhanh

Trang này đi qua một tính năng nhỏ, từ ý tưởng đến lúc merge. Bản tiếng Anh, có thêm chi tiết, nằm ở [Getting started](getting-started.md). Lệnh trong trang viết theo dạng slash command của Claude Code; trên Codex dùng `$gin-workflow:<skill>`.

## 1. Chuẩn bị

- Python 3 kèm PyYAML, git và [Beads](https://github.com/gastownhall/beads) (`bd`), cài theo bảng [Installation](../README.md#1-dependencies); Beads đã khởi tạo trong repository bằng `bd init`.
- Plugin và lệnh `gin-workflow` đã được cài ([Installation](../README.md#installation)). Kiểm tra bằng `gin-workflow --version`.

## 2. Thiết lập repository (một lần)

```
/gin-workflow:setup
```

Setup tự nhận diện dự án (giai đoạn, loại dự án, stack, các lệnh kiểm tra), rồi hỏi lần lượt từng câu:

- loại dự án;
- mức rigor: `easy`, `standard` hoặc `strict`;
- chế độ provider: `single` (chỉ dùng một harness) hoặc `multi` (chuyển việc sang các CLI khác);
- các lệnh lint, typecheck, test, build, e2e.

Setup trình cấu hình đề xuất và chờ bạn duyệt. Sau đó nó ghi `.agent-workflow/config.yaml` (bạn commit file này) cùng các file cục bộ đã được gitignore. Xem [Configuration](reference/config.md).

## 3. Thảo luận (`discuss`)

```
/gin-workflow:discuss Thêm cột "lần đăng nhập cuối" vào danh sách người dùng
```

Agent đọc phần code liên quan, hỏi lần lượt từng câu để làm rõ, đề xuất 2–3 hướng kèm khuyến nghị, rồi trình bày thiết kế theo từng phần để bạn xác nhận. Thiết kế được ghi vào `.planning/specs/<ngày>-<chủ-đề>-design.md` trên nhánh feature. Khi bạn xác nhận spec, agent ghi gate `requirement-confirmed`. Trước bước này, agent không lập kế hoạch và không viết code.

## 4. Lập kế hoạch (`plan`)

```
/gin-workflow:plan last-login-column
```

Plan nằm trong `.planning/plans/` và chia công việc thành các track. Mỗi track ghi rõ file, interface, các bước test trước, provider role và mức reasoning. Bạn duyệt plan thì agent ghi gate `plan-approved`.

## 5. Điều phối (`orchestrate`)

```
/gin-workflow:orchestrate last-login-column
```

Bước này làm các việc sau:

1. Chọn provider cho từng track.
2. Tạo epic, mỗi track một bead, và quan hệ phụ thuộc giữa các bead.
3. Tạo worktree trong `.planning/worktrees/` và kiểm tra test chạy được trong đó.
4. Ghi gate `orchestration-ready`.

## 6. Thực thi (`execute`)

```
/gin-workflow:execute
```

Với mỗi track đã sẵn sàng, agent nhận bead, viết test fail trước, rồi code cho đến khi test pass. Sau đó một reviewer độc lập (provider khác, hoặc một phiên mới) review diff và ghi kết quả vào review ledger. Agent sửa hoặc phản hồi từng finding. Khi review được duyệt, agent thu thập usage AI rồi đóng bead, và track kế tiếp trở nên sẵn sàng. Chạy lại lệnh cho track tiếp theo. Nhánh được push lên remote, chưa merge gì.

## 7. Kiểm tra (`verify`)

```
/gin-workflow:verify
```

Bước này chỉ chấp nhận bằng chứng vừa chạy:

- mọi review ledger đều hợp lệ;
- các lệnh kiểm tra theo mức rigor đều pass;
- từng dòng của spec và plan đã được đối chiếu với code.

Đủ cả ba thì agent ghi gate `verification-passed`.

## 8. Bàn giao (`ship`)

```
/gin-workflow:ship
```

Có bốn lựa chọn: merge cục bộ, push và tạo pull request, giữ nguyên nhánh, hoặc bỏ thay đổi. Merge và tạo pull request đều cần bạn cho phép rõ ràng. Sau khi merge, agent:

1. chạy lại test trên kết quả merge;
2. xóa worktree và nhánh;
3. thu thập usage của epic;
4. đóng epic, tức là đánh dấu đã ship;
5. liệt kê các việc đã sẵn sàng tiếp theo.

## Lối tắt và trạng thái

- `/gin-workflow:workflow`: đọc trạng thái và chạy stage kế tiếp.
- `/gin-workflow:quick <thay đổi>`: thay đổi nhỏ, ít rủi ro, không cần spec, plan hay bead ([use cases](guides/use-cases.md#small-change)).
- `/gin-workflow:progress`: xem việc đã sẵn sàng, đang làm và đang bị chặn. Khi workflow bị giữ lại, `gin-workflow state` cho biết lý do và cách gỡ.
- `/gin-workflow:report --epic <epic>`: xem chi phí AI theo model và theo stage, cùng các tín hiệu review và làm lại ([usage report](guides/usage-report.md)).

## Đọc thêm

- [Architecture](concepts/architecture.md): các thành phần ghép với nhau thế nào, có sơ đồ.
- [Lifecycle](concepts/lifecycle.md): gate, waiver, kiểm tra và bàn giao.
- Tính năng tùy chọn: [rule packs](guides/rules.md), [SDD living specs](guides/sdd.md), [team mode](guides/team.md), [QA add-on](guides/qa.md).
- Tra cứu: [skills](reference/skills.md), [CLI](reference/cli.md).
