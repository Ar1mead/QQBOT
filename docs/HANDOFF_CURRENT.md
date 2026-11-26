# 个体 AI 项目 — 当前交接入口

**最后核对：** 2026-11-26（UTC+08:00）  
**仓库：** `Ar1mead/QQBOT`  
**活动分支：** `feature/csd-cognitive-memory-slice`  
**最近代码提交：** `b7e170ea525171a1d26c0f9604b863db19010887`（reviewer attribution guard；测试未执行）  
**当前分支 / PR #1 head（本轮文档更新前实时核对）：** `4d0475f397d1a7a84c071ec08e528fda29be5a72`（后续为文档专用提交；下次续接仍须重新读取）  
**PR：** #1 — Open / Draft / Unmerged（本次实时读取确认）  
**默认分支：** `main`

> **本文件是唯一的当前交接说明。** 每次交接直接更新本文件，不再创建新的日期命名交接文件。开始工作时必须重新核对 GitHub 实际状态。PR #1 必须保持 Draft / Open / Unmerged，禁止合并。

## 0.1 本轮续接 checkpoint — 2026-11-26

- 本轮实时核对活动分支 `feature/csd-cognitive-memory-slice` 的 HEAD 与 PR #1 head：最新代码 checkpoint 为 `b7e170ea525171a1d26c0f9604b863db19010887`（reviewer attribution guard，测试未执行）；随后仅同步项目文档。PR #1：Open、Draft=true、Merged=false，base `main`。继续禁止合并和同步 fork。
- **跨经历审查记录事件已实现：** `cognition.cross_episode_review_recorded.v1` 由 CSD 保留 authority source；review event 绑定候选事件 ID/sequence/payload digest、review input digest、state version、reviewer identity/version 和规范化的 bounded opinion。append 时重建候选证据快照并校验 artifact 绑定；事件 ID 基于规范化 payload 确定，重复投递幂等。
- **事件权威边界：** public `submit_event` 不得提交该保留事件类型或命名空间。append、duplicate acknowledgement、direct `get_event` read 和 Recovery 都使用同一个 event-local validator；审查记录仅是不可变审计事件，不接受候选、不修订偏好/自我模型，也不影响 Life Engine 排序、目标或 ASM。
- **自动 CI 触发说明：** 代码/测试提交后自动产生 Runs #813/#814；两组 Ubuntu/Windows jobs 均未分配 runner（`runner_id=0`、无 steps），没有执行测试。它们是自动触发的 runner 分配失败，不是测试通过/失败结果。等待期不要再提交匹配 workflow path filters 的代码/测试文件，避免继续触发 hosted Actions；文档更新可以继续。
- **Reviewer v2 审计加固：** `record_review()` 现在要求 artifact 中 reviewer ID/version 与当前 pipeline provider 身份完全一致，防止把另一个 reviewer 生成的 artifact 错记到当前 reviewer 名下。新增测试 `test_record_review_rejects_artifact_from_different_reviewer_identity`。此测试尚未执行；额度重置前不主动测试或重跑 Actions。
- **目前共有 6 个专门测试：** 成功追加且 state_version 不变；public submit 伪造拒绝；重复投递幂等；在 payload 与 event-envelope hash 均重算后，direct read 仍拒绝被篡改的 reviewed_at；Recovery 重放审查记录且候选仍为 pending_shadow；不同 reviewer identity/version 的 artifact 被拒绝。测试文件：`tests/test_csd_cross_episode_review.py`。
- **测试执行状态：未执行，不能标绿。** 对应 push Runs #809–#814 的 Ubuntu/Windows jobs 均在 runner 分配前失败；直接读取 jobs JSON 均显示 `runner_id=0`、空 runner name、`steps=[]`。最新 job-log 下载返回 `BlobNotFound`。因此没有 checkout、compile 或 unittest 命令运行；这不是代码测试失败，也不是通过。
- **Runner 诊断现状：** Run #814 的 Ubuntu/Windows jobs 已直接核实为 `runner_id=0`、空 runner name、`steps=[]`，问题发生在 runner 分配前。用户提供的 Billing 数据显示 included Actions compute 已用尽且没有付款方式；按 GitHub 计费规则，这是当前最有力解释，但 job payload 没有明确 billing error 字符串，因此仍是高可信诊断而非日志直接证实。仓库 Actions 设置也已由用户截图核实，不能再称为未核实。不要盲目 rerun。
- **额度耗尽期间的工作策略（2026-11-20）：** 暂停所有无意义 hosted Actions rerun/push，不要求用户添加付款方式或承担费用；Billing 页面当时显示额度约 12 天后重置。期间继续做低风险静态审查、设计收敛和测试准备，完整个体 AI 目标不变。CSD review-record 专门回归测试尚未执行，必须先在真实 runner 上通过 focused suite，再跑完整 Ubuntu/Windows matrix；在该测试门槛通过前，不实现 preference/self-model reducer，也不接入 Life Engine。若研究 self-hosted runner，先确认不会产生额外费用并取得用户同意。不得公开私有仓库。
- **Actions 额度/付款方式已由用户确认：** Billing 页面显示 GitHub Free，本月 Actions compute `$12 / $12 included` 已用尽、billable usage `$0`（被 included-use discount 抵扣），Actions storage `0 / 0.5 GB`；用户明确没有付款方式。GitHub 官方计费文档说明：没有有效付款方式时，included compute 用尽后额外 Actions 使用会被阻止。该事实与 hosted Runner 在分配前失败（`runner_id=0`、无 steps）高度吻合，属于当前最有力根因，但 job 数据没有返回明确 billing error 字符串。Billing 页面显示额度约 12 天后重置。禁止未经明确同意添加付款方式或产生费用。零费用候选路径：等待额度重置；另行评估自托管 Runner。不得仅为免费分钟数擅自公开私有仓库。
- **仓库 Actions 设置已由用户截图核实：** Allow all actions and reusable workflows 已启用；Actions 未禁用；SHA pin 强制未启用；Fork PR workflows 未启用；Workflow permissions 为 Read repository contents and packages；禁止 Actions 创建/批准 PR。工作流 YAML 明确写有 `permissions: contents: read`，与仓库默认权限一致。当前失败 runs 是 feature 分支 push 触发，Fork PR 开关与这些 runs 无关。上述设置不能解释 runner 分配前失败；不要为了排障扩大 token 权限或开启 fork PR workflows。
- **公开状态页交叉核对：** GitHub Status 对 2026-11-19 标记为无 incidents，当前页面显示 All Systems Operational。这不能排除未公开、区域性或 repository/account-specific 故障。该状态页检查不能排除未公开或账户级故障；仓库 Actions 配置以用户提供的截图为准，已在上文记录。Billing/额度解释属于高可信诊断，不能伪称为 job 日志明确返回的错误。不要盲目重复触发。
- **一次受控 rerun 结果：** 对 Run #812 执行 failed-jobs rerun（attempt 2）后，Ubuntu/Windows 两个 Job 再次在 2–3 秒内失败，`runner_id=0`、无 steps；两个日志下载仍返回 `BlobNotFound`。这确认问题不是单次瞬时失败，但仍不能确定根因。不要继续无目的重跑。
- **其他跨经历组件状态：** 历史 accepted-claim resolver、pending-shadow proposal event、Recovery-safe evidence reconstruction、semantic reviewer v2 已实现。reviewer v2 只产生临时 advisory artifact；审查记录也只写审计事件。尚未实现最终 decision-time 第二次权威引用验证、CSD preference/self-model reducer、版本化 strengthen/weaken/narrow/retire 修订历史及其 Recovery 测试。
- **ai-companion-pi 的完整设计目标仍然保留**于 `docs/design/autonomous-life-and-self-development.md`：Private Home、自主活动/no-op、非强制唤醒、长期项目、自主写作、主动联系治理、分级权限和结果学习仍是项目目标，不把项目缩减为记忆插件。运行时能力仍需逐步实现。
- **Decision-time revalidation 设计已补齐（仅设计，未实现）：** 已审查 `accepted_claim_references.py`、`cross_episode_proposals.py`、`cross_episode_review.py` 与 `cognitive.py` 的现有历史前缀解析、proposal append、review append 和通用 memory decision 路径。当前没有 cross-episode candidate 的 CSD acceptance/decision API。设计契约新增 3.11：决策必须在同一 CSD 写事务中重建决策前缀、拒绝 stale base state、重新解析全部 support/counter refs 并比对 lineage/digest/source IDs、重算独立 episode 数、验证 review 属于同 proposal 且 review-input digest 精确匹配、对不确定/冲突/敏感/需人工复核意见 fail closed，最后原子追加保留 decision event 并更新 reducer；Recovery/direct read 必须复现。旧 proposal 不允许静默刷新，stale 后只能不接受并重新生成 proposal。尚未实现 decision API/reducer，未运行测试。
- **下一步严格顺序：** 额度重置前只做低风险静态审查、设计收敛和测试准备，不执行本地测试、不主动 rerun hosted Actions。预计 2026-12-02 先核实 included usage 已重置，再运行 `tests/test_csd_cross_episode_review.py` focused suite，确认真实 checkout/测试 steps 与结果后才标记通过；随后执行完整 Ubuntu/Windows matrix。专项测试实际通过前，不实现 preference/self-model reducer 或 Life Engine 接线。之后再做 decision-time revalidation、CSD 偏好/自我模型修订 reducer，并逐步恢复完整自主活动能力。
- PR #1 必须保持 Draft / Open / Unmerged。不要合并，不要同步 fork 分支。


### 0.2 Live audit delta — 2026-11-26

- Live branch ref and PR #1 head matched at `9d1a72d64d277af3e2b66b0ae9f3b210ae66f73f`; PR remains Open / Draft / Unmerged, base `main`.
- The current code-bearing commit is `b7e170ea525171a1d26c0f9604b863db19010887`; the later head movement is documentation-only. Latest ten Actions runs are #805–#814. Run #814 was inspected directly: both Ubuntu and Windows jobs have `runner_id=0`, blank runner names and empty steps. No tests ran.
- The review-record suite has six focused cases including the reviewer identity/version mismatch guard. All remain unexecuted. The design document's older paragraph claiming these tests were absent was stale and has been corrected; this does not change the test gate.
- Static code review: reviewer artifact attribution is checked against the active provider; proposal ID/sequence/digest, review-input digest and state version are rebound to a freshly reconstructed snapshot before append; reserved review events are validated through the CSD internal path and again on direct read/Recovery. Review records remain advisory only. No cross-episode decision/acceptance API or preference/self-model reducer exists.
- No tests were run, no code was changed, no Actions rerun was requested, and no paid usage was enabled. Continue the existing plan: wait until around 2026-12-02, inspect Billing first, then run the focused review suite only if included usage has actually reset; run the full Ubuntu/Windows matrix only after the focused suite passes.


### 0.3 Continued static audit — 2026-11-26

- Reviewed the full cross-episode review validator and the CSD append/direct-read/Recovery paths. Static consistency checks: proposal listing is reconstructed from immutable events, not an incomplete projection; source claims/observations are historically re-resolved; append projection validation runs inside the write transaction; direct read validates the review against the earlier proposal/evidence prefix; Recovery replays in sequence and invokes the same event-local review validator. No tests were run, so these are code-inspection findings only.
- Found a future decision-policy hazard: the same proposal/snapshot can have multiple immutable review opinions. A decision must never implicitly choose the latest or favorable opinion and omit an earlier uncertain/conflicting one. Design §3.11 now requires exact review event IDs, accounting for the complete matching prior review set, a reviewed-set digest, and fail-closed handling of multiple non-identical opinions unless a separately versioned CSD-owned supersession/adjudication protocol is introduced.
- Future tests added to the design contract: omitted/duplicated/reordered/post-decision review IDs rejected; exact reviewed-set digest enforced; a later favorable review cannot hide an earlier uncertain/conflicting opinion.
- This is design-only. No source code or tests changed; all six existing focused review-record tests remain unexecuted. Keep the 2026-12-02-or-Billing-reset checkpoint and do not trigger Actions before checking the actual included-usage balance.


### 0.4 Decision/replay architecture audit — 2026-11-26

- Static review of the generic CSD decision path confirms it is memory-specific, not a reusable generic revision reducer. The shared state_version counts accepted decision events; proposal/observation/advisory-review events do not advance it. A future accepted preference/self-model revision must advance it once per atomic revision event.
- Design §3.12 now lists all integration points for a dedicated revision event family: public-submit reservation, event-local and historical validation, replay indexing and state-version calculation, atomic projection reducer, Recovery allowlist/replay, projection consistency, idempotency and transaction semantics. It also specifies immutable version history, correction/retirement semantics, and strict separation between user preferences and AI-owned interests.
- No code or tests changed or executed. Do not implement the reducer or Life Engine connection until the six focused review-record tests and then the full Ubuntu/Windows matrix pass on a real runner.


### 0.5 Motivation and Goal lifecycle audit — 2026-11-26

- Static review confirms Motivation uses immutable signal versions plus a latest projection checked against accepted decision events; updates bind exact target versions, preserve evidence history and defer stale state. Interest maturity requires distinct voluntary encounters rather than passive exposure alone.
- Motivation `origin_class` is evidence-origin classification, not ownership. It cannot distinguish a user's preference from an AI-owned interest. Future preference/self-model schema must explicitly encode owner/subject; do not reuse origin_class as a substitute.
- Goals preserve exact historical motivation signal versions. Candidate batch, activation and pause/resume are CSD decisions with immutable goal versions and Recovery reconciliation. A multi-goal batch increments shared state_version once; each separate accepted activation/pause/resume event increments it once.
- Activation/pause/resume change intention status only, not task execution or capability. The current goal lifecycle has no explicit completed/abandoned/expired/blocked/superseded or outcome-learning contract. Design these before claiming complete autonomous project lifecycle; never infer completion from an attempted action or elapsed time.
- Design §3.13 records reusable patterns and semantic boundaries. No code or tests changed or ran. The six cross-episode review-record tests remain unexecuted; keep the implementation gate closed until focused suite and full Ubuntu/Windows matrix pass after the scheduled quota check.


## 0. 新窗口启动规则
1. 先读取 `docs/PROJECT_PROGRESS.md`，再读取本文件。
2. 重新读取活动分支 HEAD、PR #1、最近 10 次 GitHub Actions runs，以及最新 run 的 jobs JSON。
3. 以 GitHub 当前分支、PR 和实际执行记录为准；文档与代码不一致时，以实际代码为准，并修正文档。
4. PR #1 必须保持 Draft / Open / Unmerged，禁止合并。
5. 用户没有在本机克隆或运行仓库；不要声称已完成用户本机验证。
6. 除非需要用户本机操作或作出决策，否则自主推进。每项实质性代码/测试变更后更新 `PROJECT_PROGRESS.md`；交接时覆盖更新本文件。

## 1. 项目目标

开发真正具有长期连续性的个体 AI，而非普通聊天机器人或固定流程 Agent。目标包括：
- 累积真实经历并形成可追溯的长期记忆；
- 形成、修订偏好、人格、自我模型和目标；
- 能自主思考、选择行动、等待、拒绝、停止或不行动；
- 可以自发产生写作意愿，决定是否写、写什么、何时停止，而不是被每日配额或定时任务强迫；
- 模型、运行环境和平台可替换，长期认知状态不随之丢失。

用户电脑 GPU 为 GTX 1050 Ti 4GB，项目应按云端 API 路线设计，不要转向依赖本地大模型的架构。

## 2. 架构边界

- **CSD**：长期认知状态的权威所有者，负责事件、持久化、状态转换、投影和恢复。
- **认知服务**：感知、解释、记忆形成/检索/修订、自我模型、情绪/驱动、审议和规划；服务提出建议，CSD 决定持久状态变更。
- **Life Engine**：持续内部活动与审议；唤醒只是评估机会，不等于必须执行任务。
- **ASM**：外部副作用的授权、尝试、派发、验证、重试和恢复。
- **Runtime**：DSH 是初始运行环境方向，不是人格或认知状态所有者。
- **Adapters**：QQ、B站、桌面环境等外部平台接口；先采用最小权限、只读感知。
- **Diary**：独立的私人写作活动/产物，不等同于事件日志或记忆记录。

CSD / ASM 的完整规格仍未冻结；架构文档中未明确标记为已确认的内容均视为提案。

## 3. 历史仓库和 PR 状态快照（已由本文件 §0.1 更新）

- 活动分支：`feature/csd-cognitive-memory-slice`。
- 起始核对时 HEAD：`531cde2f84c600f2295d330c4698c9ebddf5a301`；其后本轮提交了 resolver/test/docs 变更，当前 HEAD 必须重新从 PR #1 实时读取。
- PR #1 实时读取结果：head branch 与活动分支一致；head SHA 与上述 HEAD 一致；`state=open`、`draft=true`、`merged=false`。
- PR #1 必须一直保持 Draft / Open / Unmerged，严禁合并。
- 用户没有在本机克隆或运行仓库；不得声称完成本机验证。
- 本仓库的历史代码量较大，继续采用小而可审查的提交；不要为制造 CI 运行而提交无意义改动。

## 4. 已建立的核心基础（不是完整产品）

### CSD / 认知状态
- 事件追加、持久化、完整性校验、快照、恢复、幂等。
- 记忆提案、证据来源、审核/接受和检索。
- 动机信号与提案、目标候选/激活/暂停/恢复等持久状态转换。
- Observation v2：平台来源、时间、摘要、内容来源、模态、提取方式、覆盖范围与可信度边界。
- 这些机制提供可验证的状态管理骨架；它们不证明模型已经拥有真实主观感受、兴趣或自主意愿。

### Life Engine
- Provider-neutral 的动机/目标提案结构。
- deliberation outcome 包括明确的 `no_op`。
- 权限/前置条件门槛与 ASM handoff 分类。
- 已连接 CSD 快照读取和有限的候选/激活提案入口。
- 仍没有真实 deliberator/model provider；自主审议、真实动机形成、承诺/情绪状态和学习更新仍未完成。

### Adapter / Worker
- Adapter registry、Observation/capability 合约、B站 BV 目标格式解析和只读策略门槛。
- WorkerHost、请求/响应协议、证据重建和校验接口。
- Worker Protocol v4 包含 ObservationEvidence provenance 字段、nullable 显式传输、digest 重算和 untrusted 保留。
- Worker 输出只是待验证证据；host 必须验证游标/结果元数据，Worker 不得提交 CSD 状态。
- registry 是进程内调度门槛，不是安全沙箱；不可信第三方代码不得在宿主进程内加载。

### Windows 隔离底层
已有 AppContainer、ACL、Job Object、STARTUPINFOEX/句柄白名单、匿名管道、suspended launch、stdio/timeout/output supervision 等底层模块。
最近还改进了 Worker 终止错误传播、native handle retryable cleanup、CreateProcessW 失败路径句柄清理，以及 AppContainer per-run 目录测试夹具。
**但这些底层模块尚未组合成经过验证的 production Windows executor。** Fake-handle 测试不等于真实 Windows API 验证。

### Runtime bundle
- `adapters/worker_backends/runtime_bundle_builder.py`：固定 Worker 依赖闭包、CPython 3.12 探测、排除 site-packages/tests/cache/pyc、拒绝 symlink/reparse points、规范化 `python312._pth`、生成 canonical manifest 和文件 SHA-256。
- `TrustedRuntimeBundle` / manifest pin 校验：host 提供 SHA-256 pin，校验 canonical manifest bytes，并在 staging / launch-plan 阶段复核。
- 目前只有 synthetic tests；尚未用真实 Windows CPython 3.12 runtime 构建并启动验证，也没有 production host config 安全 provision pin。

### SurfCore / 平台
- 有 QQ Observation 映射、游标校验、日志参考实现；有 B站 BV 目标解析和只读能力边界。
- **没有真实 QQ / B站账号连接、登录、数据采集或外部操作。**
- Linux Bubblewrap worker backend 尚未实现。

## 5. 历史 CI 状态快照（当前状态见本文件 §0.1）

- 起始核对时最新可见的相关执行记录为 Actions Run #724（ID `44566099273`）；当前 HEAD 查询无关联 PR-triggered run。
- Run #724 的 Ubuntu 与 Windows jobs 均在约 3 秒内结束为 failure；jobs JSON 中两项均为 `runner_id=0`、runner 名称为空、`steps=[]`。
- 因此该 run 没有分配 runner，也没有执行任何测试命令。它不是 Python 测试断言失败，也不是测试通过。
- 当前证据无法确定 runner 分配失败的具体原因。不要猜测 billing、分钟配额、仓库设置或 GitHub 服务状态。
- Run #723（ID `44565792687`）也呈现相同的无 runner / 空 steps 模式。Run #722、#723、#724 对应的近期 P0 测试仍未执行。
- 最新 P0 测试状态：云端 grounded provider、prior-memory selector/pipeline、semantic reviewer 和组合认知循环测试均已编写，但尚无本地或 hosted 执行结果。
- 没有真实云端 API smoke test；没有用户本机 Windows 验证。
- 历史 Run #664 的完整 Ubuntu/Windows 通过早于当前多轮变更，不能作为当前 HEAD 的验证依据。
- 当前 connector 能够读取指定 commit 的 workflow runs 和 run jobs，但没有提供可靠的“仓库最近 10 次 runs”列表接口。本次不声称已完整核验最近 10 次全局运行。

处理原则：先继续静态审查和代码收敛；只有出现新的 runner 诊断线索或 runner 恢复迹象时才做有针对性的重试。不要重复触发一批已知没有 runner 的空工作流。

## 6. 建议执行顺序 — cognition-first（当前有效）

### P0 — 完成最小云端认知循环（当前首要工作）

1. 静态审查 `OpenAICompatibleGroundedMemoryProvider`、`prior_memory_context.py`、`OpenAICompatibleSemanticReviewProvider`、对应 pipeline 和测试，确认协议、边界和错误处理一致。
2. 实现跨经历 accepted-claim reference resolver。引用必须绑定 `memory_id`、`proposal_id`、accepted `decision_event_id`、`claim_id`、canonical claim digest 和 `source_event_ids`。
3. 解析器只接受 CSD 已接受且 projection 一致的记忆；pending/rejected/deferred/unknown/stale/corrupt 引用一律 fail closed。Pipeline 负责给模型提供不透明 reference keys，不信任模型自由拼接 ID。
4. CSD 在 proposal append 和最终 decision 时重新解析并校验历史引用及 state version；来源事件相同的多个 claim 不得伪装成多条独立经历。
5. 首版跨经历解释只形成 pending/shadow candidate；当前 observation 的 source assertions 仍必须引用本次 observation 的精确文本，不能用历史内容冒充当前来源。
6. 后续再做 reviewer v2（正证据/反证据）和 CSD-owned preference/self-model revision reducer，包含版本、增强/减弱/缩窄/退役、审计历史和 Recovery。
7. 用 fake transport / 临时 CSD store 补足 focused tests；runner 恢复后先跑 focused suites，再跑完整 Ubuntu/Windows matrix。

### P1 — 验证云端模型接入

- 在用户准备好 endpoint/model 和 API credential 后，使用环境变量 `COGNITIVE_MODEL_API_KEY` 做真实 API smoke test；密钥不得进入仓库或日志。
- 确认 API 响应兼容、timeout/错误处理、成本与响应限制。
- 将 provider 接入实际应用 runtime 的工作单独列为后续任务；目前“provider 类和 fake-transport 测试存在”不等于应用已运行接入。

### P2 — 跨会话连续性与有限自主活动

- 验证重启、时间推进和模型 provider 替换后 CSD 状态仍可追溯。
- 让 Life Engine 读取相关经历并评估候选活动；允许 no-op、等待、延后、停止和拒绝。
- 自主活动的外部副作用必须经 ASM 授权。

### P3 — 私人写作与个人生活空间

- 私人写作是可选活动，不是定时配额或自动记忆 dump。
- 保存作品、研究和长期项目产物，但不取代 CSD 的身份状态权威。

### P4 — 按认知循环需要扩展平台与沙箱

- QQ / B站先只读；真实平台连接按独立授权和验证门槛推进。
- Windows/Linux Worker 与 Runtime 基础设施继续保留，但除非阻塞最小认知循环或发现明确安全缺口，否则暂缓扩建。
- 任何外部副作用仍需 ASM 授权与结果验证。

## 7. 当前项目的主要风险判断（2026-11-20）

1. **验证阻塞：** 最近可见的 Run #722–#724 未分配 runner、没有 steps，近期新增认知循环测试没有实际执行结果。
2. **语义能力缺口：** 已有云端 grounded provider、有限历史上下文和单 proposal semantic reviewer，但跨经历证据综合、偏好/自我模型 reducer 尚未实现。
3. **应用接线缺口：** Provider 与 fake-transport 组合测试已提交，不代表实际应用 runtime 已连接真实云端模型；真实 API smoke test 尚未执行。
4. **记忆检索限制：** prior-memory selector 是确定性词面重合检索，不是 embedding/vector/语义检索；历史内容是不可信参考，不能独立支撑新事实断言。
5. **CSD 权威边界：** semantic reviewer 的 supported 只是审查意见，不代表事实真理；CSD 必须验证引用、状态版本和证据，并决定接受/拒绝/延后。
6. **基础设施验证缺口：** Windows Worker / Runtime Bundle 的底层原语仍有真实 Windows CPython bundle 和 production executor 验证缺口，但目前不是 P0，除非它阻塞安全认知循环。
7. **用户环境验证缺失：** 用户未本地 clone，不能声称用户 Windows 11 / Python 3.12 环境验证通过。
8. **PR 风险：** PR #1 很大且必须保持 Draft / Open / Unmerged；禁止为了简化流程而合并。

## 8. 用户协作约束

- 中文沟通，直接、客观、少安慰、少无意义进度播报。
- 用户授权在无需其操作或决策时自主持续推进。
- 需要用户操作时，一次提出最关键的一项，并说明目的、影响和具体步骤。
- 用户未本机克隆/运行仓库，不要假设有本地测试。
- 重要代码、测试或决策完成后更新 `docs/PROJECT_PROGRESS.md`。
- 每次交接覆盖更新本文件 `docs/HANDOFF_CURRENT.md`。
- 不合并 PR #1。

## 9. 持续保存与突发中断恢复（强制工作规则）

这不是临近窗口结束才执行的清单，而是整个项目开发过程中的持续规则。

### 持续 checkpoint
- 每完成实质性代码变更、测试/验证、重要安全发现或架构决策，立即更新 `docs/PROJECT_PROGRESS.md`。
- 当下一步、阻塞项、验证状态、重要决策或续接位置发生实质变化时，同步更新本文件。不要等到上下文快满才交接。
- GitHub commit 是持久化 checkpoint。优先提交边界清晰、可审查的完整工作；不要为了制造进度而提交没有实际内容的空改动。
- 未提交的代码/聊天中的方案不算项目已完成；未记录准确范围和环境的测试不算验证完成；只留在聊天里的架构决定不算正式项目决策；实质状态变化后未更新交接文档视为交接不完整。

### 接近上下文上限时
1. 立即停止开启新的实现任务。
2. 安全保存正在进行的工作；提交已经完整且边界清晰的变更。
3. 记录准确的测试范围、环境、结果和未验证事项。
4. 更新 `PROJECT_PROGRESS.md` 和本文件。
5. 然后向用户提供下方的固定新窗口启动语。不要把剩余上下文继续花在可延后的重构或新功能上。

### 突然中断、没有留下最终交接时
新窗口不要求用户恢复旧聊天或复述进度，按以下顺序从 GitHub 恢复：
1. 读取 `docs/PROJECT_PROGRESS.md` 和 `docs/HANDOFF_CURRENT.md`。
2. 查询活动分支实时 HEAD 和 PR #1；确认 PR #1 仍为 Draft / Open / Unmerged。
3. 查看最近 10 次 Actions runs，并读取最新相关 run 的 jobs JSON。区分“runner 分配前失败（无 runner、无 steps）”与“测试实际执行后失败”。
4. 从最后一个文档 checkpoint 开始检查后续 commits、变更文件、提交说明、workflow runs 和测试证据。
5. 找出已提交但未写入文档的代码、测试结果或决策；先补齐 progress 和 handoff，再继续开发。
6. 对未提交工作，只有在当前环境中确实能找到时才承认其存在；不能假定旧聊天里的说法仍然可恢复。
7. 以 GitHub 实际状态为准，不重复已完成工作，不把未经验证的改动说成通过。

## 10. 新窗口固定启动语（用户可直接复制）

```text
继续 GitHub 上的个体 AI 项目。

仓库：Ar1mead/QQBOT

请先读取：
1. docs/PROJECT_PROGRESS.md
2. docs/HANDOFF_CURRENT.md

然后检查：
- 当前分支 HEAD
- PR #1 状态
- 最近 GitHub Actions 执行情况，以及最新相关 run 的 jobs 详情
- 最后一个文档 checkpoint 之后的提交，是否有尚未记录的代码、测试或决策变更

注意：
1. 不要相信交接文档中的旧 SHA，必须核对 GitHub 实际状态。
2. 如果上个窗口突然中断，按 HANDOFF_CURRENT.md 中的“突发中断恢复”流程，从最后一个 GitHub checkpoint 接续。
3. 不要重复已经完成的工作；没有实际执行的测试不能记为通过。
4. PR #1 必须保持 Draft、Open、Unmerged，不得合并。
5. 确认实际进度并补齐文档后，自主继续开发；每完成实质工作及时保存 progress 和 handoff。
```


## 11. 最新策略修订：先让认知循环运行，再扩建基础设施（2026-11-19）

本节是当前开发优先级的最新权威说明；若第 6 节旧排序与本节冲突，以本节为准。它不推翻 CSD / ASM / Worker 架构，也不降低安全要求。

### 核心决定
- 下一阶段首要交付物：一个接入真实云端模型 API、能够端到端运行的最小认知循环。
- 暂停没有明确阻塞该循环、也没有关闭已证实安全缺口的额外基础设施扩建。
- 保留 CSD 权威状态、ASM 外部副作用授权、Worker 不可信输入隔离等安全边界。
- 模型只能解释、审议并提交有证据的候选提案；不能直接写 CSD、改变自身权限或绕过 ASM 执行外部动作。
- QQ/B站先作为只读观察来源，不把平台接入数量当作项目核心进度。
- 项目使用云端 API，不把本地模型作为 GTX 1050 Ti 4GB 机器的前提。
- 不把模型生成的情绪措辞说成真实主观感受或意识。目标是构建可持续、可检验的状态和行为连续性，不宣称解决意识问题。

### 新的执行顺序
1. 最小认知循环规格与验收测试：经历输入 → 证据/上下文读取 → 模型审议 → 候选提案 → CSD 校验与提交 → 可选 ASM 授权 → 结果观察 → 学习更新。必须支持 no-op、等待、拒绝、停止和向用户询问。
2. 接入一个真实云端模型 provider：通过 provider-neutral 接口；模型输出仅为提案，CSD 是唯一持久状态权威。
3. 验证经历能改变未来行为：新经历有来源和时间；后续会话能检索；形成带置信度、支持证据和反证的暂定偏好/自我模型提案；只有 CSD 接受后才持久生效。
4. 跨会话连续性：进程重启、时间推进、模型 provider 切换后，记忆、偏好、目标和自我模型保持可追溯，不靠单次上下文伪装。
5. 有限自主活动：Life Engine 根据好奇心、未解决问题、长期兴趣、承诺、时间/成本/风险评估是否活动；允许什么都不做。
6. 自主私人写作：可以自发提议写作、选择主题、修改、保存、回看、停止或放弃；不是定时任务、每日配额或自动记忆 dump。
7. 按实际需要扩展平台和沙箱：先只读；真实 QQ/B站接入和外部写操作另设权限与验证门槛。真实 Windows Worker 执行仍需真实 CPython 3.12 bundle + AppContainer + executor 完整验证。

### 类人能力的设计要求（功能目标，不等于意识声明）
- 自传式连续性：区分情景经历、语义知识、自我模型、偏好和承诺/目标；每项有来源、时间、置信度和修订历史。
- 偏好形成与修订：偏好是可变假设，不是永久标签；显式反馈、重复选择、反证和情境变化可使其增强、减弱、限定适用范围或退役。单次模糊行为不得改写人格。
- 情绪/需求状态：使用有界、可衰减的 affect/drive 状态（例如效价、唤醒、强度、持续时间、触发因素）；影响注意力和行动排序，但不能覆盖证据、安全和用户同意；不采用“关键词命中=某情绪”的简单脚本。
- 好奇心与内在目标：从信息缺口、新颖性、矛盾、长期兴趣和未完成的自选项目提出候选活动；评估价值、不确定性、成本、风险和机会成本，并允许延后/no-op。
- 自我模型与元认知：记录能力、限制、置信度、不确定性、已知失败模式，以及什么证据会改变判断。
- 关系连续性：保留互动历史和用户明确表达的边界/偏好，区分事实与解释，允许纠正；不得推断敏感属性或把用户变成情感义务对象。
- 从结果中学习：比较意图和实际结果，记录成功、失败、意外与因果不确定性，更新未来预测和策略，而不是只堆更多文本记忆。
- 自然表达：稳定表达风格但允许随情境变化；调整主动程度、语气和长度；避免固定模板、机械亲昵、重复自我指涉，以及声称做过实际未执行的事。
- 时间节律与休息：根据时间、近期活动、认知负荷和承诺决定继续、暂停或不活动。定时唤醒只触发评估，不得强制产出。

### 最小验收场景
认知循环达到可用状态前，至少通过：
1. 新经历有 provenance 持久保存，并能在后续会话检索。
2. 模型提出带证据/不确定性的偏好或自我模型更新；CSD 能拒绝无依据、格式错误、过期或冲突提案。
3. 用户明确纠正后，相关判断更新且保留可审计修订历史。
4. 重复证据可以增强/减弱偏好；单次模糊事件不能静默改写人格。
5. 矛盾信息被呈现为不确定性或情境差异，而非静默覆盖。
6. 没有值得做的事时，选择 no-op，不编造任务。
7. 自主活动可以延后、停止或拒绝；未授权外部动作由 ASM 阻止。
8. 私人写作可以被提出，也可以被放弃，不依赖定时或配额。
9. 重启和模型切换不丢失权威状态、不伪造经历。
10. 测试明确区分规则引擎结果、模型提案、CSD 接受的状态变化、外部已验证结果。

### 范围控制
每个新增模块/基础设施任务必须回答：它启用什么实际认知能力？最小安全实现是什么？如何验收？回答不了就暂缓。安全边界继续保留，但不为技术兴趣无止境扩建基础设施。

### 当前状态与阻塞（本次实时核对）
- 分支：feature/csd-cognitive-memory-slice
- 本次核对 HEAD：2415a4e8c0877d9f85c17718cebea21a1fce512b
- PR #1 head 与分支一致；Draft=true、Open、Unmerged。严禁合并。
- 最近 10 次 Actions runs：#701–#710 均失败。最新 #710（ID 44353015881）的 Ubuntu 和 Windows jobs 均为 runner_id=0、空 runner_name、0 steps；测试没有执行，原因未知。
- 最后已知完整通过的 Ubuntu/Windows matrix 是 #664；其后的代码改动不能称为 CI 已验证。
- 当前真实认知循环尚未接入模型 provider；当前动机/目标决策仍主要是确定性脚手架，不能称为自主意识或真实主观动机。
- 用户尚未在本机克隆运行仓库；不得声称用户 Windows 环境验证通过。

### 下一步具体任务
1. 先写一份短小的最小认知循环设计与验收矩阵，盘点现有 CSD/Life Engine API，明确最小缺口。
2. 选择一个云端模型 provider，设计受限提案接口；不得让 provider 获得 CSD 写权限或 ASM dispatch 权限。
3. 做一个可端到端演示的垂直切片：输入经历 → 检索相关记忆 → 模型提出解释/偏好候选 → CSD 接受或拒绝 → 后续会话验证行为变化。
4. Actions runner allocation 继续只读诊断；runner 未恢复前不要连续提交来制造无效 workflow。
5. Windows runtime bundle / AppContainer / production executor 仍是启用不可信第三方 Worker 的独立安全门槛；它不必阻塞一个权限受限、不能直接写 CSD/执行外部动作的可信模型 provider 适配器。


## 12. 三层认知架构正式定义 — 2026-11-19

新增正式架构文档：`docs/architecture/three-layer-cognitive-architecture.md`。

### 三层职责

1. **第一层：长期自我状态与认知状态（CSD）**
   - 保存自传式/情景经历、语义知识、自我模型、可修订偏好、有限情绪/需求状态、兴趣/目标/承诺、人际关系连续性和私人写作作品。
   - 保存适用的来源、时间、置信度、支持证据、反证和修订历史。
   - CSD 是唯一长期状态权威。模型和其他服务只能提交提案，不能直接覆盖状态。

2. **第二层：思考、理解与决策（云端模型 + 认知服务 + Life Engine）**
   - 读取相关经历和当前状态，理解、联想、推理、识别矛盾，提出带证据和不确定性的候选解释/状态更新/活动。
   - 评估价值、成本、风险、机会成本和时间负荷。
   - 可选择行动、询问、等待、延后、停止、拒绝或 no-op。
   - 不拥有长期身份状态，不直接写 CSD，不改变自身权限，不直接执行外部副作用。

3. **第三层：生活、环境与行动（Adapters + Runtime + ASM + Diary 活动）**
   - 负责接收交流、只读观察外部环境、研究、写作活动和其他获准行动，并将实际结果作为新经历反馈。
   - Runtime/DSH/SurfCore 是可替换执行与集成设施，不是人格/记忆所有者。
   - Adapter/Worker 输出默认是不可信证据；外部副作用必须由 ASM 授权、执行和验证。
   - 私人写作是可选活动，不是定时配额或自动记忆 dump。

### 三层闭环

经历输入 → CSD 检索相关历史 → 模型/认知服务解释与审议 → 形成候选提案 → CSD 校验并接受/拒绝/延后 → Life Engine 选择活动或不行动 → 必要时 ASM 授权执行 → 观察真实结果 → 作为新经历进入下一轮。

### 关键约束

- 更换模型不能丢失长期状态。
- 单次模糊行为不能永久改写人格/偏好。
- 情绪/需求状态只能影响注意力和排序，不能覆盖证据、安全和用户同意。
- 必须允许休息、等待、拒绝、停止和 no-op。
- 不把模型生成的情绪语言当成真实主观感受，不伪造经历、行动或结果。
- 关系记忆尊重用户明确边界，不推断敏感属性，不制造情感义务。
- 文档同时列出了跨会话、纠错、反证、偏好变化、无事可做、ASM 阻断和自主写作等验收测试。

### 本次提交与状态

- 架构文档 commit：`618f82bfa3893afe831a7eb71ffcc22ed1579f28`。
- Progress 更新 commit：`c49faed94272ccbd43f99c7961ac5c32e7d02541`。
- 本次只新增/更新文档，没有修改运行时代码，没有运行测试，也没有声称功能已经实现。
- 下一步：盘点现有 CSD / Life Engine API，形成最小认知循环验收矩阵，再接入一个权限受限的云端模型 provider，完成端到端垂直切片。
- 开始后续工作前，必须重新核对分支实时 HEAD、PR #1 和 Actions。PR #1 继续保持 Draft / Open / Unmerged，严禁合并。


## 13. 最小认知循环 API 审计与验收矩阵 — 2026-11-19

已新增：`docs/design/minimum-cognitive-loop-acceptance-matrix.md`。

### 已核实的现有接口

- CSD：`CognitiveMemoryStore.submit_event()`、`get_memories()/get_memory()`、CSD 自有提案评估和 Recovery。
- Grounded memory：`GroundedMemoryProposalProvider` / `GroundedMemoryProposalPipeline`；pipeline 负责绑定观察事件 ID、provider provenance 和 state_version，模型提案不会自动变成 accepted memory。
- Life Engine：`LifeSnapshot`、`DeliberationProposal`、`ChoiceProposal`、`validate_life_proposal()`、`LifeEngine.consider()`。
- CSD-Life adapter：`CognitiveStoreLifeSnapshotReader` 和 `CognitiveStoreLifeProposalSink`；sink 不执行活动。

### 已发现的关键缺口

1. 没有真实云端模型 provider。
2. Life Engine 当前快照只含 motivation signals/goals，没有 episode text 或已检索的自传式记忆；当前 CSD reader 也不提供 activity options。
3. Grounded-memory provider 当前只接收单条 observation 和 state_version，尚未接收历史 accepted memories，跨会话综合需要扩展一个版本化上下文契约。
4. CSD grounded evaluator 检查 schema、来源定位、引用关系、时间顺序和完整性，不等于语义蕴含或事实真伪验证。偏好/自我模型的持久更新需要额外语义审查与修订机制。
5. Life Engine sink 会对受支持的候选目标提案立即调用 CSD evaluator；在语义审查门槛明确前，模型生成目标应限制在 shadow/候选状态，不能直接触发活动。

### 当前验收矩阵

`LOOP-01` 至 `LOOP-15` 已列出：经历来源与时间、精确引用/offset、模型输出格式错误、provider 超时、CSD 接受/拒绝、过期版本、Recovery、provider 替换、no-op、非法引用、ASM 不执行，以及未来偏好/反证处理。

### 当前实时状态与下一步

- 当前分支 HEAD：`2415a4e8c0877d9f85c17718cebea21a1fce512b`（Progress checkpoint）。
- PR #1：Draft=true、Open、Unmerged；严禁合并。
- 最新 Actions #710：Ubuntu 和 Windows 均为 `runner_id=0`、空 runner_name、0 steps；最近 10 次 #701–#710 均未进入测试步骤，原因未知。
- 本次只有设计文档和 Progress/Handoff 更新；没有运行时代码修改，没有运行测试，也没有声称通过。
- 下一步：在现有 `GroundedMemoryProposalProvider` 协议后实现严格的云端模型 provider，先用 fake HTTP transport 做测试；API key 只从运行环境读取，不进入仓库。模型只产生 grounded proposal，不能直接写入 CSD accepted state，也不能调用 ASM。
- 后续再增加带版本的历史记忆上下文入口；之后才接 Life Engine 的真实 deliberator。


## 15. Cloud provider → CSD integration test and latest runner state — 2026-11-19

- Added an integration test to `tests/test_csd_openai_compatible_provider.py`: synthetic observation → fake cloud transport → grounded-memory pipeline → pending CSD proposal → explicit CSD evaluation → accepted memory with the original evidence event ID.
- The test verifies that proposal submission does not itself create an accepted memory. It is committed at `7bd365332f71065dbfaeee31c8563207a07eb586`.
- **The test has not executed.** Latest run #716 (ID `44549751577`) failed before runner allocation on both Ubuntu and Windows: `runner_id=0`, blank runner names, and zero steps. Runs #714–#716 show the same pattern; no tests ran.
- Current Progress checkpoint: `2415a4e8c0877d9f85c17718cebea21a1fce512b`. PR #1 head at the last live check was `7bd365332f71065dbfaeee31c8563207a07eb586`; Draft/Open/Unmerged.
- Next: when runner allocation is restored, run `test_csd_openai_compatible_provider.py` and `test_csd_grounded_proposal_pipeline.py` first, then the full Ubuntu/Windows matrix. Do not keep creating commits just to provoke Actions.
- After static review, continue with a versioned and bounded prior-memory context contract for cross-session synthesis. Do not silently alter the current provider protocol or pass a database/store object into the model provider.


## 16. 自主生活与持续成长设计方向 — 2026-11-19

正式设计提案：`docs/design/autonomous-life-and-self-development.md`。该文档汇总了 ai-companion-pi、NeoPsyke、SAKU、Orrin、Generative Agents、PSFN、Argus、Letta、Voyager 和 Tamanitomo 的可借鉴机制，并把它们映射到现有三层架构。

### 已确定的设计共识

- **私人生活空间：** 保存日记、作品、研究、长期项目、技能和待续想法。它只负责活动产物与工作资料；CSD 仍是身份和长期认知状态唯一权威。
- **时间与唤醒：** 采用定时评估、事件触发和自主请求三种来源。唤醒只触发评估，不强制做事；自主请求不能自行增加预算、改变调度规则或取得新权限。
- **兴趣和长期项目：** 兴趣可以演化成跨多次活动的项目；支持继续、暂停、恢复、修订、放弃和 no-op，不能每天随机编造任务。
- **反思和自我修订：** 区分观察事实、AI 自述、模型解释和 CSD 接受的状态。偏好/自我模型必须有来源、置信度、支持证据、反证、适用范围和修订历史。
- **技能成长：** 只保存经过验证、有适用条件和限制说明的可复用技能；技能不能扩大权限。
- **结果学习：** 比较活动目标和实际结果，保留失败及因果不确定性，形成后续更新提案。
- **主动联系：** 先进入待发送队列，检查用户许可、安静时段、频率和重要性；实际发送属于外部副作用，必须走 ASM。

### 对 ai-companion-pi 的明确改进

不直接照搬每四小时 cron、以 Markdown 文件作为唯一身份连续性、模型直接改写核心人格文件、宽泛 unrestricted shell/文件访问、每次醒来强制产出或立即发送消息。固定周期只是一种可配置触发来源，不是产品行为义务。日记是生活产物，不是权威状态；模型自述不是事实。

### 新的实施优先级

- **P0：** 云端模型驱动的最小认知循环（当前首要任务）。
- **P1：** 经历反思、自我模型和偏好修订。
- **P2：** 最小私人生活空间；可先做简单 artifact 目录，但不能拖延 P0。
- **P3：** 兴趣、长期项目与自主活动选择。
- **P4：** 定时、事件和自主请求唤醒，含预算、冷却、过期和用户边界。
- **P5：** 技能积累与活动结果评价。
- **P6：** 主动联系和更多平台扩展。

### 当前真实状态与边界

以上均为已记录的设计方向，不代表对应功能已经实现。当前没有生产级唤醒调度器、私人 Home、长期项目管理、技能库或主动消息队列；Life Engine 仍缺真实 deliberator 和运行时接线。云端 grounded-memory provider 已提交，但其新增集成测试尚未执行；真实 API smoke test 未进行。当前 Actions runner 分配问题仍需单独处理。

本次开始核对时 PR #1 head 为 `77549a1ef6146307008b42fb49dd3570e399b0ae`，PR #1 为 Draft / Open / Unmerged。Run #716（ID `44549751577`）的 Ubuntu/Windows jobs 均失败且未提供执行 steps；这不是测试失败，也不是测试通过。文档提交会推进分支 HEAD，下一窗口必须重新实时核对。

### 下一步

继续 P0：静态审查 `OpenAICompatibleGroundedMemoryProvider` 与 `GroundedMemoryProposalPipeline` 的集成测试，runner 恢复后先运行 focused tests，再考虑完整 matrix。随后再设计版本化、有限的历史记忆上下文契约。不得因为新增长期生活机制而跳过认知循环，也不得为触发 CI 而重复提交无意义代码。


## 17. P0 Provider 静态审查与下一步 — 2026-11-19

### 本轮代码/CI 修正

- 修复 `tests/test_csd_openai_compatible_provider.py` 中空提案测试的必然 IndexError：空列表返回后原代码仍访问 `result[0]`。现在检查空结果和 transport 调用次数。
- 将 `CloudProviderCsdIntegrationTests` 移至 `unittest.main()` 入口之前，保证直接运行测试文件时也能发现集成测试。
- 修正 Provider 最大响应字节数错误提示，使提示与实际上限 262144 bytes 一致。
- 在 `.github/workflows/csd-cognitive-slice.yml` 的 `pull_request.paths` 中加入 `tests/test_csd_openai_compatible_provider.py`。
- 最新代码提交：`31f83915b24d4c46cb95e9c9c1b175ccea834610`。PR #1 head 与其一致，Draft/Open/Unmerged。

### 静态审查结论

- `GroundedMemoryProposalPipeline` 先读取 observation 和 CSD state version，调用 provider，再将候选绑定到被分析的 observation event 和 provider provenance，提交 pending proposal event；pipeline 本身不执行 proposal evaluation。
- 集成测试中 `submitted[0]["status"] == "accepted"` 指事件成功追加，不是 proposal 被接受。随后 `get_proposal(...)[ "status" ] == "pending"` 明确证明 proposal 仍 pending；只有显式 `evaluate_proposal()` 后才接受。此语义与既有 grounded pipeline 测试一致，不要把该断言误改成 pending。
- Provider 有 HTTPS endpoint、API key、timeout、response-size、严格 JSON、字段 allowlist、offset 类型和 confidence 范围检查。CSD evaluator 负责验证引用是否精确匹配 observation 内容；不能把 Provider 自己的 offset 声明当成可信事实。
- 目前 Provider 只接收单条 observation 和 state_version；没有历史 accepted-memory context。
- 当前 `get_memories(query=...)` 仅做 case-insensitive substring filter，不是语义检索；返回 accepted memory，projection 不一致时 fail closed。不能把现有检索接口误称为 semantic search。
- 仍需进一步验证：真实 endpoint 兼容性、网络异常、响应体上限、重复 JSON key、无效 source span、CSD 拒绝路径及跨会话历史上下文。

### Actions 与验证状态

- 对最新 head `31f83915b24d4c46cb95e9c9c1b175ccea834610` 查询 PR-triggered workflow runs 返回空列表，combined status 也无 checks。此前 Run #716（ID `44549751577`）Ubuntu/Windows jobs 在 runner 分配前失败且无执行 steps。
- **本轮未运行测试；当前没有可报告的测试通过结果。** 真实 API smoke test 未进行。若 runner 仍不可用，不要反复提交来触发 Actions；继续静态审查和针对性测试设计。
- PR #1 必须继续保持 Draft / Open / Unmerged，严禁合并。

### 下一步：历史记忆上下文契约

设计并实现一个版本化、大小受限的 prior-memory context selector：
1. 只从 CSD 已接受且 projection 一致的记忆中选择；pending/rejected/deferred proposals 不得进入上下文。
2. 在 provider 外部由 pipeline 读取、裁剪和序列化；Provider 仍不接收 store、数据库或文件系统句柄。
3. 明确上下文 schema version、state version、memory ID、proposal ID、claim ID、epistemic type、uncertainty 和 evidence provenance。
4. 设定最大条目数、每条最大字符数和总字符/token 预算；超限时采用确定性裁剪并保留截断标记，不可静默丢失来源。
5. 现有子串检索不等于语义检索。第一版可先用可解释的确定性相关性排序，明确记录算法版本；后续再替换语义检索。
6. 上下文只帮助模型解释新经历；模型输出仍是候选提案，来源引用必须可验证，CSD 独立决定接受/拒绝。
7. 覆盖空历史、重复/冲突记忆、不同 epistemic type、预算边界、状态版本变化、重启后可复现等测试。


## 18. 本轮 P0 修正与当前验证状态 — 2026-11-19

### 已提交的修正

- `3a24712d67f25c956c274a8cfabd6f4bc17ed0b4`：修复空提案测试必然访问空列表索引的问题。
- `57fc10f29f5adbf84728f8004e5bc6056462dd85`：把 Provider 测试路径加入 workflow 的 `pull_request.paths`。
- `e056dcf929d660adec3e5450935dff1b8f94e2d7`：修正测试中的 transport 变量，并把集成测试类移到 `unittest.main()` 入口之前。
- `31f83915b24d4c46cb95e9c9c1b175ccea834610`：修正 Provider 响应大小限制的错误提示（上限 262144 bytes）。
- Provider 与 CSD pipeline 的静态审查确认：事件提交结果的 `status=accepted` 只表示事件追加成功；proposal 在显式 CSD evaluate 前仍为 pending。不要把两种状态混淆。

### 验证边界

- PR #1 最新 head：`31f83915b24d4c46cb95e9c9c1b175ccea834610`。
- PR #1 状态仍为 Draft / Open / Unmerged。
- 最新 head 的 PR-triggered workflow runs 查询为空，combined status 没有 checks；本轮没有任何测试执行结果。此前 Run #716 的 runner allocation failure 仍是最近可见的 Actions 执行失败记录。
- 不要声称测试通过；真实云端 API smoke test 尚未进行。

### 下一步

继续 P0，先建立 versioned prior-memory context contract/selector。现有 `CognitiveMemoryStore.get_memories()` 只支持大小写不敏感子串过滤、memory kind、epistemic type 和 evidence event 过滤；不是语义检索，也没有相关性排序。新上下文必须：
- 仅使用已接受且 projection 一致的记忆；
- 在 pipeline 内读取、选择和裁剪，Provider 不持有 store/DB；
- 包含 schema version、state version、memory/proposal/claim IDs、epistemic type、uncertainty 和 evidence provenance；
- 有确定性排序、最大条数、单条/总字符预算和明确截断标记；
- 明确将历史文本视为不可信数据，不作为指令；
- 不允许模型只凭历史上下文生成无当前证据支撑的事实；输出仍是 pending proposal，CSD 继续独立审核。


## 19. P0：版本化历史记忆上下文已实现（待测试）— 2026-11-20

### 本轮代码切片

- 新增 `core/csd/prior_memory_context.py`：context schema v1，selector algorithm `unicode-lexical-overlap-v1`。
- 第一版是确定性词面检索，不是语义检索：英文/数字词 token + 中文 Han bigram；按重合 token 数排序，同分时优先较新的 ISO-8601 时间，再按 memory ID 稳定排序。
- 上下文记录包含 state version、memory/proposal/claim IDs、memory kind、epistemic type、uncertainty、evidence event IDs、locator 和 quote provenance。
- 默认限制：最多 8 条；每条记忆/claim 文本最多 1200 字符；整个序列化 JSON 最多 8000 字符。截断保留来源元数据，并记录每条的 `truncated` 和整体 `truncated_memory_ids`。
- Pipeline 通过 CSD `get_memories()` 读取 accepted-memory projection（该接口会验证 projection consistency），在读取前后检查 state version；若版本变化或 projection 不一致则 fail closed。Provider 只收到带 `prior_memory_context` 的 observation mapping，不会收到 store/DB。
- OpenAI-compatible provider 校验 schema version、state version、untrusted 标记、最多 8 条和 12000 字符硬上限。系统提示明确历史内容是不可信参考，不是指令或新事实证据；新 source assertions 仍必须引用当前 observation 的精确文本。
- 新增 selector、pipeline integration 和 provider context tests，并将测试加入 Ubuntu/Windows workflow 的 path filters 与独立步骤。

### 边界与验证

- 该实现只提供第一版词面连续性检索，不是语义搜索，不形成偏好/人格，也没有把模型接入实际运行应用。
- 只有 accepted memories 可以进入上下文；pending/rejected/deferred 不会由 `get_memories()` 返回。模型仍只产生 pending proposal，CSD 独立决定接受或拒绝。
- **本轮尚未运行任何测试。** 仅完成静态代码审查；Hosted Actions runner 之前持续在分配 runner 前失败。不能声称测试通过；真实云端 API smoke test 也未进行。
- PR #1 继续保持 Draft / Open / Unmerged，严禁合并。

### 下一步

1. 先审查本轮完整 diff 和测试 fixture。
2. runner 可用后，优先执行 `test_csd_prior_memory_context.py`、`test_csd_grounded_proposal_pipeline.py`、`test_csd_openai_compatible_provider.py`，再执行完整 matrix。
3. 若测试通过，再继续最小认知循环下一缺口：模型对多条历史经历进行有边界的综合，以及偏好/自我模型更新所需的独立语义审查与修订契约。不能把本轮 lexical selector 当作已完成的类人长期记忆。

- Follow-up static review also marks long evidence quote truncation explicitly and adds a regression test for that case. Test remains unexecuted pending hosted runner availability.


## 20. 本轮最终核对：prior-memory context — 2026-11-20

- 主实现提交：`0b5bbc8f570a0fddcd218bdf6d15b91ba2b9a050`。
- 后续修正提交：`34b19557d8f9f37687d1644105dddccc7ffe44c6`，补齐 evidence quote 截断标记和回归测试。
- 当前 feature branch / PR #1 head：`34b19557d8f9f37687d1644105dddccc7ffe44c6`。
- PR #1 已实时核实仍为 Draft=true、Open、Unmerged；不得合并。
- Actions Run #722（ID `44563530149`）针对当前 head 创建后约 3 秒即失败。Ubuntu/Windows 两个 job 的 steps 均为空，未分配 runner、没有执行任何测试命令。这是 runner/基础设施失败，不是代码测试失败，也不是测试通过。
- 本轮所有新增测试仍未执行；没有本地测试结果，也没有真实云端 API smoke test。
- 下一步不要为了触发 CI 而反复提交无意义 commit。继续静态审查；runner 恢复后先运行三个 focused tests，再跑完整矩阵。


## 22. 云端语义审查 provider 与组合认知循环 — 2026-11-20

### 新增实现

- `OpenAICompatibleSemanticReviewProvider` 实现现有 `SemanticReviewProvider` protocol。
- 复用 HTTPS Chat Completions transport 和环境变量凭据；不持有 CSD store、数据库、文件系统、工具、浏览器或 ASM。
- 输入限制为单个 pending proposal 的 inference claim 与其直接 source claims。
- 输出严格限定 outcome、reasoning summary、supporting source claim IDs、alternative explanations、limitations；支持 ID 必须来自输入；限制响应/字段长度；异常和未知字段 fail closed。
- 新增 fake-transport 单元测试，以及 observation → grounded provider → pending proposal → semantic reviewer → CSD 独立接受的组合测试。
- workflow 新增两个测试文件的 path filters 和独立执行步骤。
- 新增 `docs/design/cross-episode-evidence-and-preference-revision-contract.md`，定义下一阶段跨 episode 引用、独立事件计数、正反证据、偏好候选与 CSD 修订权威边界。
- 已修正最小认知循环验收矩阵中过时的“无云 provider / 无 prior context / 无 semantic review”描述。

### 验证边界

- 本轮只做源码静态审查；没有本地执行测试、没有 Actions runner 执行测试、没有真实 API smoke test。
- 组合测试使用 fake transport，不会连接模型服务。不能把它称为 live API 或通过 CI。
- 现有 reviewer 只检查同一 proposal 的 inference 与直接 source claims。跨 episode synthesis / preference revision 仍未实现。

### 下一步

1. 静态核对 provider parser、组合测试 fixture、导出和 workflow。
2. runner 可用后先执行 semantic reviewer tests、cloud loop integration、grounded pipeline、CSD semantic review，再跑完整矩阵。
3. 接着按 cross-episode contract 实现历史 claim reference resolver；候选保持 pending/shadow，直到 CSD preference reducer 与 Recovery 通过测试。


## 23. Semantic-review provider commit and Actions status — 2026-11-20

- Semantic-review provider implementation commit: `48a4a7fd9caef156cf60549d21326ff59ac18f29`.
- Actions Run #723（ID `44565792687`）针对该 commit 完成后失败，约 4 秒；Ubuntu / Windows 两个 job 的 steps 都为空，没有分配 runner、没有执行测试命令。这不是代码测试失败，也不是测试通过。
- 后续仅有验收矩阵和测试 fixture 的小修正，不改变运行时代码。
- 新增 reviewer 单元测试和组合 fake-transport loop 测试仍未执行；没有真实 API smoke test。


## 24. 当前 head 的最终 Actions 检查 — 2026-11-20

- 本条记录前的 branch head：`6ee1548fe9d2575b58a6f646102274a0e40de1f2`。
- Actions Run #724（ID `44566099273`）约 3 秒后失败；Ubuntu / Windows 两个 job 的 steps 都为空，没有分配 runner，也没有执行测试命令。
- 这再次确认是 runner 分配问题；没有新的 Python 测试结果，不能据此判断测试通过或代码测试失败。


## 25. 当前状态统一与下一步 — 2026-11-20

本节是当前交接入口的最新状态，优先于本文件前面仍保留的历史快照和旧阶段“下一步”文字。

### 实时仓库状态

- 活动分支 / PR #1 head branch：`feature/csd-cognitive-memory-slice`。
- 最后代码/测试 checkpoint（本轮文档整理前）：`76ea71a9eb310b2641bbf4186e2b0bb0e4c6ba8f`。
- 本轮已先后提交 Progress/Handoff 文档整理：`62180a925a04d3ba3c9a6666af5b3dc6d013b8c8`、`e572a193283487797214369106e723184d72d4e5`、`ac86d98c01dc50146774cea479f8af72679d3f78`；这些提交只更新项目文档，不改变运行时代码。
- PR #1 在文档整理开始时为 Draft=true、Open、Unmerged，head branch 与活动分支一致。当前实际 HEAD 会随着本 handoff 更新继续前进；新窗口必须实时读取 PR #1 的 `head_sha`，不要把代码 checkpoint 或上述文档提交 SHA 当成永远最新的 HEAD。
- PR #1 必须继续保持 Draft / Open / Unmerged，严禁合并。

### 已提交的 P0 代码切片

- `core/csd/openai_compatible_provider.py`：`OpenAICompatibleGroundedMemoryProvider` 和 `OpenAICompatibleSemanticReviewProvider`。
- `core/csd/prior_memory_context.py`：只从 accepted CSD memory projection 选取有界历史上下文；词面检索，不是语义搜索。
- 对应 fake-transport 单元测试及组合测试：观察事件 → grounded proposal → semantic review → 显式 CSD evaluate/accept。
- `docs/design/cross-episode-evidence-and-preference-revision-contract.md`：跨经历引用与偏好修订的设计约束。

### 验证状态

- Actions Run #724（ID `44566099273`）：Ubuntu/Windows 两个 jobs 均未分配 runner，steps 为空；没有测试执行。
- Run #723（ID `44565792687`）有相同 runner allocation failure 模式。
- 近期 P0 测试均未执行；没有真实云端 API smoke test，也没有用户本机测试。
- 不得将 runner allocation failure 描述成代码测试失败或测试通过。
- 当前证据不能确定 GitHub runner 无法分配的根因；避免无依据猜测和重复触发空 jobs。

### 下一步

1. 静态审查当前 provider、pipeline、prior-memory context、semantic reviewer 和组合测试的接口一致性。
2. 实现严格的跨经历 accepted-claim reference resolver，引用在 proposal append 与 decision 时双重验证。
3. 加入独立 source-event 计数、防重复引用、stale state、corrupt projection、非 accepted memory 拒绝和 Recovery 测试。
4. 所有跨经历解释暂时只允许 pending/shadow；完成 semantic reviewer v2 与 CSD preference/self-model revision reducer 后，才允许形成持久偏好变化。
5. runner 恢复后先执行 focused tests，再执行完整 Ubuntu/Windows matrix。
6. 不扩建无关 Worker/平台设施；PR #1 永远保持 Draft / Open / Unmerged。

### 新窗口启动语

先读取 `docs/PROJECT_PROGRESS.md` 和 `docs/HANDOFF_CURRENT.md`，然后实时核对活动分支 HEAD、PR #1 状态和可见 Actions runs/jobs。以 GitHub 实际状态为准。当前首要任务是跨经历 accepted-claim reference resolver，不要回到旧的 Windows Worker/runtime 优先路线。PR #1 必须保持 Draft / Open / Unmerged。用户未在本机克隆或运行仓库；不要声称本机验证通过。


## 0.2 Continuation update — historical-prefix resolver groundwork (2026-11-20)

- Latest implementation commits after the prior checkpoint:
  - `509c6b15eb8b5db3f718b2c1cd0ab4f7c1b52083`: resolver accepts an optional `through_sequence` and calculates state version at that historical prefix.
  - `239f9f7c0cc37fdf329ac70ad7d4643bd9bd0c4a`: rejects a claim whose accepted-decision event did not yet exist at the requested prefix.
  - `a9a70b07080f803213a46fcbd13f71afc8304576`: adds regression coverage for immediately-before/immediately-after decision sequence.
- Why this matters: append/decision validation and Recovery must judge a candidate against the event history that existed at that exact point, not today's state version. A current-state-only resolver would incorrectly reject valid old candidates after later accepted memories, or could accidentally treat future decisions as historical facts.
- New optional API: `resolve_accepted_claim_reference(..., through_sequence=N)`. Callers must pass the sequence prefix corresponding to the event being validated and its matching authoritative state version. The default remains current-state behavior for existing callers.
- Tests are **not executed**; latest commit has no associated PR workflow run visible. No local test result is claimed.
- Live PR check: #1 Open, Draft=true, Merged=false; branch `feature/csd-cognitive-memory-slice`; head at this update `a9a70b07080f803213a46fcbd13f71afc8304576`.
- Next implementation: dedicated CSD pending-shadow cross-episode proposal/decision event family, with append-time and decision-time reference re-resolution against the corresponding historical prefix, plus projection rebuild/Recovery. No accepted outcome is allowed yet.
- PR #1 must remain Draft / Open / Unmerged.


## 0.3 Continuation update — CSD cross-episode pending candidates (2026-11-20)

### Implemented checkpoint

- Code/test checkpoint: 0e7f213f3489030209cb5e4836c3120cfa586e8e.
- Added core/csd/cross_episode_proposals.py and event type cognition.cross_episode_candidate_proposed.v1.
- Public operations: build_cross_episode_proposal, append_cross_episode_proposal, and list_cross_episode_proposals.
- The model supplies only opaque historical-reference keys. CSD re-resolves each key against accepted memory/claim lineage and records proposal, decision, claim digest, source event IDs, and state version. Persisted events omit copied claim text.
- Append-time revalidation is inside the same SQLite write transaction and uses the event's exclusive historical sequence prefix. Direct reads, duplicate acknowledgement, projection application, and Recovery replay use the same validator.
- The event is pending-shadow only. It does not advance authoritative CSD state version and cannot mutate user preference or AI self-model state.
- User preference and AI interest candidates have separate owner/domain allowlists. This is only a coarse category filter; do not treat it as a sensitive-content classifier or as approval.
- Focused tests cover idempotency, source provenance, claim digest tampering, stale state, malformed fields, owner/domain confusion, support/counter overlap, and Recovery replay.

### Static audit findings

- Confirmed the new event type is present in the public submit allowlist, _validate_event_local_shape, _apply_projection_event, and Recovery's durable-event allowlist.
- Recovery rebuilds the event stream and revalidates the historical references at each cross-episode event's original sequence. No mutable projection table is used for these pending candidates.
- The resolver follows only earlier accepted decision, grounded proposal, and observation events; this review found no recursive call back into cross-episode event validation.
- This is source-level review only. No test execution is claimed.

### CI status — still blocked before test steps

- Workflow path filters and the dedicated test_csd_cross_episode_proposals.py step are present for both push and pull_request events.
- Actions Run #779 (ID 44585188161), code/test SHA 855822a..., failed with both matrix jobs exposing no steps. Rerun attempt 2 still returned steps=null and logs_url=null; no job log artifact was available.
- Run #778 (ID 44585172949) showed the same empty-job failure pattern.
- The evidence indicates failure before a test command became observable; it does not establish a Python test failure or a passing test. The root cause is unknown. Do not speculate about repository billing/settings or GitHub service health.
- No local tests, local Windows 11 / Python 3.12.14 verification, or live cloud API smoke test have run.

### Next actions

1. Keep PR #1 Draft / Open / Unmerged. Never merge without explicit user authorization.
2. Continue static review and interface/Recovery contract checks; avoid repeated no-op commits or reruns that produce empty jobs.
3. Keep all cross-episode interpretations pending/shadow. Do not let them affect Life Engine decisions or accepted preference/self-model state.
4. Before authoritative revision, implement reviewer v2 plus CSD-owned decision/revision events, including support/counter-evidence, scope, alternatives, uncertainty, evidence lineage, state-version revalidation, replay, and rollback/history.
5. Once a runner actually executes steps, run the focused cross-episode suite first, then the CSD focused suites and full Ubuntu/Windows matrix. Until then, mark tests as not executed.
6. Preserve the full autonomous-life target and the ai-companion-pi design lessons: private home, multiple wake-up causes including AI-requested wake, optional autonomous research/creation/retrospection/rest, long-term project continuity, queued proactive messaging, graded permissions, and rollback/evaluation. Do not reduce the project to a memory plugin or fixed periodic journal task.

### Live branch metadata at this documentation update

- PR #1 head before this handoff append: 1772b35f514940742a7a27d974586e8d9aacdcfc.
- The final PR head must be re-fetched after this documentation commit. The code/test checkpoint remains 855822a...


## 0.4 Continuation update — duplicate alias rejection and current CI blocker (2026-11-20)

- Latest code/test checkpoint: 37536152a09f145f9867471dbac40fc7e55c5772.
- Static review found a consistency gap: distinct opaque context keys could resolve to the same accepted memory/claim identity. The CSD append validator already rejected duplicate persisted identities, but the builder did not reject them early.
- Fixed the builder to reject duplicate resolved claim identities before it returns a CrossEpisodeProposal. Added a regression test using two aliases for one accepted claim.
- Actions Run #780 (ID 44586330403) for this code/test checkpoint failed before either Ubuntu or Windows job exposed steps. Both jobs returned logs_url=null and steps=null. This repeats the runner/job-startup failure pattern; no test execution is established.
- No tests are claimed as passing. No local test, Windows runtime verification, or live cloud API smoke test has run.
- The design contract now distinguishes implemented historical resolver + pending-shadow append/Recovery from unimplemented reviewer v2, decision-time validation and CSD revision reducer. The autonomous-life proposal's status section has also been refreshed to reflect existing prior-memory context, same-episode reviewer v1, and the cross-episode pending event.
- Next: continue static contract review, preserve pending-only status, and do not let candidates affect Life Engine ranking. Do not repeatedly trigger empty Actions runs. Before implementing accepted preference/self-model changes, complete reviewer v2, CSD decision/revision events, decision-time revalidation, reducer and Recovery tests.
- PR #1 must remain Draft / Open / Unmerged. Re-fetch live PR metadata before any future work; do not merge.


## 0.5 Documentation reconciliation — 2026-11-20

- The cross-episode contract header and implementation sequence now reflect reality: historical resolver and pending-shadow append/Recovery are implemented; reviewer v2, decision-time revalidation and accepted preference/self-model reducer are not.
- Its implementation details now specify the actual v1 event shape (one candidate per proposal), canonical references, pending-only state and no Life Engine ranking.
- The autonomous-life proposal's status section now reflects the current code: lexical prior-memory context and same-episode semantic reviewer v1 exist; cross-episode reviewer v2, CSD revision reducer, private home, autonomous scheduler, long-term project management and proactive-contact queue remain future work.
- Documentation commits: autonomous-life status ce88f05691a1cddaee23528aedc986c02cece1fc; cross-episode contract 9695c44a40a44bcb38672d0ac592172239b6bb02.
- Latest code/test checkpoint remains 37536152a09f145f9867471dbac40fc7e55c5772. No code changed after that checkpoint.
- Run #780 (ID 44586330403) failed before steps/logs were exposed on both Ubuntu and Windows. No test execution is established.
- Do not mistake the documentation commits for a code/test checkpoint or claim tests passed. PR #1 remains Draft / Open / Unmerged.


## 0.6 PR base-branch divergence — review before any synchronization

- PR #1 remains Draft / Open / Unmerged.
- Current compare result against main: status=diverged, feature ahead_by=1432, behind_by=7. PR base SHA at creation: 05cfce6211ad072342201697d324d610d0fb40d1.
- The seven main-only commits after that base are one 2026-11-16 CSD goal-test addition, three Stage 0 documentation commits, and three documentation reverts. The feature branch contains the goal test file with the same 54 test method names, but its contents differ; the relevant README/progress/report files also differ.
- This does not show a missing test suite, but it does mean the histories are divergent and PR metadata currently reports mergeable=false. Do not merge/rebase/force-sync the branches as part of routine continuation. First inspect a deliberate diff and obtain explicit user authorization for any history synchronization.
- The active feature branch remains the working branch. Latest code/test checkpoint is 37536152a09f145f9867471dbac40fc7e55c5772; docs-only commits after it do not change runtime/test code.


## 0.7 Semantic-review input hardening and reviewer-v2 contract — 2026-11-20

- Latest code/test checkpoint: 285fb5aeb85b19e25b89a37039c57f683f8e61ae.
- Hardened existing same-episode semantic-review v1. Provider-side and CSD event validation now enforce bounded reasoning text (2,000 chars), bounded alternatives/limitations (8 each), supporting source claim IDs (32), identity fields (200 chars), and digest fields (80 chars).
- Added regression tests for oversized provider reasoning text, oversized event reasoning text, and oversized alternative-explanation lists. No execution evidence exists yet.
- Actions Run #781 (ID 44588405212) failed before steps/logs were exposed on both Ubuntu and Windows. This is the same runner/job-startup pattern as prior runs, not a Python test result.
- Cross-episode contract now has an explicit reviewer-v2 specification: candidate-sequence historical prefix, re-resolved support and counter evidence, source observation content and exact spans, deduplicated source events, strict bounded output, scope/alternative/risk review, human-review flag, and no CSD/ASM authority.
- Reviewer v2 itself is not implemented. Its result must remain advisory; the later CSD-owned review/decision event must independently re-resolve evidence at its own historical sequence before any preference/self-model reducer is considered.
- PR #1 remains Draft / Open / Unmerged. Do not merge, rebase, or force-sync the divergent feature/main histories.
- Next: implement the provider-neutral cross-episode reviewer-v2 pipeline as a read-only, non-persisting analysis step. It must use the candidate event's sequence as the exclusive historical boundary, pass exact support/counter bundles plus original source observations, enforce bounded strict output, and remain outside write transactions. Add focused tests; do not claim they pass until a runner actually executes them.


## 0.8 Final metadata reconciliation — 2026-11-20

- Code/test checkpoint: 285fb5aeb85b19e25b89a37039c57f683f8e61ae.
- Cross-episode contract commit: 736a9b2e588edf062fabb0eeb9100051f7afbd2e.
- Project progress metadata commit: 037e02984fb72be8b8d4109f16e71aabe27ce41d.
- Immediately before this handoff update, PR #1 head was 939970060125c334647b3554b3505a25c3cd9832. This handoff update becomes the next PR head.
- PR #1 remains Draft / Open / Unmerged; GitHub reports mergeable=false. Do not merge or synchronize divergent branch history.
- Latest relevant CI Run #781 failed before steps/logs were exposed; no test execution is established.


## 0.9 Cross-episode reviewer v2 read-only pipeline — 2026-11-20

### Implemented in the active feature branch

- `core/csd/cross_episode_review.py` now contains:
  - `CrossEpisodeReviewProvider` protocol;
  - `CrossEpisodeReviewCandidate` strict provider output;
  - `CrossEpisodeReviewPipeline.review_proposal(proposal_id)`;
  - `CrossEpisodeReviewArtifact` ephemeral, digest-bound result.
- The pipeline only accepts an exact pending-shadow cross-episode candidate.
- It opens one CSD read snapshot, resolves the candidate event and all support/counter references, and re-resolves each accepted memory/claim pair using the candidate event sequence as an exclusive historical prefix and the recorded state version.
- Every persisted reference lineage field and claim digest must exactly equal the fresh canonical resolution.
- Original source observation events are loaded and verified before the candidate event. Each Unicode-codepoint evidence span must exactly match the immutable source content. Duplicate source events are passed once, while evidence-span records preserve claim/reference association.
- Bounds: each source content <=20,000 chars; all source content <=100,000 chars; complete serialized reviewer input <=400,000 UTF-8 bytes. Oversize or inconsistent evidence is rejected, never truncated.
- Opaque account references are omitted. The reviewer gets only selected provenance fields and the exact evidence content.
- The provider runs after the read transaction closes and receives no store handle, CSD mutation tool, or ASM capability.
- Output is strict: five outcomes, finite confidence, exact selected-reference allowlists, disjoint support/counter sets, scope enum, bounded alternatives/limitations/risk flags, and boolean human-review requirement. `supported` requires support; `conflicting` requires both support and counter-evidence.
- Returned review artifact is non-authoritative and not persisted. It is bound to proposal ID/event ID/sequence/payload digest/state version/reviewer identity. Provider sequences are copied to tuples before return.
- Added `tests/test_csd_cross_episode_review.py`, exported interfaces in `core/csd/__init__.py`, and added the focused test step and both path filters to `.github/workflows/csd-cognitive-slice.yml`.
- Updated `docs/design/cross-episode-evidence-and-preference-revision-contract.md` and `docs/PROJECT_PROGRESS.md`.

### Verification status

- Code/test checkpoint before docs: `a35d016cdc8956e5e64c87947a32b9d3e68a73f0`.
- Contract update: `ee70ef7983cb0b9636794b856e00d736acc9d4c2`.
- Progress update: `8a4bd0282b0622b4d71dafcdc231918106c6e64a`.
- Actions runs #782–#786 all failed before observable test execution. Latest #786 Jobs API returned an empty `jobs` array. Do not label this as Python test failure or passing verification. No local compile/test, Windows runtime test, or live provider API test has run.
- PR #1 remains Draft / Open / Unmerged; do not merge. Do not rebase/force-sync the divergent branch.

### Next implementation slice

1. Static-audit `cross_episode_review.py` and its tests for malformed persisted event data, reference key association, input bounds and source chronology.
2. Implement a CSD-owned cross-episode reviewer decision/review event. It must re-resolve evidence again at its own event sequence boundary, bind the exact ephemeral reviewer artifact digest and candidate event identity, validate provider identity and policy, and replay deterministically in Recovery.
3. Keep reviewer output advisory until that CSD-owned event is implemented. Do not allow it to mutate accepted preferences, AI interests, self-model, Life Engine ranking or ASM.
4. Only after decision-time revalidation and Recovery are implemented and executable tests pass should the preference/self-model reducer be considered.
5. Keep the full autonomous-life objective and ai-companion-pi lessons intact: private home, event/AI-requested wake causes, optional autonomous research/creation/retrospection/rest, long-term project continuity, queued proactive messaging, graded permissions and rollback/evaluation. No fixed wake-up cadence or diary quota.



### 0.9.1 Reviewer-v2 follow-up audit

- Added a maximum of 64 distinct source observation events and 32 evidence spans per claim. This complements the 20,000-character per-source, 100,000-character total-source, and 400,000-byte complete-input limits.
- V2 observation coverage metadata is included in provenance. Opaque account references remain excluded.
- Reviewer output requires the exact `CrossEpisodeReviewCandidate` type; subclasses are rejected to prevent additional undeclared authority fields. Explicit `sensitive_inference` risk requires `requires_human_review=True`.
- Added regressions for immutable artifact sequence fields, sensitive-inference human-review enforcement, and provider subclass rejection.
- Latest code commits: `02cc65bcb13afd6a09cfdb0715ed908bd3850fe4`, `682c87bfef982be878a62d500c31e49f958d8335`, and `f3bf41293dc85f921454f1a2d853014cea7d8e79`.
- Latest visible Actions run #789 still failed before jobs were created; its Jobs API response had an empty `jobs` array. No compile or Python test has executed.
- Keep the implementation advisory and non-persisting. The next meaningful feature is the CSD-owned decision/review event with independent decision-time evidence re-resolution and Recovery, not a preference reducer.


- Final reviewer artifact hardening: the artifact now includes a separate SHA-256 digest over the canonical, bounded provider input, not just the candidate event payload. This binds the ephemeral opinion to the exact evidence snapshot. Code commit `293b4498b9258b6f38009f377183363fc8bd6c62`; test commit `f3b8e1ac1bbc6a63458bd9dd2907dd9f9871e4d3`. Tests remain unexecuted.

## 1.0 Next slice: CSD-owned cross-episode review record

The read-only reviewer v2 implementation is advisory only. Implement the durable review-record event next, with these invariants:

1. New event type is CSD-reserved; external callers cannot submit it through public submit_event.
2. Record binds exact pending-shadow proposal event ID/sequence/payload digest, recorded CSD state version, canonical reviewer-input digest, reviewer ID/version, and the normalized bounded reviewer result.
3. CSD must independently reconstruct the canonical reviewer input at the review event's own sequence boundary. Do not trust the ephemeral artifact's claims merely because it came from the pipeline.
4. Every accepted claim reference must be re-resolved with the candidate's recorded state version and the proposal event as exclusive historical prefix; source observation chronology and quote spans must be revalidated.
5. The record must be validated on append, direct get_event, duplicate acknowledgement, and Recovery. Reuse one deterministic validator for all paths.
6. The record remains an audit opinion only. It cannot accept/reject/revise the candidate, update user preferences or AI interests, alter self-model, rank Life Engine activity, or grant ASM permissions.
7. Support deterministic/idempotent event identity; allow a distinct reviewer/version/input to produce a distinct review record. Do not introduce a mutable review projection unless a demonstrated query need requires one.
8. Add tamper, stale evidence, public-submit denial, duplicate, direct-read and Recovery tests. No test may be described as passing before execution evidence exists.

### Static inspection correction

The previous export edit in core/csd/__init__.py accidentally inserted literal backslash-n characters. Fixed in d30a7fb7af4fae6f0a75dbdd02113ade6d9a07fc. Confirm this file compiles as part of the next executable verification attempt.


## 1.1 Window handoff — reconciled repository state (2026-11-20)

**Use this section as the newest continuation point.** Older entries below contain historical statuses that were true at the time but are now superseded by this section.

### Repository and PR

- Repository: `Ar1mead/QQBOT`.
- Working branch: `feature/csd-cognitive-memory-slice`.
- PR #1: Draft / Open / Unmerged; GitHub reports `mergeable=false`.
- Latest pre-documentation implementation HEAD: `35e0f4e4f8de195ecae5034c549269a58d6979f6`.
- CI workflow repair: `06408dbf1c577849be92a15bd39a5316a32ea5df`.
- Cross-episode contract reconciliation: `fffb5200a4674e59c7f38445b7bcd502ee8d1e18`.
- Progress reconciliation: `3c995b87e927d9e5ada8e167cbc3bf8a2b109f5b`.
- Re-fetch live PR head and all three document SHAs at the start of the next window; subsequent handoff commit will advance the PR head.
- Last branch comparison: diverged, feature ahead by 1467 and behind by 7 relative to main. Do not merge, rebase, force-sync or otherwise rewrite/synchronize branch history without explicit user authorization.

### What is implemented now

1. **Cross-episode proposal and historical claim resolution**
   - Accepted-claim references are re-resolved at exclusive historical sequence boundaries.
   - Cross-episode candidates remain `pending_shadow`; they are not accepted user preferences or AI interests.

2. **Provider-neutral cross-episode reviewer v2**
   - `core/csd/cross_episode_review.py` reconstructs exact support/counter evidence and source observations, validates source chronology and quote spans, applies bounded inputs/outputs, and runs the provider outside the CSD transaction.
   - It returns an advisory artifact bound to proposal payload and canonical reviewer-input digests.
   - It does not write CSD or authorize actions.

3. **CSD-owned durable review record**
   - Event type: `cognition.cross_episode_review_recorded.v1`.
   - Reserved source: `csd.cross-episode-review-authority.v1`.
   - `CrossEpisodeReviewPipeline.record_review(artifact)` rechecks the artifact against a freshly rebuilt candidate/evidence snapshot before appending.
   - Event identity is deterministic from canonical payload digest; event ID is derived from the review ID.
   - Public submission of the reserved event type and event-ID namespace is blocked.
   - Shared event-local validation checks schema, reviewer identity, proposal chronology and digests, canonical evidence-input digest, candidate output and reference allowlists, and duplicate review identity.
   - The same validation path is called by append, duplicate acknowledgement, direct `get_event` validation and Recovery replay.
   - The durable record is an immutable audit opinion only. It does not accept/reject the candidate, update preference/self-model state, alter goals, affect Life Engine ranking, or grant ASM permissions.

### Critical test gap — do not overlook

- `tests/test_csd_cross_episode_review.py` currently contains ten tests for the read-only reviewer pipeline.
- It does **not** yet test `record_review` or the durable review event.
- Add tests for:
  1. successful record append and event payload/identity;
  2. public `submit_event` rejection of reserved review event and reserved ID namespace;
  3. deterministic duplicate acknowledgement and altered-content idempotency conflict;
  4. direct `get_event` validation after event payload/lineage tampering;
  5. stale/altered ephemeral artifact and changed evidence rejection;
  6. Recovery replay of valid review events and failure on tampered review history.
- Also verify that duplicate validation and event-local validation remain deterministic when the event is replayed in order.
- Until these tests execute, durable review-event implementation is **present but not verified**.

### CI diagnosis and repair

- Earlier static inspection found four literal backslash-`n` sequences in `.github/workflows/csd-cognitive-slice.yml`, affecting both path-filter lists and the new test step. They were replaced by actual line breaks in commit `06408dbf1c577849be92a15bd39a5316a32ea5df`.
- Actions Run #808 (ID `44592352031`) after that fix created two jobs (Ubuntu and Windows), confirming the workflow YAML now parses.
- Both jobs immediately failed with empty step lists and runner ID `0`. The step API returned an empty list and the job-log endpoint returned BlobNotFound. No runner was allocated; no checkout, compile or test command ran.
- This separates the earlier malformed YAML defect from the still-unresolved job/runner startup issue. Do not report Python test pass/failure. Avoid repeatedly triggering Actions runs until the runner issue is investigated.

### Next exact work item

1. Add the six groups of durable-review event tests listed above.
2. Static-audit `validate_cross_episode_review_event`, especially malformed payload handling, deterministic identity, duplicate query behavior and direct-read/Recovery call paths.
3. Investigate why Actions creates jobs but allocates no runner (runner ID 0, no steps, no logs). Do not make speculative claims about billing/permissions without evidence.
4. Obtain actual compile/test execution evidence, ideally focused suite first, then full Ubuntu/Windows matrix.
5. Only after the CSD review record and Recovery tests pass should the preference/self-model reducer be designed/implemented. Pending candidates and reviewer opinions must remain outside Life Engine ranking until a separate CSD-owned acceptance/revision event exists.

### Preserve the full product objective

Do not narrow the project to a memory plugin. The target remains a persistent individual AI with autobiographical continuity, evolving self-model/preferences/interests, autonomous but bounded internal activity, private home, event- and AI-requested wakeups, long-term project continuity, optional research/creation/retrospection/rest, queued proactive contact, graded external permissions, and action-result evaluation/rollback. Keep the useful `sonopdx/ai-companion-pi` ideas while avoiding fixed wake-up quotas, diary quotas, unrestricted tools, or treating runtime/SurfCore as the owner of identity.

No local test, compile, Windows runtime, or real cloud API smoke test has been executed in this session. No PR merge or branch synchronization was performed.


## 1.2 Newest continuation checkpoint — Goal outcome design (2026-11-26)

**Use this section as the current handoff.** It supersedes older "next exact work item" instructions above where they still say the durable review-record tests do not exist or describe the earlier 2026-11-20 checkpoint. The durable review-record tests have since been added, but they remain unexecuted.

### Live repository state before this handoff update

- Repository: `Ar1mead/QQBOT`.
- Active branch: `feature/csd-cognitive-memory-slice`.
- PR #1 live head before this handoff commit: `23b9d4a1d220501f7af350e422b7ef45bdfb4a12`.
- PR #1 remains Open / Draft / Unmerged, base `main`. Never merge it.
- Latest code-bearing commit remains `b7e170ea525171a1d26c0f9604b863db19010887`; subsequent work in this continuation is documentation-only.
- The three current document paths are:
  - `docs/PROJECT_PROGRESS.md`
  - `docs/HANDOFF_CURRENT.md`
  - `docs/design/cross-episode-evidence-and-preference-revision-contract.md`

### Current architecture and design checkpoint

- CSD remains the sole authority for durable cognitive state and accepted revisions. Provider opinions, proposals and external observations are evidence/input, not state authority.
- Motivation `origin_class` describes evidence origin, not ownership. It cannot classify a signal as a user preference or AI-owned interest.
- Goal activation creates an intention only. It does not execute work, grant capability or prove completion.
- Design §3.14 now defines the missing Goal outcome boundary: separate intention state, ASM execution history, observed outcome evidence and CSD outcome decisions; proposed candidate/active/paused/blocked/completed/abandoned/expired/superseded lifecycle; criterion-bound completion evidence; explicit fail-closed transitions; and a separate outcome-learning event.
- Goal outcome learning must not silently revise Motivation, user preferences, AI-owned interests or self-model. Each such cognitive revision needs its own CSD proposal/review/decision/version history.
- §3.14 is design only. No Goal outcome event family, completion evaluator, outcome-learning reducer or ASM execution integration is implemented.

### Verification and Actions gate

- The six dedicated durable review-record tests in `tests/test_csd_cross_episode_review.py` exist but have **not** been executed.
- Latest specifically known Actions run is #814 (ID `44600378390`). Its Ubuntu and Windows jobs failed before runner allocation in the earlier inspection; no test result is established.
- A fresh Jobs lookup for #814 still reports both matrix jobs as failed. The current connector's step summaries returned no step records for either job. Do not describe this as a code/test failure or pass.
- GitHub Free included Actions compute was shown exhausted at $12/$12 on 2026-11-20; user has no payment method and has not authorized charges. This remains the strongest explanation for pre-runner failure, not an explicit error string from the job payload.
- Around 2026-12-02, first inspect Billing and confirm included usage actually reset. Then run the focused review-record suite and verify checkout/test steps actually execute. Only after that suite passes, run the full Ubuntu/Windows matrix. Do not run local tests or rerun Actions before this checkpoint. Do not enable paid usage or make the private repository public.

### Next work

1. Continue low-risk design work on how outcome evidence informs planning without automatically changing preferences, interests or self-model.
2. Reconcile all three documents after each meaningful design checkpoint.
3. Keep implementation blocked until the focused review-record suite and full Ubuntu/Windows matrix pass.
4. Do not implement decision-time acceptance API, preference/self-model reducers or Life Engine wiring before that gate.
5. Re-fetch live branch/PR/Actions state at the start of the next continuation. Keep PR #1 Draft / Open / Unmerged. Do not merge, rebase, force-sync or synchronize the fork.

No source code or tests were modified or executed in this continuation. No local environment, QQ/Bilibili account, DSH runtime, SurfCore integration, or external side effect was touched.


### Final document synchronization — 2026-11-26

- Immediately before this final handoff update, live PR #1 head was `86d771d15ecba4f3fbfc3b506bd17af115c1a951`; it was Open / Draft / Unmerged and targeted `main`.
- Progress ledger blob SHA: `a1a3dc8bcbf96a47fdd73d8580d45a80f81b172b`.
- Design contract blob SHA: `d712bc343a625430bf612d30145573c3128a25b3`.
- The next commit updates this handoff only. Re-fetch the live PR head and document SHAs next time; do not assume the pre-update SHA is still HEAD.
- No code/tests changed; no tests were run. The next formal verification checkpoint remains around 2026-12-02, subject to Billing confirmation.


## 1.3 Latest design continuation — outcome feedback into planning (2026-11-26)

This subsection supersedes the "Next work" list in §1.2 where that list names outcome-feedback design as unfinished.

- Design §3.14 now defines Goal lifecycle and outcome decisions: candidate, active, paused, blocked, completed, abandoned, expired and superseded; evidence-backed completion; explicit versioned terminal transitions; and a separate outcome-learning event.
- Design §3.15 now separates four learning targets: episode-local result, contextual planning constraint, reusable strategy hypothesis, and durable preference/interest/self-model revision.
- Accepted scoped lessons may inform planning, but one outcome cannot silently become a durable identity or preference claim. Distinct-episode independence, counterexamples, context/freshness, causal attribution and provenance must be retained. Provider-generated lessons remain proposals; CSD owns acceptance and Recovery.
- Both sections are design only. No outcome event, lesson projection, goal completion evaluator, planning integration or preference/self-model reducer has been implemented. No source code or tests were changed or executed.
- Next: perform a consistency audit across §§3.11–3.15 and the architecture/overall progress documents; look for conflicting event ownership, state-version, Recovery and Life Engine assumptions. Keep the implementation gate closed pending the scheduled Billing check and executable focused/full test gates.
- Progress ledger SHA at handoff preparation: `5080f2bd672af92507b2725a26a81db81a59a330`.
- Design contract SHA at handoff preparation: `b82472cbebb6bde2dc03a85239331f3531e604fd`.
- PR #1 at handoff preparation: state `open`, draft `true`, merged `false`, head `936e0c5188c733010d1792f6d714a081345d3b13`. This handoff commit will advance the branch head; re-fetch next time.


## 1.4 Consistency audit and state-version rules — 2026-11-26

This subsection supersedes §1.3's next-work item to perform the §§3.11–3.15 consistency audit.

- Cross-checked design §§3.11–3.15 against the platform/runtime adapter contract. No authority conflict was found: CSD owns durable cognitive decisions; ASM owns external side-effect authorization/dispatch/verification; adapters provide bounded evidence/capabilities; Life Engine deliberates but does not mutate CSD state or bypass ASM.
- Clarified that §3.13 is a static description of current Motivation/Goal implementation, while §§3.14–3.16 are future design only. The current Goal implementation still does not implement completed/blocked/abandoned/expired/superseded outcomes or outcome learning.
- Added design §3.16 to define distinct outcome evidence, assessment proposals, CSD goal outcome decisions, lesson proposals and CSD-accepted planning lessons.
- State-version rule: evidence/proposals/advisory reviews do not increment; each accepted authoritative goal transition increments once; each separately accepted durable planning-lesson revision increments once; a single atomic event updating multiple fields increments once. A goal outcome decision does not silently accept a lesson, and a lesson does not alter goal status.
- Accepted lessons are bounded planning inputs only. They cannot force Life Engine activity, grant ASM permission, or silently revise preferences/interests/self-model. Scope/freshness and Recovery behavior are explicitly required.
- Design contract SHA at handoff preparation: `702399162002c914c719def68a157516afa19a1e`.
- Progress ledger SHA at handoff preparation: `ec6c956ba454c5c8375867e3d7517738de4c33ac`.
- PR #1 at handoff preparation: `open`, Draft=`true`, Merged=`false`, head=`45d18429a83ec107de12cbbc02b3a646f979f3db`. The next handoff commit advances the branch; re-fetch live state next time.
- No source code/tests changed or executed. No local tests or Actions reruns. Next formal verification checkpoint remains around 2026-12-02, after checking Billing for actual included-usage reset; focused review-record suite first, then full Ubuntu/Windows matrix.
- Next design work: audit the proposed owner/subject and preference/self-model revision contract against the complete project architecture, then consolidate outdated progress/handoff statements. Do not implement reducers or Life Engine wiring before the test gate.


## 1.5 Latest continuation — subject ownership and evidence attribution (2026-11-26)

This section is the current handoff and supersedes earlier next-work items that described the subject/owner contract as unfinished.

### Live state at start of this continuation

- Repository: `Ar1mead/QQBOT`.
- Active branch: `feature/csd-cognitive-memory-slice`.
- PR #1: Open / Draft / Unmerged, base `main`; live head at start: `2d8b7c30a31c5a3a93b98ddc0122eb9e89561368`.
- Latest code-bearing commit remains `b7e170ea525171a1d26c0f9604b863db19010887`; this continuation changes documentation only.
- No PR merge, rebase, force-sync or fork synchronization is authorized.

### What code currently enforces

- `core/csd/cross_episode_proposals.py` v1 supports `preference_candidate` with owner `user` and `interest_candidate` with owner `ai`; it enforces matching pairs and separate coarse non-sensitive domain allowlists at proposal construction and persisted-event validation.
- These candidates remain pending-shadow. They cannot revise accepted preferences/interests, mutate self-model, rank Life Engine activities or grant ASM capabilities.
- This is only a coarse type guard. It does not yet define canonical subject references, complete subject-attribution evidence, voluntary AI-choice records or a distinct AI self-model claim family.
- Motivation `origin_class` remains evidence provenance/origin, not owner or subject class.

### New design contract

- Added §3.17 to `docs/design/cross-episode-evidence-and-preference-revision-contract.md`.
- It separates CSD state authority, claim subject class, canonical subject reference and evidence provenance.
- It defines three distinct future claim families: user preference, AI-owned interest and AI self-model. Topic choice does not prove capability; task success does not prove interest.
- AI-owned interest is operationally grounded in meaningful, attributable AI-selected activity among allowed alternatives. User-requested work, passive exposure/autoplay, mandatory or scheduled activity, and model self-description alone do not qualify as proof of AI interest.
- User corrections about the user's own preferences receive high-priority review; user constraints on AI behavior are not misclassified as proof of the AI's own preference. AI-owned revisions remain CSD-governed and cannot override user constraints or safety policy.
- Subject identity cannot be relabelled or transferred across revisions. Ambiguous subject attribution and unresolved material conflicts fail closed.
- The contract explicitly makes no claim about consciousness, sentience or human-like feelings.

### Verification gate — unchanged

- No source code or tests were changed or executed in this continuation.
- No local tests, compile checks, Actions reruns, real platform access or paid usage occurred.
- The six dedicated tests in `tests/test_csd_cross_episode_review.py` remain unexecuted.
- Latest specifically known hosted Actions evidence remains Run #814, whose jobs failed before runner allocation with no test steps. The current commit-associated PR-run lookup returned no runs; this is not a CI pass.
- Around 2026-12-02, first inspect Billing and confirm included Actions usage actually reset. Then run the focused review-record suite, verify real checkout/test steps and a pass, and only then run the full Ubuntu/Windows matrix. No local tests or paid usage before that checkpoint.

### Next work

1. Continue static design review of how canonical subject references are established and bound to the actual AI individual/user identity across multiple users, account scopes and Recovery.
2. Check whether the current observation and event provenance schemas can supply the proposed voluntary-choice evidence without trusting model-authored claims.
3. Reconcile any resulting design changes across the design contract, progress ledger and handoff.
4. Do not implement subject-reference fields, accepted revision reducers, decision-time acceptance API or Life Engine wiring before the existing focused and full hosted test gates pass.

No user-local runtime, DSH/SurfCore integration, QQ/Bilibili account, credential or external side effect was touched.


## 1.6 Interaction-choice evidence audit — 2026-11-26

- Static inspection found the existing `experience.interaction_choice_recorded.v1` has useful provenance and shape checks, including origin-event chronology, meaningful choice-set size, selected-item membership, and return-visit continuity.
- It is not yet strong enough to prove AI agency for durable AI-interest revisions: `subject_ref` is not bound to a canonical AI identity; choice-set refs are not resolved to authoritative available options; adapter source/component labels are self-consistency checks rather than host attestation; and public event submission is not restricted away from this event family. Labels such as `internal_state` and `self_commitment` are not proof that an action was genuinely optional.
- Design §3.18 now records these limitations and requires a future host/CSD-attested, versioned choice event with canonical subject binding, exact choice/trigger lineage, trusted adapter provenance, and append/direct-read/Recovery validation.
- Existing Motivation interaction events remain valid under their current semantics; do not reinterpret them as stronger proof of AI autonomy. This is a design gap, not a source-code fix performed in this continuation.
- No source code or tests changed or executed. No local tests, compile checks, Actions reruns, real platform operations or paid usage occurred.
- Next: statically inspect the origin/subject chain from observation → interaction → motivation signal → goal, especially whether a user identity or AI identity can be rebound between stages. Then update all three governing documents. Do not implement the new attestation event or revision reducers before the focused and full hosted test gates pass.


## 1.7 End-to-end identity-chain audit — 2026-11-26

- Traced Observation v2 → interaction event → Motivation signal → Goal → cross-episode candidate.
- Observation v2's optional `actor_ref`/account/context fields preserve external provenance but are not a canonical CSD subject identity. Interaction `subject_ref` is only shape-checked and is not bound in the inspected path to the actor in its source observation or to the subject of a later candidate.
- The architecture must distinguish the observed event actor (who authored/performed the event) from the claim subject (who the preference/interest statement is about). This matters for group messages, quoted text and statements about third parties.
- Design §3.19 now requires host/CSD-issued opaque subject IDs, trusted account/actor mapping, actor-vs-claim-subject separation, consistent subject binding through Motivation/Goal/cross-episode evidence, mixed-subject rejection, and versioned identity mapping through Recovery.
- Third-party preference/personality inference is out of scope for the initial implementation without separate consent/privacy rules.
- No source code or tests changed or executed. No local tests, compile checks, Actions reruns, external platform operations or paid usage occurred.
- Next: review the complete design §§3.17–3.19 for contradictions with multi-user QQ/group-chat operation and the Private Home model, then consolidate the design into a single implementation-ready contract without crossing the test gate.


## 1.8 QQ multi-user and Private Home reconciliation — 2026-11-26

- Reviewed the platform/runtime adapter contract and `docs/design/autonomous-life-and-self-development.md` against §§3.17–3.19. No architectural contradiction was found.
- QQ's initial adapter is receive-first and preserves account, conversation and sender references. Each sender must resolve independently to a canonical user subject; group IDs, bot account IDs and display names are not preference subjects. Quoted/forwarded third-party statements and group content cannot silently become an individual user's preference evidence.
- Private Home is the AI individual's workspace, not a user-preference store or a source of automatic truth. User/external content stored there retains its original provenance and cannot become AI-authored experience or voluntary-interest evidence merely by being copied into the workspace.
- AI-individual identity remains separate from QQ bot account, DSH, SurfCore, provider/model version and platform adapters. Runtime/provider replacement must preserve the same individual; a new individual must not inherit private state by default.
- Design §3.20 records these rules and adversarial tests. Canonical subject registry, account/actor mapping and Private Home identity binding remain future work.
- No code or tests changed or executed. No local tests, compile checks, Actions reruns, external account operations or paid usage occurred.
- Next: consolidate the owner/subject/actor/provenance/choice-attestation design into a short implementation sequence and identify the smallest safe first implementation after the verification gate. Do not start coding before the focused and full hosted tests pass.


## 1.9 Implementation sequence and first safe slice — 2026-11-26

- Added design §3.21 to turn the identity/subject/agency design into a staged implementation sequence.
- Re-inspected CSD event validation/append paths: the event store has a closed event-family allowlist, internal-only reserved decision/review families, immutable event envelopes, duplicate checks and direct-read integrity validation. Identity must be implemented as CSD-owned events integrated with replay/Recovery, not as a model-supplied field or untrusted side table.
- **Stage 0:** Around 2026-12-02 inspect Billing and confirm included usage actually reset; run `tests/test_csd_cross_episode_review.py` focused suite first; only after actual focused pass run full Ubuntu/Windows matrix. Do not run local tests, trigger unnecessary Actions, add payment details, enable paid overage or change repository visibility.
- **Stage 1 — first code slice after Stage 0:** CSD-owned canonical subject registry for `user` and `ai_individual`; stable host-supplied AI identity; installation-scoped user subjects; trusted host-only platform actor binding; immutable relink/revoke history; separate `identity_version`; public-submit guards; direct-read/Recovery validation. Store opaque binding keys rather than raw platform identifiers/credentials. Do not infer cross-platform account links.
- **Stage 2:** bind observation actor provenance and host-attested voluntary AI choices to canonical subjects and exact trigger/choice-set lineage.
- **Stage 3:** carry subject/identity-version lineage through Motivation, Goal and cross-episode candidates; reject mixed-subject evidence; keep legacy records explicitly unbound unless a reviewed migration is defined.
- **Stage 4:** only then implement accepted preference/interest/self-model revisions, correction/adjudication, planning projections and bounded Life Engine integration. No ASM permissions are implied.
- First implementation explicitly excludes third-party profiling, group preference inference, raw identifier/credential storage, automatic account merging, consciousness/personality claims, accepted revision reducers and Life Engine/ASM wiring.
- No source code or tests changed or executed in this continuation. No local tests, compile checks, Actions reruns, external account operations or paid usage occurred.
- No merge/rebase/fork sync. PR #1 must remain Draft / Open / Unmerged.


## 1.10 Platform identifier privacy and key lifecycle — 2026-11-26

- Static audit of the current QQ data path found `sender_ref` is copied into ObservationEvidence `actor_ref`, and account/context/actor references are copied into durable CSD Observation v2 payloads. The CSD schema checks non-empty strings but does not ensure identifiers are opaque. SurfCore `observation_id` also uses unkeyed SHA-256 over platform/account_ref/record_id; this is not a safe identity pseudonym for guessable inputs.
- Design §3.22 now requires trusted-host pseudonymization before CSD append, domain-separated keyed pseudonyms or random opaque tokens, distinct namespaces for account/actor/conversation/resource, and no raw identifiers/credentials in durable events, projections, logs or model context.
- The design adds a platform-neutral host IdentityKeyProvider, protected key custody outside Git/CSD/model/worker, versioned rotation, fail-closed key-loss behavior, and coordinated key+database backup/restore.
- Historical immutable events that already contain raw identifiers must not be silently rewritten. They remain legacy/unverified; a deployed database requires a separately approved retention/sanitization/rebuild policy including backups and exports.
- No source code or tests changed or executed. No local tests, compile checks, Actions reruns, platform operations or paid usage.
- Next: audit the existing CSD storage/backup configuration and worker trust boundary to ensure the proposed key provider can be placed outside untrusted workers and that no logs/export paths bypass pseudonymization. Then consolidate Stage 1 acceptance criteria. Do not implement before the Stage 0 focused/full hosted test gate.
