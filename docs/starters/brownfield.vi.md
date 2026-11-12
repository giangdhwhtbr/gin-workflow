# Brownfield: từ monolith JSP legacy tới giao hàng theo milestone { #brownfield-from-a-legacy-jsp-monolith-to-milestone-delivery }

Trang này theo chân một nhóm từ lúc "chúng tôi thừa hưởng một hệ thống legacy" tới khi milestone đầu tiên được ship và milestone kế tiếp được lập kế hoạch. Mỗi giai đoạn nêu ai chạy nó, prompt cần dán, nội dung đưa vào prompt, kết quả nhận được, cổng hoặc phê duyệt, và các lỗi cần tránh.

Trong một codebase có sẵn, code thường là đặc tả duy nhất, nên ngăn regression là việc đặt lên đầu. Chiến lược hiện đại hóa ở đây (strangler fig, parity test, data migration) là quy ước mà nhóm của bạn tuân theo. gin-workflow chỉ cưỡng chế các khu vực của track (`team.areas`) và các requirement hash mà test case của `gin-qa` ghim lại.

## Kịch bản { #the-scenario }

`shop-portal` là một monolith Java 8 JSP và Struts chạy trên Oracle. Nhóm thay thế nó phía sau một facade bằng REST API Spring Boot và React SPA, dưới một repository cha (workspace):

| Thư mục | Nội dung |
|---|---|
| `legacy/shop-portal/` | ứng dụng Struts, repository `frozen` chỉ để đọc |
| `services/order-api/` | Spring Boot API cho đơn hàng và facade |
| `services/catalog-api/` | Spring Boot API cho danh mục |
| `apps/web-shop/` | React SPA cho khách hàng |
| `apps/web-admin/` | React SPA cho quản trị |
| `qa/` | repository automation: test case, end-to-end spec, evidence |
| `.beads/` | cơ sở dữ liệu Beads dùng chung |

Nhóm có bảy người. Lan và Binh giữ hai seat Claude Team Premium, nên nhận các việc cần model mạnh nhất: roadmap và milestone, plan, review, và track migration khó nhất. An, Em, Dung, Hoa và Chi giữ năm seat Standard và nhận các track có phạm vi rõ. Việc phân bổ seat là lựa chọn của nhóm, không phải một thiết lập.

| Người | Vai trò | Đọc | Làm |
|---|---|---|---|
| Lan | `pm` | [PM](../roles.md#pm) | Roadmap, milestone, báo cáo milestone |
| An | `ba` | [BA](../roles.md#ba) | Spec và user story |
| Binh | `be_lead` | [Tech lead](../roles.md#tech-lead) | Setup, plan, orchestrate, ship, cutover |
| Em | `be_dev` | [Developer](../roles.md#developer) | Công việc API |
| Dung | `be_dev` | [Developer](../roles.md#developer) | Công việc API |
| Hoa | `fe_lead`, `fe_dev` | [Frontend lead](../roles.md#who-owns-what) | Công việc React SPA, duyệt plan của web |
| Chi | `qe` | [Tester](../roles.md#tester) | Test case, E2E, phê duyệt ship |

Khối `team:` trong `.agent-workflow/config.yaml` (do `/gin:team-setup` ghi):

```yaml
team:
  host: github
  commit_convention: conventional
  members:
    lan@example.com: {roles: [pm], login: lan-pm}
    an@example.com: {roles: [ba], login: an-ba}
    binh@example.com: {roles: [be_lead], login: binh-dev}
    em@example.com: {roles: [be_dev], login: em-dev}
    dung@example.com: {roles: [be_dev], login: dung-dev}
    hoa@example.com: {roles: [fe_lead, fe_dev], login: hoa-dev}
    chi@example.com: {roles: [qe], login: chi-qe}
  areas:
    legacy: {paths: ["legacy/shop-portal/**"], lead: be_lead, roles: [be_dev]}  # read-only: for tech-doc reading, no track targets it
    api: {paths: ["services/**"], lead: be_lead, roles: [be_dev]}
    web: {paths: ["apps/**"], lead: fe_lead, roles: [fe_dev]}
    qa: {paths: ["qa/**"], lead: be_lead, roles: [qe]}
  approvals:
    requirement_confirmed:
      capability: {all: [ba], any: [be_lead, fe_lead]}
      technical: [be_lead, fe_lead]
      parity: [ba]
    plan_approved: area_lead
    ship: {all: [qe], any: [be_lead, fe_lead]}
    roadmap: [pm, be_lead]
  permissions: {milestone: [pm]}
```

Các khu vực không chồng lấn, nên mọi track của plan đều nằm trong một khu vực. Không cổng nào do tác giả của pull request duyệt. `requirement_confirmed` giữ một chính sách cho mỗi [loại epic](../guides/team.md#policy-per-epic-kind), còn `capability` và `ship` dùng dạng object: mọi vai trò `all` phải duyệt, và một vai trò `any` phải duyệt. Tác giả không bao giờ duyệt. An là `ba` duy nhất, nên với spec capability do An viết, vai trò `ba` bị bỏ qua kèm ghi chú "ba skipped: the author is its only holder", và Binh hoặc Hoa duyệt. Spec technical chỉ cần một lead: khi Binh viết nó thì Hoa duyệt, không có BA tham gia. Spec parity cần một `ba` khác tác giả, nên Binh viết nó từ bản capture đã xác nhận của An và An duyệt. Chi là `qe` duy nhất, nên với pull request QA của chính Chi, vai trò `qe` bị bỏ qua tương tự, và Binh hoặc Hoa duyệt. Lan không có `pm` thứ hai, nên Binh duyệt các pull request roadmap của Lan (`roadmap: [pm, be_lead]`). Binh và Hoa mỗi người dẫn một khu vực, nên `gin setup doctor` ghi chú rằng `qe`, `be_lead` và `fe_lead` chỉ có một người giữ. Cơ chế bỏ qua chỉ áp dụng khi tác giả là người giữ duy nhất; thêm người giữ thứ hai để bỏ nó. Chỉ Lan, `pm` duy nhất, được chạy các lệnh ghi của `gin milestone`.

## Toàn cảnh luồng làm việc { #the-flow-at-a-glance }

```mermaid
flowchart LR
  R["Repository<br/>Tech Lead"] --> A["Setup<br/>Tech Lead"]
  A --> B["tech-doc<br/>Tech Lead"]
  B --> C["roadmap<br/>PM"]
  C --> D["Milestone<br/>PM"]
  D --> CA["capture + mockup<br/>BA"] --> E["discuss epic<br/>BA"]
  E --> F["plan + orchestrate<br/>Tech Lead"]
  F --> G["Test cases<br/>QE"]
  G --> H["execute<br/>Dev"]
  H --> I["e2e<br/>QE"]
  I --> J["ship<br/>Tech Lead"]
  J --> K["review + spill-over<br/>PM"]
  K -->|"next milestone"| D
```

## Thiết lập repository và workspace { #repository-and-workspace-setup }

**Ai làm:** Tech Lead, một lần.

**Làm ở đâu:** repository cha, nơi chứa `docs/` và `.planning/`. Các repository con là bản clone thường nằm dưới nó, không phải submodule.

**Prompt**
```text
/gin:setup
Repositories: legacy/shop-portal (Struts, frozen), services/order-api and services/catalog-api (Spring Boot, Maven), apps/web-shop and apps/web-admin (React, npm), qa (automation), .beads (shared Beads database).
Checks: mvn -q test and mvn -q package for the services; npm run lint, npm test and npm run build for the apps.
```
Trả lời `stage: brownfield`, `shape: fullstack`, và `workspace` cho kiểu bố trí repository. Sau đó đặt `artifacts.layout: sdd` và điền `workspace.repos` trong `.agent-workflow/config.yaml`:

```yaml
artifacts:
  layout: sdd
  test_globs: ["**/src/test/**", "**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*", "tests/**", "__tests__/**"]
workspace:
  repos:
    - {path: legacy/shop-portal, url: git@github.com:acme/shop-portal.git, frozen: true}
    - path: services/order-api
      url: git@github.com:acme/order-api.git
      shape: backend
      verify: {checks: {test: mvn -q test, build: mvn -q package}}
    - path: services/catalog-api
      url: git@github.com:acme/catalog-api.git
      shape: backend
      verify: {checks: {test: mvn -q test, build: mvn -q package}}
    - {path: apps/web-shop, url: git@github.com:acme/web-shop.git, shape: frontend,
       verify: {checks: {lint: npm run lint, test: npm test, build: npm run build}}}
    - {path: apps/web-admin, url: git@github.com:acme/web-admin.git, shape: frontend,
       verify: {checks: {lint: npm run lint, test: npm test, build: npm run build}}}
    - {path: qa, url: git@github.com:acme/qa.git, shape: qa}
    - {path: .beads, url: git@github.com:acme/beads.git, shape: beads}
```

Danh sách `test_globs` là các glob mặc định cộng thêm cây test của Maven, vì danh sách được cấu hình sẽ thay thế các giá trị mặc định. Nhờ vậy `gin specs trace` tìm thấy test của các service.

Sau đó clone tất cả và cài hook trong từng repository:

```bash
gin workspace clone --all
gin hooks install --all-repos
gin setup doctor
```

Đưa vào prompt: sáu repository ở trên cùng stack của từng cái (Maven cho các service, npm cho các app), và repository Beads dùng chung.

`legacy/shop-portal` là `frozen`: nó được clone nông (shallow), chỉ để đọc cho bước khảo sát và các parity test, và không bao giờ có hook, track hay worktree. `.beads` là mục giữ cơ sở dữ liệu Beads dùng chung. `qa` là repository automation, nên nó là [QA home](../guides/qa.md#the-qa-home) và `gin-qa` vẫn ghi `cases/`, `e2e/` và `evidence/` vào đó. Mỗi path được thêm vào `.gitignore` của repository cha, nên repository cha không theo dõi repository con nào. Mỗi kỹ sư chỉ clone các repository họ làm việc; xem [hướng dẫn workspace](../guides/workspace.md).

Phương án thay thế là một repository duy nhất với code legacy dưới dạng git subtree:

```bash
git subtree add --prefix=legacy git@github.com:acme/shop-portal.git main
mkdir -p services/api apps/web qa
```

Ở biến thể này, trả lời `monorepo: true` trong `/gin:setup` và tự thêm một mục `project.packages` cho `services/api` và một cho `apps/web`, mỗi mục có `path`, `shape` và `verify.checks` ([cấu hình](../reference/config.md#verifychecks)). Chọn nó khi một thay đổi facade, một parity test và một lần gỡ legacy phải nằm trong cùng một pull request và một lịch sử, khi nhóm đủ nhỏ để dùng chung một pipeline deploy, và khi không ai cần deploy một service riêng lẻ. Kéo các bản sửa của vendor về sau bằng `git subtree pull --prefix=legacy git@github.com:acme/shop-portal.git main`. Phần còn lại của trang này giả định bạn dùng workspace.

**Kết quả:** mọi repository được clone tại path của nó, một hook pre-commit và pre-push trong từng repository đã clone (trừ mục frozen và beads) chạy check của chính repository đó, và `.agent-workflow/config.yaml` với `workspace.repos`.

**Cổng hoặc phê duyệt:** không có.

**Lỗi thường gặp:** chạy `/gin:setup` trong một repository con thay vì repository cha; để một path trong `.gitmodules` trong khi nó cũng có trong `workspace.repos` (`gin setup doctor` báo là vẫn còn submodule); quên `gin hooks install --all-repos` nên một repository con không có hook.

## Setup và team setup { #setup-and-team-setup }

**Ai làm:** Tech Lead một lần cho mỗi repository, sau đó mỗi thành viên một lần trên bản clone của mình. Thành viên không tự đăng ký: lead liệt kê mọi thành viên, vai trò, khu vực và phê duyệt trong khối `team:`. Chi cũng chạy `/gin-qa:setup` một lần.

**Làm ở đâu:** repository cha.

**Prompt (Tech Lead)**
```text
/gin:team-setup
Members: lan@example.com (pm), an@example.com (ba), binh@example.com (be_lead), em@example.com and dung@example.com (be_dev), hoa@example.com (fe_lead and fe_dev), chi@example.com (qe).
Areas: legacy is legacy/shop-portal/** and read-only; api is services/**; web is apps/**; qa is qa/**. Binh leads legacy, api, and qa; Hoa leads web.
Approvals: requirement_confirmed by kind (capability: ba and one of be_lead or fe_lead; technical: be_lead or fe_lead; parity: ba); plan_approved by the area lead; ship by qe and one of be_lead or fe_lead; roadmap by pm and be_lead.
Permissions: only the pm changes milestones.
```

**Prompt (mỗi thành viên, sau khi pull branch đã merge)**
```text
/gin:team-setup
I am Em (em@example.com), a be_dev. The team: block is merged on master.
```

**Prompt (Chi, một lần)**
```text
/gin-qa:setup
Case types: api, e2e and manual.
The api type: tests under qa/api/, run with npm test.
```

Đưa vào prompt: bảy thành viên cùng git email và vai trò của họ, bốn khu vực cùng đường dẫn, và `permissions: {milestone: [pm]}` để chỉ PM thay đổi milestone. Với `/gin-qa:setup`: các loại case `api`, `e2e` và `manual`, và lệnh test của loại `api`.

Lead trả lời `team-setup` với tư cách lead. Nó ghi khối `team:`, chạy `gin team init` (thêm `--ci` cho một workflow CI), rồi bạn commit trên một branch, push và mở pull request. Hãy merge nó. Một thành viên trả lời với tư cách thành viên: nó kiểm tra `gin team whoami` tìm thấy `git config user.email` của bạn, cài commit-msg hook (`gin team hooks`), yêu cầu bạn đăng nhập (`gh auth login` hoặc `glab auth login`), chạy `bd init --remote <remote>` khi nhóm dùng chung Beads, và kết thúc bằng `gin setup doctor`. Không có gì được ghi ngược vào repository.

`/gin-qa:setup` đọc những gì QA home đã nói và ghi `guidelines.md` của nó (các mục `## Types`, `## Automated types`, `## Manual runs` và `## Bugs`), `README.md`, và một skill QA của dự án dưới `.claude/skills/`. Xem [add-on QA](../guides/qa.md#setup-gin-qasetup).

**Kết quả:** khối `team:`, `.github/CODEOWNERS` (`.gitlab/CODEOWNERS` trên GitLab), một pull request template, một commit-msg hook trên mỗi bản clone, và các QA guideline.

**Cổng hoặc phê duyệt:** không có. Lead bảo vệ base branch trên host (pull request, một lượt duyệt, "Require review from Code Owners") và, để job CI chạy được `team codeowners --check`, đặt biến repository `GIN_WORKFLOW_INSTALL` (xem [CI](../guides/team.md#ci-optional)).

**Lỗi thường gặp:** quên một thành viên hoặc PM trong `members` (khi đó phê duyệt `roadmap` thất bại với "role pm is held by no member" và cách sửa là một pull request khác); git email khác với email trong `members` (`team whoami` không tìm thấy gì); bỏ qua bước đăng nhập host.

## Khảo sát hệ thống legacy { #survey-the-legacy-system }

**Ai làm:** Tech Lead.

**Làm ở đâu:** repository cha.

**Prompt**
```text
/gin:tech-doc whole repository
Entry points: web.xml and struts-config.xml in legacy/shop-portal.
Database: Oracle; the checkout JSPs call stored procedures.
Replace first: the catalog, then the cart and checkout.
```

Đưa vào prompt: các entry point bạn biết (`web.xml`, cấu hình Struts), cơ sở dữ liệu, và các module bạn định thay thế trước.

**Kết quả:** bộ tech-doc dưới `.planning/codebase/` (hoặc `docs/codebase/` với layout SDD), mỗi chủ đề một file (`OVERVIEW`, `FEATURES`, `API`, `STACK`, `INTEGRATIONS`, `ARCHITECTURE`, `STRUCTURE`, `CONVENTIONS`, `TESTING`, `CONCERNS`, `GLOSSARY`).

Khi hệ thống legacy dùng một ngôn ngữ khác tiếng Anh, bộ này còn có `11-GLOSSARY.md`: mỗi thuật ngữ nghiệp vụ kèm thuật ngữ tiếng Anh đề xuất, các identifier mang nó, và bằng chứng. Trước `/gin:discuss` đầu tiên, hãy đặt các bản dịch bạn chấp nhận thành `confirmed`, giải quyết bảng `Conflicts`, và thêm `glossary` vào `rules.packs` trong `.agent-workflow/config.yaml`. Khi đó spec, plan, code, và review dùng cùng thuật ngữ, và các lần chạy `/gin:tech-doc` sau không bao giờ đổi một thuật ngữ đã confirmed.

**Cổng hoặc phê duyệt:** không có. Hãy review nó cùng nhóm; roadmap chỉ tốt bằng bản khảo sát này.

**Lỗi thường gặp:** chỉ ghi lại những phần bạn định đụng tới trước; roadmap cần toàn bộ bức tranh as-is để đặt các dependency, chẳng hạn các stored procedure Oracle mà các JSP checkout gọi tới.

## Tổng quan roadmap { #roadmap-overview }

**Ai làm:** PM.

**Làm ở đâu:** repository cha.

**Prompt**
```text
/gin:roadmap Goal: replace the catalog, cart and checkout JSP flows with the Spring Boot REST API and the React SPA.
Deadline: 2027-05-28.
Constraints: the Oracle schema stays; no downtime; each module cuts over behind the facade.
Non-goals: reporting screens.
```

Đưa vào prompt: mục tiêu, deadline, các ràng buộc không thể dịch chuyển (ở đây là schema, zero downtime và facade), và các non-goal. Thứ tự thực hiện và cách làm việc không phải đầu vào: skill đề xuất cả hai và PM xác nhận.

**Kết quả:** skill đọc bộ tech-doc và hỏi về mục tiêu, deadline, các ràng buộc và năng lực AI. Dòng `AI capacity:` bắt đầu bằng số lane, tức số luồng công việc mà mỗi luồng chạy một epic tại một thời điểm. Skill đề xuất hai hoặc ba cách chia công việc cùng một cách làm việc, rồi hiển thị roadmap kèm `Estimate:` theo ngày làm việc của từng epic để xác nhận. Khi chưa có epic roadmap nào đã đóng để đo tốc độ, skill hỏi một giá trị ngày cho mỗi cỡ (nhỏ, vừa, lớn) và đánh dấu các ước lượng là `(assumed)`.

Sau khi xác nhận, skill ghi `.planning/roadmap.md` (`docs/roadmap.md` với layout SDD) trên branch `roadmap/<topic>`. `Deadline:` và `AI capacity:` nằm dưới `## Constraints`, còn cách làm việc đã xác nhận nằm dưới `## Way of working`. Sau khi đồng bộ, skill tạo mỗi mục một epic cùng dependency trong Beads và lưu từng ước lượng bằng `gin milestone estimate`. Báo cáo của skill so sánh forecast từ `gin milestone list` với deadline: ngày hoàn thành, số ngày làm việc còn dư hoặc vượt, và số epic chưa có ước lượng. Vượt deadline chỉ được báo cáo, không chặn. Đọc kết quả dưới dạng đồ thị:

```bash
gin task graph --all
```

Trang Dependencies của gin-console hiển thị cùng đồ thị đó. Từ đó chọn việc làm trước: các epic không có blocker đang mở, và epic mở khóa được nhiều epic khác nhất (ở đây là API facade).

Mỗi mục roadmap có một dòng `Kind:`, và các epic nhận label `kind:<kind>` tương ứng (xem [loại epic](../concepts/lifecycle.md#epic-kinds)). Ở đây `shop-portal-catalog-read` là `capability`, API facade là `technical` (`Kind: technical`, không có hành vi người dùng thấy), và `shop-portal-cart-parity` là `parity` (`Kind: parity`, port 1-1 các trang giỏ hàng mà An đã capture). Mỗi loại có chính sách `requirement_confirmed` riêng trong khối `team` ở trên.

**Cổng hoặc phê duyệt:** với `team.approvals.roadmap: [pm, be_lead]`, roadmap đi qua một pull request mà Binh duyệt (Lan không thể tự duyệt). Chạy lại prompt với URL của PR; skill kiểm tra nó bằng `gin team check <url> --gate roadmap`, rồi tạo các epic.

**Lỗi thường gặp:** sửa epic id trong file roadmap về sau (id không bao giờ đổi một khi đã ghi); mong roadmap đóng hoặc xóa các epic bạn bỏ khỏi file (nó chỉ báo cáo chúng); bắt đầu với epic có nhiều người dùng nhất thay vì epic mở khóa phần còn lại; coi forecast dựa trên ước lượng `(assumed)` là kết quả chắc chắn.

## Lập kế hoạch milestone { #milestone-planning }

**Ai làm:** PM.

**Làm ở đâu:** repository cha.

**Prompt**
```bash
gin milestone create "M1 Catalog read path" --start 2026-11-10 --end 2026-11-28 --lanes 3
```
```text
/gin:roadmap --milestone <id>
Milestone goal: customers browse the catalog on the new API behind the facade.
Leave out: the cart and checkout epics.
```

Dùng id mà `milestone create` in ra. Đưa vào prompt: mục tiêu của milestone và các epic cần loại ra. Skill tự chọn các epic sẵn sàng.

`--lanes` là năng lực của milestone này và có thể khác số ở `AI capacity:` của dự án. Khi không có `--lanes`, milestone dùng số đó, rồi đến số `team.members`, rồi 1.

Sau đó chốt ngày kick-off, đọc forecast và đọc lịch:

```bash
gin milestone kickstart <id> --date 2026-11-10
gin milestone list
gin milestone show <id>
```

**Kết quả:** các epic được chọn nằm dưới milestone, mỗi epic có `Estimate:` theo ngày làm việc. File roadmap gom chúng dưới `## Milestone: <title>`, mở đầu bằng `Spec ready by:` (ngày kick-off, nếu chưa có thì ngày bắt đầu) và một khối `Integration point:`. Integration point chỉ là một ngày trong file roadmap; Beads không lưu nó.

`gin milestone list` in một dòng forecast cho mọi epic đang mở, đã gán milestone hay chưa. `gin milestone show` in lịch và các cảnh báo (`overflow`, `late`, `unestimated`, `external_blocker`, `spec_not_ready`). Sau kick-off, `spec_not_ready` đánh dấu epic đang mở mà spec chưa được xác nhận, để BA biết spec nào đến hạn.

Lặp lại cho từng milestone. Khi các milestone đóng, số epic đang mở trong dòng forecast giảm và ngày hoàn thành thay đổi, vì các epic còn lại được xếp lịch lại từ hôm nay. Một milestone là một bead của Beads có ngày bắt đầu và ngày kết thúc, không phải một label.

**Cổng hoặc phê duyệt:** `permissions.milestone: [pm]` chỉ cho Lan ghi; cổng pull request roadmap của giai đoạn trước vẫn áp dụng cho các thay đổi roadmap.

**Lỗi thường gặp:** chọn một epic có blocker nằm ở milestone sau (`external_blocker`); để epic không có ước lượng (`unestimated`); lập kế hoạch vượt quá ngày kết thúc (`overflow`); kick-off milestone khi epic chưa có spec được xác nhận (`spec_not_ready`).

## Chụp và mockup (BA) { #capture-and-mockup-ba }

**Ai làm:** BA.

**Làm ở đâu:** repository cha.

**Prompt**
```text
/gin-ba:capture catalog --date 2026-11-12
Screenshots: the JSP catalog list and the product detail page, from the legacy system.
```
```text
/gin-ba:mockup catalog
```

Đưa vào prompt: ảnh chụp màn hình legacy của danh sách catalog và trang chi tiết sản phẩm. Chỉ chạy `/gin-ba:mockup catalog` khi UI mới khác UI legacy.

**Kết quả:** một thư mục có ngày dưới `docs/specs/catalog/assets/`, với `Kind: legacy` trong `description.md`, và một thư mục mockup khi UI thay đổi. Ảnh chụp nằm dưới `legacy/` trong thư mục có ngày. Cả hai skill đều để thư mục chưa commit.

**Cổng hoặc phê duyệt:** không có. BA xác nhận từng thư mục bằng `gin specs assets confirm catalog --date 2026-11-12`, và `--agreed-with` ghi lại ai khác đã đồng ý (xem [hướng dẫn cho BA](../guides/ba.md)). `/gin:discuss` chỉ trích dẫn thư mục đã xác nhận và commit chúng cùng thư mục change, như [hình ảnh và mockup](../guides/sdd.md#images-and-mockups) mô tả. Xem thêm [living spec trong lúc migration](../guides/sdd.md#living-specs-during-a-migration) và [hướng dẫn cho BA](../guides/ba.md).

**Lỗi thường gặp:** commit một thư mục asset trên nhánh riêng; chạy discuss trước khi các thư mục được xác nhận.

## Discuss một epic { #discuss-an-epic }

**Ai làm:** BA.

**Làm ở đâu:** repository cha.

**Prompt**
```text
/gin:discuss shop-portal-catalog-read
Replace the JSP catalog list and product detail pages.
Legacy rules: hidden products never show; the price comes from the customer's price list and falls back to the list price; out-of-stock items show "Notify me".
Out of scope: search and reviews.
```

Đưa vào prompt: hành vi người dùng nhìn thấy của luồng JSP bạn thay thế, các edge case và quy tắc validation của nó (xem [Hành vi legacy và living spec](#legacy-behavior-and-living-specs)), và những gì nằm ngoài phạm vi. An không có vai trò kỹ thuật, nên discuss ghi mỗi chi tiết của hợp đồng (path, method, field, mã lỗi) thành một câu hỏi kỹ thuật cho tech lead (xem [hợp đồng](../guides/workspace.md#contract)).

**Kết quả:** cuộc thảo luận bắt đầu từ epic và mục roadmap của nó và dùng lại epic đó (không tạo epic mới). Spec được dựng từ template `design-spec.md` (hoặc `proposal.md` với layout SDD) và có mục `## User Stories`. Mỗi story có acceptance criteria và, với REQ-ID, một dòng `REQ:`.

**Cổng hoặc phê duyệt:** spec được commit trên `spec/<topic>` và mở dưới dạng pull request. Với epic capability, chính sách `capability` áp dụng: vai trò `ba` của chính An bị bỏ qua vì An là tác giả, và Binh hoặc Hoa duyệt. Epic technical hoặc parity dùng chính sách riêng (xem [Tổng quan roadmap](#roadmap-overview)). Cổng được ghi nhận cùng URL của PR sau khi merge. Một khi đã được xác nhận, phần nghiệp vụ của hợp đồng bị đóng băng; các chi tiết kỹ thuật bị đóng băng khi plan được duyệt.

**Lỗi thường gặp:** tạo epic thứ hai bằng tay; story không có acceptance criteria; bỏ qua các edge case của legacy.

### Hành vi legacy và living spec { #legacy-behavior-and-living-specs }

Living spec mô tả hệ thống mới. Hành vi legacy nằm trong các thư mục `Kind: legacy` đã xác nhận, và mỗi requirement lấy từ đó nêu thư mục của nó trong dòng `Source:`. Xem [living spec trong lúc migration](../guides/sdd.md#living-specs-during-a-migration).

```markdown
### REQ-CATALOG-001: Hide unpublished products
The catalog API SHALL omit hidden products from the product list.
Source: `assets/2026-11-12/description.md`
```

## Plan và orchestrate { #plan-and-orchestrate }

**Ai làm:** Tech Lead.

**Làm ở đâu:** repository cha.

**Prompt**
```text
/gin:plan shop-portal-catalog-read
Migration: the facade comes first; the catalog API reads the existing Oracle tables, so no dual-write and no backfill.
Rollback: route the facade back to the JSP pages when the parity tests fail after cutover.
Parallel: QA cases, the catalog API, and the SPA against contract mocks.
Seats: the router cutover track goes to Binh on a Premium seat.
Each track names its repository, for example Repo: services/catalog-api.
Answer each TQ-<n> with the contract of its endpoint.
```
```text
/gin:orchestrate shop-portal-catalog-read
Create the track beads and worktrees from the approved plan.
Leave every track bead unassigned; members take theirs with gin team claim.
```

Đưa vào prompt: các ràng buộc của migration (facade trước, dual-write hay backfill, tiêu chí rollback), các track nào có thể chạy song song, và ai giữ seat Premium. Mỗi track mang `Repo: <path>`, ví dụ `Repo: services/order-api`. Tech lead cũng trả lời từng `TQ-<n>` mà discuss để lại, bằng path, method, request, response và mã lỗi của endpoint, để API mới và các mock của SPA được xây từ cùng một nguồn. Duyệt plan đóng băng các câu trả lời đó.

**Kết quả:** một plan với các track theo khu vực và owner (`gin team check-plan <plan>` phải qua), rồi mỗi track một track bead dưới epic được dùng lại, gồm cả các track QA, một worktree cô lập cho mỗi track, và các dependency. Thành viên claim bead của mình bằng `gin team claim <bead>`.

**Cổng hoặc phê duyệt:** với `plan_approved: area_lead`, lead của từng khu vực mà plan đụng tới duyệt pull request của plan. Binh viết plan và là `be_lead` duy nhất, nên phê duyệt `api` và `qa` của anh ấy được bỏ qua kèm ghi chú khi Hoa, lead của `web`, đã duyệt.

**Lỗi thường gặp:** một track đụng tới hai khu vực, ví dụ `services/` và `apps/`; hãy chạy `gin team check-plan <plan>` trước khi xin duyệt.

### Strangler Fig { #strangler-fig }

Hiện đại hóa từng bounded context một phía sau một facade hoặc router ổn định thay vì viết lại tất cả cùng lúc. Traffic của các endpoint đã hiện đại hóa đi tới bản triển khai mới, còn các request chưa migrate được chuyển tiếp xuống lõi legacy. Facade hoặc gateway là hạ tầng của riêng bạn; gin-workflow không cung cấp. Các `team.areas` ở trên giữ mọi track trong các repository đã hiện đại hóa; khu vực `legacy` bị đóng băng chỉ tồn tại để `/gin:tech-doc` đọc, và không track nào nhắm tới nó.

Trong `/gin:discuss`, hãy chốt chiến lược data migration (dual-write hoặc backfill) và tiêu chí rollback, còn trong `/gin:plan` hãy chia epic thành các track một khu vực. Đó là một epic cho capability, với các track ở mỗi repository mà nó thay đổi ([giới hạn của workspace](../guides/workspace.md#limits)):

| Track | Khu vực | Repo | Owner | Công việc |
|---|---|---|---|---|
| 1 | `qa` | `qa` | Chi | Test case cho capability catalog, mỗi case một file |
| 2 | `api` | `services/catalog-api` | Em | Spring Boot API, facade và parity test theo hợp đồng |
| 3 | `web` | `apps/web-shop` | Hoa | React UI xây dựa trên contract mock |
| 4 | `web` | `apps/web-shop` | Hoa | Tích hợp: thay các mock bằng lời gọi API thật |
| 5 | `api` | `services/order-api` | Binh | Router cutover sang facade mới, trên seat Premium với effort cao |
| 6 | `qa` | `qa` | Chi | API test, E2E, manual run và báo cáo |

```mermaid
flowchart LR
  S["requirement_confirmed"] --> T1["Track 1 qa cases"]
  S --> T2["Track 2 api"]
  S --> T3["Track 3 web mocks"]
  T2 --> T4["Track 4 web integration"]
  T3 --> T4
  T2 --> T5["Track 5 router cutover"]
  T1 --> T6["Track 6 qa E2E and report"]
  T4 --> T6
  T5 --> T6
```

Các script kiểm tra parity và dữ liệu chạy trong hook `pre-push` khi lệnh `verify.checks.test` chạy chúng ([cấu hình](../reference/config.md#verifychecks)).

## Test case { #test-cases }

**Ai làm:** QE.

**Làm ở đâu:** repository `qa`.

**Prompt**
```text
/gin-qa:cases catalog
Epic: shop-portal-catalog-read.
Legacy behaviors the new API must match: hidden products never listed; customer price list with list-price fallback; the legacy pagination; the "Notify me" button on out-of-stock items.
```
```text
/gin-qa:tests catalog --type api
Compare the new API with the legacy pages on payloads recorded from staging.
```

Đưa vào prompt: epic, và các hành vi legacy mà API mới phải khớp.

Unit test qua không chứng tỏ code mới hành xử như code cũ. Parity test so sánh hai bên:

1. Thu thập các payload production hoặc staging đã ghi lại (Golden Master).
2. Chạy từng payload trên cả bản triển khai legacy lẫn bản hiện đại.
3. Khẳng định không có khác biệt ngoài dự kiến nào trong các response.

**Kết quả:** mỗi case một file dưới `qa/cases/catalog/`, ví dụ `TC-CATALOG-001-list-products.api.md`, `TC-CATALOG-002-search-by-name.e2e.md` và `TC-CATALOG-003-legacy-pagination.manual.md`. Mỗi case gắn với một requirement và content hash của nó, và `gin-qa cases pin` ghi lại hash sau khi một case được cập nhật; `gin-qa cases plan` đánh dấu các case đã lỗi thời. Các loại `api`, `e2e` và `manual` được liệt kê dưới `## Types` trong `qa/guidelines.md`. `/gin-qa:tests` viết và chạy các test `api` từ các glob `Tests:` và lệnh `Run:` khai báo dưới `## Automated types`. Một repository vẫn còn file case phẳng theo từng capability thì chuyển nó một lần bằng `gin-qa cases split catalog`.

**Cổng hoặc phê duyệt:** không có.

**Lỗi thường gặp:** viết case trước khi spec được merge, vì chúng trỏ tới các requirement vẫn có thể thay đổi; loại `api` không có khai báo `Tests:` và `Run:`.

## Execute { #execute }

**Ai làm:** Developer (Em và Dung cho các track API, Hoa cho các track SPA).

**Làm ở đâu:** worktree của track `<parent>/.planning/worktrees/<track-id>` (một service hoặc một app).

**Prompt**
```bash
gin team ready
gin team claim shop-portal-catalog-read.2
```
```text
/gin:execute
Track: shop-portal-catalog-read.2, the catalog API track in services/catalog-api.
Stay inside that repository and run its checks before closing the track.
```

Đưa vào prompt: track bead cần làm, nếu bạn muốn tự chọn.

`team ready` liệt kê các bead trong khu vực của bạn. `team claim` ghi một lease dài `team.claim_ttl_hours` (mặc định 48); claim lại để gia hạn, và khi lease hết hạn thì thành viên khác có thể nhận bead. Nếu một thành viên vắng mặt hoặc hết quota, hãy push track branch và chạy:

```bash
gin team reassign <bead> dung@example.com
```

Người nhận mới phải được phép sở hữu track trong các khu vực của bead, sau đó checkout branch đã push và tiếp tục.

**Kết quả:** một track được triển khai test-first trong worktree, một review độc lập, một track bead đã đóng, và một feature branch đã push.

**Cổng hoặc phê duyệt:** `execute` từ chối một epic `roadmap` chưa có spec được xác nhận; hãy chạy [Discuss một epic](#discuss-an-epic) trước. Claim thất bại nếu đồng đội đang giữ một lease còn hiệu lực.

**Lỗi thường gặp:** làm việc ngoài phạm vi file của track; để lease hết hạn trong khi công việc vẫn tiếp diễn; đóng bead trước khi review xong.

## E2E { #e2e }

**Ai làm:** QE.

**Làm ở đâu:** repository `qa`.

**Prompt**
```text
/gin-qa:e2e catalog
Base URL: the web-shop staging URL, read from BASE_URL.
Accounts: SHOP_USER and SHOP_PASSWORD for a customer.
Flows: browse a category, open a product page, join the "Notify me" list of an out-of-stock product.
```
```text
/gin-qa:run catalog
Manual cases only; start with TC-CATALOG-003.
```
```text
/gin-qa:report catalog
Include the evidence of this run; the report goes to the product owner as a zip.
```

Đưa vào prompt: base URL của SPA, các tài khoản test (dưới dạng tên biến môi trường), và các luồng cần phủ.

**Kết quả:**
- `gin-qa e2e init` ghi `playwright.config.ts` khi repository chưa có, cùng evidence fixture.
- `/gin-qa:e2e` viết các Playwright spec dưới `qa/e2e/catalog/` và ghi evidence dưới `qa/evidence/`.
- `/gin-qa:run` đi qua các manual case, ghi từng kết quả bằng `gin-qa cases result`, và tạo một bug bead cho mỗi lỗi qua `gin-qa cases bug`, liên kết với epic bằng `discovered-from`.
- `/gin-qa:report` ghi một thư mục báo cáo HTML offline dưới `qa/evidence/` mà bạn có thể nén và gửi đi.

**Cổng hoặc phê duyệt:** với `ship: [qe, be_lead]`, Chi duyệt commit mới nhất của pull request của developer trước khi nó merge, và Binh duyệt của Chi. Một lần push sau đó cần duyệt lại. Xem [checklist phê duyệt ship](../guides/qa.md#ship-approval-checklist).

**Lỗi thường gặp:** duyệt trước commit cuối; một lần push sau khi duyệt âm thầm làm phê duyệt mất hiệu lực.

## Ship { #ship }

**Ai làm:** Tech Lead.

**Làm ở đâu:** repository cha.

**Prompt**
```text
/gin:ship
Epic: shop-portal-catalog-read.
Open a pull request instead of merging locally; Chi approves the latest commit first.
```

Đưa vào prompt: epic, và liệu có merge ngay hay giữ branch.

**Kết quả:** sản phẩm bàn giao đã merge. Ở chế độ nhóm, bằng chứng PR của cổng được ghi vào metadata `gates` của epic bead, để đồng đội thấy nó trong `gin state` mà không cần event store cục bộ của bạn.

**Cổng hoặc phê duyệt:** BA nghiệm thu mỗi epic bằng một comment nghiệm thu trước khi ship ([trong lúc build](../guides/ba.md#during-the-build)). Merge vào base branch cần phê duyệt rõ ràng; phê duyệt `ship` trên commit mới nhất được kiểm tra trước.

**Lỗi thường gặp:** ship track của một thành viên như thể tính năng đã hoàn tất; lead tuyên bố epic xong khi mọi pull request của track đã merge.

## Review milestone và spill-over { #milestone-review-and-spill-over }

**Ai làm:** PM, vào ngày kết thúc của milestone.

**Làm ở đâu:** repository cha.

**Prompt**
```bash
gin milestone show <id>
gin milestone create "M2 Cart and checkout" --start 2026-12-01 --end 2026-12-18
gin milestone move <open-epic>... --to <next-id>
gin milestone close <id> --reason "Catalog read path shipped; checkout epic moved to M2"
```
```text
/gin:report --milestone <id>
Question: what did the catalog epics cost, and which of them were reopened or had bugs found later?
```
```text
/gin:progress milestone <id>
Question: which epics are still open, and which tracks block them?
```
```bash
gin milestone kickstart <next-id> --date 2026-12-01
```

Đưa vào prompt: milestone id, và với báo cáo thì là câu hỏi bạn cần trả lời (chi phí, tín hiệu chất lượng, hoặc cả hai).

**Kết quả:** `milestone show` liệt kê các epic đang mở và các cảnh báo; `move` chuyển parent của các epic chưa xong và ghi `{from, to, at, actor}` vào metadata `milestone_moves` của mỗi epic, để lịch sử của một epic bị trượt vẫn đọc được; `close` lưu lý do của bạn làm close reason của bead. `report` cho biết chi phí và mức sử dụng của các epic trong milestone cùng các track của chúng, còn `progress` liệt kê các epic của milestone bằng `gin task list --parent <id>` và trạng thái các track của từng epic. Sau đó bạn chạy `kickstart` cho milestone kế tiếp, và lập kế hoạch nó như trong [Lập kế hoạch milestone](#milestone-planning).

**Cổng hoặc phê duyệt:** `milestone close` bị từ chối khi milestone còn epic đang mở, và `--reason` là bắt buộc.

**Lỗi thường gặp:** đóng một epic chưa xong để milestone đóng được, trong khi lẽ ra nó phải được chuyển; chuyển epic mà không ghi lý do khi close.

## Tùy biến đầu ra { #customizing-outputs }

Mỗi artifact bắt đầu từ một template bạn có thể ghi đè; test case theo `qa/guidelines.md`. Xem [tùy biến template](../guides/customizing-templates.md).

## Biến thể làm một mình { #solo-variant }

Một người đóng mọi vai trò, nên luồng được rút gọn:

- Không có `team-setup`, không có khối `team:`, không có pull request cho các cổng: bạn xác nhận trong chat.
- Các lệnh `milestone` hoạt động như cũ; không có khóa `permissions` thì không gì hạn chế chúng.
- Roadmap: `/gin:roadmap` ghi file sau khi bạn xác nhận và tạo các epic trực tiếp.
- Execute: chọn việc bằng `gin task ready` thay vì `gin team ready`, và bỏ qua claim.
- Mọi thứ còn lại giống nhau: `/gin:discuss <epic-id>`, `plan`, `orchestrate`, `execute`, `ship`.
