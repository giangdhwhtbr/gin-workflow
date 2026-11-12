# Thoả thuận git của team { #team-git-agreement }

## Mục đích và phạm vi { #purpose-and-scope }

Thoả thuận này quy định cách team tạo branch, commit, mở pull request, review, approve và merge công việc. Thoả thuận ràng buộc mọi thành viên của dự án đã bật [chế độ nhóm](team.md). Chế độ nhóm mô tả cách vận hành; trang này nêu các quy tắc.

Trong thoả thuận này, PHẢI đánh dấu một nghĩa vụ và PHẢI KHÔNG đánh dấu một điều cấm. Thành viên vi phạm một trong hai là chưa đáp ứng thoả thuận. Những câu không có hai cụm này mô tả mặc định khuyến nghị mà team có thể đổi.

Không cần biết git để tuân theo thoả thuận. Mục Quy trình theo từng host nêu các bước trên host đang dùng, và phần phụ lục có các prompt nhờ AI agent làm phần việc git.

## Thuật ngữ { #terms }

- Branch: một nhánh công việc, tách khỏi nhánh chính cho đến khi được merge.
- Base branch: branch mà team giữ làm trạng thái đã thống nhất của dự án, thường là `main` hoặc `master`.
- Commit: một tập thay đổi đã được lưu, kèm message nói rõ thay đổi gì.
- Pull request: yêu cầu merge một branch vào base branch, kèm một trang để review. GitLab gọi là merge request.
- Review: đọc các thay đổi trong pull request và nhận xét về chúng.
- Approve: đánh dấu pull request là chấp nhận được để merge.
- Request changes: đánh dấu pull request là chưa chấp nhận được cho đến khi tác giả sửa.
- Merge: đưa các thay đổi của một branch vào base branch.
- Conflict: hai branch cùng sửa những dòng giống nhau, nên host không merge được nếu không có người chọn.
- Gate: một điểm kiểm tra mà gin ghi nhận sau khi đúng người đã approve pull request tương ứng.
- Approving role: vai trò được liệt kê cho một gate trong `team.approvals` của `.agent-workflow/config.yaml`.
- Track: một phần của plan, được giao bằng một pull request.
- Bead: một bản ghi công việc trong công cụ theo dõi task của dự án.
- CI: các kiểm tra tự động chạy trên mỗi pull request.
- Host: dịch vụ lưu repository và các pull request của nó: GitHub, GitLab, Gitea hoặc AWS CodeCommit.
- Roadmap: file liệt kê các epic mà team dự kiến giao.
- Epic: một khối công việc lớn trong công cụ theo dõi task, gồm nhiều track.
- Spec: file nêu công việc phải làm gì, theo ngôn ngữ nghiệp vụ.
- Requirement: một quy tắc trong spec mà công việc hoàn thành phải đáp ứng.
- User story: một câu ngắn nêu ai cần gì và vì sao, nằm trong spec.
- Acceptance criterion: một phép kiểm tra cho thấy requirement đã được đáp ứng.
- Plan: file chia spec thành các track và nêu ai làm từng track.
- Artifact: một roadmap, spec, plan hoặc track mà team review.
- Area: một phần của repository, có vai trò lead, sở hữu một số path.
- Owner: thành viên làm một track.
- Change folder: thư mục trong layout SDD chứa một thay đổi của các spec.
- Layout SDD: cấu trúc repository giữ living spec và change folder dưới `docs/`.
- Skill: một lệnh của AI agent chạy một stage của công việc.
- BA: business analyst, người viết và xác nhận spec.
- Developer: thành viên làm một track.
- Tester: thành viên kiểm tra công việc đáp ứng spec.
- Tech lead: thành viên viết plan và dẫn dắt các area.

## Branch { #branches }

Base branch được bảo vệ. Thành viên PHẢI KHÔNG commit trực tiếp vào base branch.

Mỗi phần việc PHẢI có branch riêng, và tên branch PHẢI cho thấy loại công việc.

| Loại công việc | Tên branch |
|---|---|
| Roadmap | `roadmap/<topic>` |
| Spec | `spec/<topic>`, hoặc `spec/<epic>-<slug>` với [layout SDD](sdd.md) |
| Plan | `plan/<topic>` |
| Track của plan | `feat/<topic>-t<N>`, trong đó `<N>` là số thứ tự track |
| Việc khác | `chore/<topic>` |

Một branch PHẢI chứa đúng một loại công việc. Spec và plan không dùng chung branch.

Thư mục asset không có branch riêng: thư mục đã xác nhận vào nhánh gốc cùng pull request của spec mà change folder trích dẫn nó ([hình ảnh và mockup](sdd.md#images-and-mockups)).

## Commit { #commits }

Mọi commit message PHẢI theo quy ước đặt trong `team.commit_convention`. Hook commit-msg do `gin team hooks` cài sẽ kiểm tra message khi commit, và CI kiểm tra lại trên pull request.

Với giá trị `conventional`, message có dạng `type(scope): subject`, ví dụ `docs(ba): add legacy edge cases`. Với giá trị `none`, message nào cũng được chấp nhận.

## Pull request { #pull-requests }

Mọi artifact có gate PHẢI vào base branch qua pull request. Các vai trò approve lấy từ `team.approvals` của dự án.

| Artifact | Branch | Người approve | Gate |
|---|---|---|---|
| Roadmap | `roadmap/<topic>` | các vai trò được liệt kê cho `roadmap` | `roadmap` |
| Spec | `spec/<topic>` | các vai trò được liệt kê cho `requirement_confirmed` | `requirement_confirmed` |
| Plan | `plan/<topic>` | các vai trò được liệt kê cho `plan_approved` | `plan_approved` |
| Track | `feat/<topic>-t<N>` | các vai trò được liệt kê cho `ship` | `ship` |
| Archive vào living spec | phần tích hợp của epic: merge feature branch, hoặc pull request của repository cha trong workspace | các vai trò được liệt kê cho `ship`; theo quy ước của nhóm, BA review phần diff của living spec | `ship` |

Tác giả PHẢI điền template pull request do `gin team init` ghi. Template có các trường sau:

- Summary: thay đổi gì và vì sao, trong hai hoặc ba câu.
- Plan: file plan, hoặc `none`.
- Tracks: các số track mà pull request giao, ví dụ `1,2`. Máy của các thành viên khác đọc trường này, nên phải ghi đúng định dạng.
- Spec: change folder hoặc file spec, và các requirement ID mà nó chạm tới.
- Beads: các bead ID.
- Tests: các lệnh đã chạy và kết quả.
- Checklist: commit theo quy ước, mỗi requirement thay đổi đều có test, và các comment review đã được xử lý.

## Review { #review }

Mỗi pull request PHẢI được review bởi một thành viên giữ approving role của gate đó. Mỗi người review PHẢI dùng checklist của vai trò mình bên dưới. Các checklist là quy tắc của chính thoả thuận này và là quy ước của team, team có thể đổi.

BA dùng checklist này trên các pull request spec do thành viên khác tạo.

Người duyệt một spec kiểm tra rằng:

- mỗi user story có acceptance criteria;
- mỗi requirement lấy từ một đầu vào có một dòng `Source:` nêu tên nó;
- các edge case của hệ thống cũ đã được phủ;
- mọi requirement đều test được: mỗi acceptance criterion nêu một kết quả quan sát được.

Team cũng có thể yêu cầu một review `qe` không chặn gate trên các pull request spec. CODEOWNERS trên các thư mục spec là cơ chế của host cho việc này; đây chỉ là gợi ý, gin không áp đặt.

BA không review pull request của track. BA nghiệm thu mỗi epic một lần, dựa trên báo cáo QA ([trong lúc build](ba.md#during-the-build)).

Tester review pull request của developer và kiểm tra rằng:

- mọi acceptance criterion trong spec đều được đáp ứng;
- bằng chứng test có trong trường Tests.

Tech lead review một plan và kiểm tra rằng:

- mỗi track có area và owner;
- các track không liệt kê cùng một file.

gin chỉ tự kiểm tra một phần. `gin team check-plan` kiểm tra area, owner và các path của plan, còn `gin specs lint` kiểm tra cấu trúc của spec. Phần còn lại tuỳ vào người review.

Để approve, mở pull request trên host và chọn Approve. Để request changes, comment vào các dòng liên quan và chọn Request changes. Mục Quy trình theo từng host nêu các bước.

Người review nên phản hồi trong vòng một ngày làm việc. Đây là quy ước mà team có thể đổi; gin không áp dụng quy ước này.

## Quy tắc approve và merge { #approval-and-merge-rules }

Thành viên PHẢI KHÔNG approve pull request của chính mình.

Một approval chỉ có giá trị trên commit mới nhất. Sau mỗi lần push, PHẢI có approval mới.

Thành viên PHẢI KHÔNG merge pull request khi chưa có đủ approval cần thiết hoặc khi CI chưa đạt.

Theo quy ước, tác giả merge và xoá branch sau khi merge. Đây là quy ước của team mà team có thể đổi; gin không áp dụng quy ước này.

## Phê duyệt gate { #gate-approval }

Gate được ghi từ một pull request đã approve. Skill của stage chạy lệnh; thành viên không tự gõ lệnh. Mỗi skill truyền URL của pull request làm bằng chứng.

| Gate | Trạng thái pull request | Do ai ghi |
|---|---|---|
| `roadmap` | Đã merge | Skill `roadmap` kiểm tra bằng `gin team check <url> --gate roadmap`; skill này không ghi gate |
| `requirement_confirmed` | Đã merge | Skill `discuss`, bằng `gin record requirement-confirmed --evidence <PR url>` |
| `plan_approved` | Đã merge | Skill `plan`, bằng `gin record plan-approved --evidence <PR url>` |
| `ship`, trước khi merge | Đang mở và đã approve trên commit mới nhất | Skill `ship` kiểm tra bằng `gin team check --gate ship <url>`; lệnh này không ghi gì |
| `ship`, sau khi merge | Đã merge | Skill `ship`, bằng `gin record shipped --evidence <PR url>`, chỉ cho bead độc lập |

Epic có bead con được ship khi bead epic đóng, nên không cần `gin record shipped`.

gin chỉ chấp nhận pull request khi mọi điều kiện sau đều đúng:

- pull request thuộc repository này và thay đổi artifact của gate; khi nó thay đổi nhiều spec hoặc plan, `--spec` hoặc `--plan` chọn một file;
- một thành viên có approving role đã approve, và người đó không phải tác giả;
- với `plan_approved`, `gin team check-plan` cũng phải đạt, và `area_lead` nghĩa là lead của area approve.

Khi gin từ chối pull request, gin liệt kê các approval còn thiếu. Thành viên PHẢI lấy các approval đó rồi nhờ skill chạy lại. Thành viên PHẢI KHÔNG thay bằng chứng khác hoặc xin miễn gate. [Chế độ nhóm](team.md#what-changes-in-each-stage) mô tả cơ chế chi tiết.

## Conflict và thay đổi sau khi approve { #conflicts-and-changes-after-approval }

Khi host báo conflict, tác giả PHẢI cập nhật branch từ base branch, giải quyết conflict và xin review lại. Approval trước đó không còn giá trị.

Thay đổi requirement sau khi plan được approve PHẢI nằm trong một change folder mới, không sửa spec đã approve. [Living spec SDD](sdd.md#changing-a-requirement-after-plan-approval) mô tả cách làm.

## Quy trình theo từng host { #host-procedures }

Chọn mục tương ứng với host. Các lệnh `gh`, `glab`, `gt`, và `aws` làm cùng việc với các bước trên web, và cần đăng nhập trên host. Các lệnh login là `gh auth login`, `glab auth login`, `gt auth login --host <instance URL>`, và `aws configure` hoặc `aws sso login`. [Thiết lập trên host](team.md#host-settings) của hướng dẫn team có thêm chi tiết.

### GitHub { #github }

1. Tạo: mở repository, chọn Pull requests, rồi New pull request. Đặt base là base branch và compare là branch của mình. Điền template và chọn Create pull request.
2. Review: mở pull request và chọn Files changed. Rê chuột lên một dòng, chọn dấu cộng, viết comment và chọn Start a review.
3. Approve: chọn Review changes, chọn Approve, rồi chọn Submit review.
4. Request changes: chọn Review changes, chọn Request changes, viết nội dung cần sửa, rồi chọn Submit review.
5. Merge: sau khi đủ approval cần thiết và các check đạt, chọn Merge pull request.
6. Xoá branch: chọn Delete branch trên pull request đã merge.

```bash
gh pr create --base <base-branch> --title "<title>" --body "<description>"
gh pr review --approve
gh pr review --request-changes -b "<comment>"
gh pr merge --delete-branch
```

### GitLab { #gitlab }

1. Tạo: mở project, chọn Merge requests, rồi New merge request. Chọn source branch và base branch làm target, điền template và chọn Create merge request.
2. Review: mở merge request và chọn Changes. Rê chuột lên một dòng, chọn biểu tượng comment và viết comment.
3. Approve: chọn Approve ở đầu merge request.
4. Request changes: nếu phiên bản GitLab có, chọn Request changes khi submit review. Nếu không, để lại một comment nêu rõ cần sửa gì.
5. Merge: sau khi đủ approval cần thiết và pipeline đạt, chọn Merge.
6. Xoá branch: giữ nguyên ô Delete source branch được chọn khi merge.

```bash
glab mr create --target-branch <base-branch> --title "<title>" --description "<description>"
glab mr approve
glab mr note -m "<comment>"
glab mr merge --remove-source-branch
```

Trên GitLab, project PHẢI bật Reset approvals on push, để approval chỉ có giá trị trên commit mới nhất.

### Gitea { #gitea }

1. Tạo: mở repository, chọn Pull requests, rồi New Pull Request. Đặt base branch và compare là branch của mình, điền template và chọn Create Pull Request.
2. Review: mở pull request và chọn Files Changed. Rê chuột lên một dòng, chọn biểu tượng comment, viết comment và chọn Start Review.
3. Approve: chọn Finish Review, chọn Approve, rồi chọn Submit Review.
4. Request changes: chọn Finish Review, chọn Request Changes, viết nội dung cần sửa, rồi chọn Submit Review.
5. Merge: sau khi đủ approval cần thiết và các check đạt, chọn nút merge.
6. Xoá branch: chọn Delete Branch trên pull request đã merge.

```bash
gt pr create --base <base-branch> --title "<title>" --body "<description>"
gt pr review <number> --approve
gt pr review <number> --request-changes --body "<comment>"
gt pr merge <number> --delete-branch
```

Trên Gitea, protected branch PHẢI yêu cầu approval và bật Dismiss stale approvals, để approval chỉ có giá trị trên commit mới nhất.

### AWS CodeCommit { #aws-codecommit }

1. Thiết lập một lần: trong AWS console, mở CodeCommit, rồi Approval rule templates, và tạo một template nêu các approving role và số approval cần có. Gắn template vào repository. [Chế độ team](team.md#aws-codecommit) nêu cùng các bước bằng `aws codecommit`.
2. Tạo: mở repository, chọn Pull requests, rồi Create pull request. Chọn destination branch và source branch của mình, rồi điền title và description.
3. Review: mở pull request và chọn Changes. Chọn một dòng để thêm comment.
4. Approve: chọn Approve. Để rút approval, chọn Revoke approval.
5. Request changes: để lại một comment nêu rõ cần sửa gì, và không approve.
6. Merge: khi approval rule được thoả, chọn Merge và chọn tuỳ chọn xoá source branch.

```bash
aws codecommit create-pull-request --title "<title>" --targets repositoryName=<repo>,sourceReference=<branch>,destinationReference=<base-branch>
aws codecommit update-pull-request-approval-state --pull-request-id <id> --revision-id <revision-id> --approval-state APPROVE
aws codecommit merge-pull-request-by-squash --pull-request-id <id> --repository-name <repo>
aws codecommit delete-branch --repository-name <repo> --branch-name <branch>
```

Lấy `<revision-id>` từ `aws codecommit get-pull-request --pull-request-id <id>`. Approval chỉ có giá trị trên revision hiện tại, nên đọc lại revision id sau mỗi lần push.

## Phụ lục: hỗ trợ từ AI { #appendix-ai-support }

Các prompt này nhờ AI agent làm phần việc git. Thay phần trong dấu ngoặc nhọn bằng nội dung thật.

Mở pull request cho công việc hiện tại:

```text
Commit my changes with a message that follows the team convention, push the branch, and open a pull request. Fill the template: Summary, Plan, Tracks, Spec, Beads, and Tests.
```

Tóm tắt một pull request để review:

```text
Summarise pull request <url> for review against its spec. List what changed, which acceptance criteria are met, and which are not.
```

Xử lý các comment review:

```text
Read the review comments on <url>. Address each one, commit the fixes, push, and tell me which comments you resolved.
```

Cập nhật branch và giải quyết conflict:

```text
Update my branch from the base branch and resolve the conflicts. Show me each conflict and the choice you made before you commit.
```
