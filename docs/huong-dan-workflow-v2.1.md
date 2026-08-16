# Hướng dẫn Gin Workflow v2.2

`gin-workflow` là plugin điều phối quy trình làm việc cho Claude Code,
Antigravity CLI và Codex CLI. Phiên bản 2.2 tách rõ cấu hình, kế hoạch,
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

## Thiết lập repository một lần

Cài plugin chỉ cung cấp CLI và skill, không tự sửa repository. Chạy `/setup`
một lần trước phiên `discuss` đầu tiên. Setup phát hiện harness, thu thập cấu
hình portable, hiển thị dry-run, xin phê duyệt rồi tạo cấu hình ban đầu trong
một thao tác atomic. Setup không phải là một giai đoạn của lifecycle.

Có thể gọi CLI tương đương:

```bash
gin-workflow setup init --repository /duong-dan/repository \
  --harness codex --set policy.mode=guarded --approve
gin-workflow setup status --repository /duong-dan/repository
```

`init` có tính idempotent. Workflow bình thường chỉ đọc effective config đã
tạo và không tự chạy lại setup. Nếu effective config chưa tồn tại, lifecycle
dừng và yêu cầu chạy `/setup` một lần. Sau đó chỉ gọi lại setup khi chủ động
bảo trì, ví dụ `status`, `doctor`, `configure`, `update` hoặc `rollback`.

Setup tạo:

- `.agent-workflow/generated/effective-config.yaml`
- `.agent-workflow/generated/config-provenance.yaml`

Lifecycle chỉ đọc `effective-config.yaml`. File portable chỉ chứa lựa chọn
capability, artifact, policy, model tier logic và `secret_ref`; không ghi
provider command, model provider hay credential dạng plain text.

Ba kênh phiên bản phải tương thích với bản 2.2:

- `schema_version: "2.2"`
- `workflow_version: "2.2"`
- `setup_cli_version: "2.2"`

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

## Điều phối Claude, Codex và Antigravity

Plan gán mỗi track bằng `provider_role` và mức suy luận `low`, `medium` hoặc
`high`; plan không ghi tên model cụ thể. Khi orchestrate, workflow đọc role từ
`.agent-workflow/config.yaml`, rồi tra model tương ứng trong file local đã
gitignore `.agent-workflow/providers.local.yaml`. Ví dụ role `backend` có thể
ưu tiên Claude, role `frontend` ưu tiên Antigravity, còn role `review` ưu tiên
`main_harness` là Codex đang mở dự án.

Nếu Claude/Opus hết quota, circuit breaker chỉ mở cho đúng cặp Claude/Opus.
Router thử fallback của cùng mức `high`, ví dụ Codex/model reasoning; không tự
hạ xuống model `medium`. Nếu CLI không chứng minh được khả năng chọn model rõ
ràng, provider được xem là unavailable thay vì dùng model mặc định. Khi mọi
route đều lỗi hoặc hết capacity, task giữ trạng thái mở với blocker
`worker_routes_unavailable`.

`/setup` hỏi lần lượt chín nhóm: main harness, provider được bật, role ưu tiên,
mapping model low/medium/high, fallback, concurrency, queue/timeout/retry,
circuit breaker và review độc lập. Dry-run phải hiển thị cả config portable lẫn
config provider local trước khi xin duyệt. Xem cấu hình đầy đủ và giải thích chi
tiết tại [provider-routing.md](provider-routing.md).

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
