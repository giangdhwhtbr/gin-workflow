# Hướng dẫn Gin Workflow v2.1

`gin-workflow` là plugin điều phối quy trình làm việc cho Claude Code,
Antigravity CLI và Codex CLI. Phiên bản 2.1 tách rõ cấu hình, kế hoạch,
trạng thái công việc và bằng chứng kiểm tra để quá trình từ yêu cầu đến bàn
giao có thể kiểm chứng và khôi phục.

## Quy trình chuẩn

Thực hiện các giai đoạn theo thứ tự sau:

1. **Thảo luận yêu cầu (`discuss`)**: làm rõ mục tiêu, phạm vi, rủi ro và
   tiêu chí chấp nhận; chờ người dùng xác nhận cách hiểu.
2. **Tạo kế hoạch (`plan`)**: ghi kế hoạch đã duyệt vào
   `.planning/plans/`.
3. **Điều phối (`orchestrate`)**: chuyển từng track trong kế hoạch thành
   Bead, thiết lập phụ thuộc và thứ tự thực thi.
4. **Thực thi (`execute`)**: worker làm việc trong worktree riêng, cập nhật
   trạng thái Beads và trả về kết quả theo hợp đồng chuẩn.
5. **Kiểm tra (`verify`)**: chạy test, review và kiểm tra repository; chỉ
   chấp nhận khi đủ bằng chứng cho mọi nhóm bắt buộc.
6. **Bàn giao (`ship`)**: hoàn tất handoff, cập nhật Beads và chuẩn bị thay
   đổi cho việc tích hợp.

Có thể dùng `workflow` để hệ thống tự chọn đúng giai đoạn kế tiếp. Các lệnh
chỉ là alias tùy host; các skill nêu trên là giao diện chính.

## Khởi tạo repository

Cài plugin chỉ cung cấp CLI và skill, không tự sửa repository. Chạy setup một
cách tường minh:

```bash
gin-workflow setup init --repository /duong-dan/repository
gin-workflow setup status --repository /duong-dan/repository
```

`init` có tính idempotent. Khi cần thay đổi cấu hình, dùng `configure` với
phê duyệt rõ ràng; các lệnh đọc như `status`, `diff` và `doctor` không ghi
thay đổi.

Setup tạo:

- `.agent-workflow/generated/effective-config.yaml`
- `.agent-workflow/generated/config-provenance.yaml`

Lifecycle chỉ đọc `effective-config.yaml`. File portable chỉ chứa lựa chọn
capability, artifact, policy, model tier logic và `secret_ref`; không ghi
provider command, model provider hay credential dạng plain text.

Ba kênh phiên bản phải tương thích với bản 2.1:

- `schema_version: "2.1"`
- `workflow_version: "2.1"`
- `setup_cli_version: "2.1"`

## Trạng thái và quyền sở hữu dữ liệu

- **Beads** là nguồn sự thật cho task, phụ thuộc, claim, blocker, readiness và
  trạng thái đóng.
- **Plan** trong `.planning/plans/` là nguồn sự thật cho decomposition, phạm
  vi file và ý định kiểm tra.
- **Worktree, branch và runtime metadata** chỉ là dữ liệu tạm thời, có thể
  dựng lại hoặc xóa mà không làm mất trạng thái bền vững.
- **Evidence** và event log hỗ trợ audit/verification nhưng không thay thế
  Beads.

Không dùng checkbox trong plan hoặc sự tồn tại của worktree để kết luận task
đã hoàn tất. Dùng `progress` để xem trạng thái Beads và đề xuất công việc kế
tiếp.

## Worker và capability provider

Worker nhận context manifest đã giới hạn, policy isolation và result contract
đã định kiểu. Dispatcher chuẩn hóa lifecycle event, idempotency, retry,
timeout, cancellation và fallback. Worker native không khả dụng sẽ chuyển về
worker tuần tự khi policy cho phép; context bí mật hoặc parent context không
được truyền sang payload worker.

Capability provider (task tracking, knowledge, workspace, review, evidence và
notification) được chọn trong effective config. Provider chỉ thực hiện đúng
hợp đồng capability; không tự điều phối lifecycle hay thay đổi Beads ngoài
quyền được cấp.

## Kiểm tra và bàn giao

Trước khi đóng công việc:

```bash
python3 -m unittest discover -s tests/workflow_core -p 'test_*.py' -v
python3 -m unittest discover -s tests/workflow_providers -p 'test_*.py' -v
python3 -m unittest discover -s tests/review_ledger -p 'test_*.py' -v
bash tests/install_smoke_test.sh
git diff --check
git status --short
```

Installer smoke kiểm tra layout cho cả Claude Code, Codex và Antigravity.
Evidence phải có kết quả đạt cho test, review và repository trước khi route
đến `ship`. Nếu một nhóm thiếu hoặc thất bại, workflow dừng ở `verify`.

## Tài liệu tham chiếu

- [Agent task lifecycle](agent-task-lifecycle.md)
- [Orchestration state model](orchestration-state-model.md)
- [Setup system](setup-system.md)
- [Capability provider contracts](capability-provider-contracts.md)
- [Context and evidence policy](context-and-evidence-policy.md)
- [Verification and handoff workflow](verification-and-handoff-workflow.md)
