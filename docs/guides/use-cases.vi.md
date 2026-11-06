# Các tình huống sử dụng { #use-cases }

Bốn tình huống thường gặp và đường đi qua workflow cho từng tình huống. Lệnh được viết dưới dạng slash command của Claude Code (`/gin:<skill>`); Codex dùng `$gin:<skill>`.

## Thay đổi nhỏ { #small-change }

Một lỗi chính tả, một thay đổi nội dung chữ, một bản sửa một file có test rõ ràng.

1. `/gin:quick <what to change>`: agent diễn đạt lại thay đổi trong vài dòng và chờ bạn xác nhận.
2. Nó chạy `gin quick-check` với ước tính số file và module của mình. `escalate` nghĩa là thay đổi vượt giới hạn của quick; hãy dùng vòng đời đầy đủ (bên dưới). `refused` chỉ xuất hiện ở mức rigor `strict`: dùng vòng đời đầy đủ, hoặc miễn `requirement_confirmed` bằng `gin unblock` để dùng `/quick`.
3. Nó triển khai (test trước khi hành vi thay đổi), chạy các verify command theo rigor của bạn, review (tự kiểm tra ở mức `easy`, review độc lập ở các mức khác), rồi ghi `quick-completed`.
4. Bạn xem diff và commit.

Nếu thay đổi lớn hơn ước tính, agent chạy lại `quick-check` và dừng khi gặp `escalate`.

## Lỗi có phạm vi hẹp { #bounded-defect }

Một bug tái hiện được mà bản sửa nên giữ hẹp.

1. `/gin:discuss`: xác nhận triệu chứng, hành vi mong đợi, và những gì nằm ngoài phạm vi.
2. Chẩn đoán bằng skill `debugging`: tái hiện, tìm nguyên nhân gốc, và dừng nếu chưa cô lập được. Đừng đoán plan.
3. `/gin:plan`: một track với regression test fail trước khi sửa.
4. `/gin:orchestrate`, rồi `/gin:execute`: regression chuyển đỏ, bản sửa đưa nó về xanh, review phê duyệt, track đóng.
5. `/gin:ship`.

Nếu chẩn đoán làm phạm vi rộng ra, quay lại `discuss`; đừng bao giờ mở rộng bản vá một cách âm thầm. Một bản sửa đủ nhỏ có thể dùng đường quick thay thế.

## Thay đổi lớn nhiều track { #large-multi-track-change }

Một tính năng hoặc migration được tách thành các track phụ thuộc nhau, ví dụ xuất CSV: (A) schema và quyền, (B) exporter streaming phụ thuộc A, (C) giao diện tải xuống phụ thuộc B.

1. `/gin:discuss` tạo ra spec đã được xác nhận.
2. `/gin:plan` cho mỗi track danh sách file, interface, các bước test trước, một provider role (`backend` cho A và B, `frontend` cho C), cùng model và effort lấy từ model catalog kèm lý do chọn.
3. `/gin:orchestrate` tạo epic và ba task track, rồi resolve mọi route và chỉ ghi assignment manifest khi tất cả track đều resolve được. Sau đó nó thêm các dependency và tạo worktree.
4. `/gin:execute` cho từng track sẵn sàng, mỗi track chạy trong một subagent `gin:developer` với model và effort của track: A trước; đóng A làm B sẵn sàng, và cứ thế tiếp tục. Mỗi track được review độc lập trước khi đóng.
5. `/gin:ship` kiểm tra mọi ledger và mọi thay đổi sau review (các cổng chất lượng đã chạy trong git hook), rồi merge hoặc mở pull request khi bạn phê duyệt.

Route sang các harness khác cần extension [gin-orchestrator](../orchestrator/README.md); không có nó, mọi track chạy trên main harness. Nếu một route không khả dụng, task vẫn mở; một fallback harness chạy route được ánh xạ theo rank vào catalog của chính nó. Nếu việc resolve route báo một role chưa được resolve, hoặc một model hay effort nằm ngoài catalog, nó không ghi manifest cho tới khi plan hoặc cấu hình được sửa; các bead vẫn còn.

## Tiếp tục công việc đang dở { #resume-in-progress-work }

Một session, provider, hoặc máy đã dừng trước khi công việc tới trạng thái kết thúc.

1. `/gin:progress` đọc trạng thái bền vững: trạng thái bead, mức sẵn sàng, blocker, waiver, trạng thái review, và các lần chạy quick gần đây. Một worktree hay branch còn sót lại không phải bằng chứng của tiến độ.
2. Nếu review của một track đang chờ, hoàn tất review trước (skill `review`): reviewer lấy một lease mới, kiểm tra snapshot hiện tại, và ghi lại phát hiện hoặc phê duyệt.
3. `/gin:workflow` định tuyến tới đúng một stage. Khi mọi track đã đóng, nó chọn `ship`, stage này fail closed khi một ledger thiếu phê duyệt cuối.
4. Tiếp tục từ stage mà nó nêu tên.

Khi trạng thái bị giữ lại, `gin state` liệt kê các cách khắc phục: gỡ một blocker, miễn một process gate kèm lý do, hoặc sửa cấu hình còn thiếu qua `/setup`. Một worktree hoặc runtime cache còn sót lại là [runtime metadata](../concepts/state-model.md#runtime-metadata), không phải state, nên đừng dùng chúng để đánh dấu công việc là xong.
