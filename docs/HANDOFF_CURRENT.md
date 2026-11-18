# 个体 AI 项目 — 当前交接入口

**最后核对：** 2026-11-19（UTC+08:00）  
**仓库：** `Ar1mead/QQBOT`  
**活动分支：** `feature/csd-cognitive-memory-slice`  
**核对时分支 HEAD：** `8e617fd487f8485a03b22432c1310fe03bcb1f77`  
**PR：** #1 — Draft / Open / Unmerged（严禁合并）

> **本文件是唯一的当前交接说明。** 每次交接直接更新本文件，不再创建新的日期命名交接文件。日期命名的旧交接文件只作为历史记录，不得作为当前状态依据。开始工作时必须重新核对 GitHub 实际状态，文中的 SHA 和 Actions 状态都是本次核对时的快照。

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

## 3. 当前仓库和 PR 状态

本次核对：
- 活动分支 HEAD：`8e617fd487f8485a03b22432c1310fe03bcb1f77`。
- PR #1 head 与该 SHA 一致。
- PR #1：Draft=true、state=open、merged=false。
- PR #1 当前规模很大（约 1,268 commits、151 changed files）；这增加了审查、回归定位和发布风险。不要为了缩短流程而合并；应继续按明确验证门槛推进。

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

## 5. CI 状态 — 当前首要阻塞

本次读取到最近 10 次 Actions runs：#701–#710，均为 failure。
对最新 Run #710（ID `44353015881`）直接读取 jobs JSON：
- Windows job：`runner_id=0`、`runner_name=""`、`steps=[]`。
- Ubuntu job：`runner_id=0`、`runner_name=""`、`steps=[]`。
- 因此测试步骤没有执行；这是 runner 分配前失败，不是测试断言失败，也不能当作代码通过。
- 原因未知。不要猜测是 billing、minutes、配额、GitHub 服务或代码导致。
- 最后一次已知完整 Ubuntu + Windows matrix 通过为 Run #664；它早于之后的 runtime bundle pin/builder、Worker boundary 和 Windows lifecycle 改动。
- **#664 之后的代码变更目前均不能宣称已完整 CI 验证。**

下一步必须先确认 runner 分配是否恢复。如果没有，先做只读诊断，不要靠连续提交代码制造更多无效 runs。

## 6. 建议执行顺序

### P0 — 恢复真实 CI 验证
1. 每次开始先核对最近 runs 和最新 jobs JSON。
2. runner 恢复后先执行新增的 `tests/test_worker_windows_io.py` 与 `tests/test_worker_windows_handle_cleanup.py`。
3. 再执行 `test_surfcore_observation_mapping.py`、`test_worker_runtime_bundle.py`、`test_worker_runtime_bundle_builder.py`、`test_worker_windows_launch_plan.py`。
4. 最后跑完整 Ubuntu / Windows matrix；检查真实执行步骤与日志，不能只看 workflow conclusion。

### P1 — 真实 Windows CPython 3.12 bundle 验证
1. 在真实 Windows CPython 3.12 runtime 上运行 builder。
2. 检查 manifest 文件列表、canonical digest、`python312._pth` 和排除项。
3. 从 staging copy 执行 `python.exe -I -S -B app/worker_entrypoint.py`。
4. 验证 AppContainer 目录祖先 traverse、runtime 只读/可执行、runtime 不可写、worker temp 可写。
5. 验证 stdin/stdout/stderr、超时、输出上限、异常退出和清理。
6. 只有真实验证后，才把 manifest SHA-256 pin 安全配置进可信 host config。

### P2 — 完整 Windows executor coordinator
由 host 严格拥有资源生命周期并按逆序清理：trusted pin、runtime staging/temp、AppContainer profile、ACL、最小环境变量、WorkerPipes、capabilities、STARTUPINFOEX、Job Object、suspended launch/Job assignment/resume、有界 stdio、超时/输出限制、WorkerHost 响应验证、逆序释放。
若无法确认 Worker 已终止，必须 quarantine / fail closed；不得删除可能仍被进程使用的目录。cleanup errors 不可吞掉。

### P3 — Linux 与真实平台
- 实现并验证 Linux Bubblewrap backend。
- 完成 host-side SurfCore cursor/result metadata validation。
- 之后才做真实 QQ / B站只读连接和数据接入；外部写操作仍必须由 ASM 授权。

### P4 — 从“骨架”走向“个体”
- 冻结并审查 CSD / ASM 核心协议和安全边界。
- 接入云端模型 provider，但模型输出只能产生候选/提案，不能直接改写权威状态。
- 实现真实的持续审议、动机/偏好修订、学习更新、主动活动选择和可停止的自发写作循环。
- 做长时间运行、故障恢复、状态迁移、记忆质量、错误归因和成本/延迟测试。
- 明确哪些行为是模型模拟、哪些是系统可验证的状态变化，避免把规则引擎或定时任务包装成“自主意识”。

## 7. 当前项目的主要风险判断

1. **验证风险最高：** Actions runner allocation 连续失败，最近多次 workflow 实际没有执行任何步骤；最新代码处于未验证状态。
2. **安全闭环未完成：** Windows worker 的隔离原语已大量实现，但没有完整 coordinator，也没有真实 runtime bundle + AppContainer 启动验证。此时不能运行不可信插件。
3. **平台落地缺口：** SurfCore 只是适配基础，QQ/B站真实账号连接和数据流尚不存在。
4. **认知能力缺口：** CSD/Life Engine 主要是确定性状态与提案骨架，没有真实模型 provider、持续审议和学习更新；不能宣称已经形成自主动机。
5. **规格与范围风险：** CSD/ASM 规格仍未冻结，PR #1 体量很大。若继续并行堆叠功能，容易扩大未验证面并让审查困难。优先收敛协议、验证安全闭环，再接入新能力。
6. **性能证据不足：** 目前部分 replay/投影优化有测试，但尚缺少长历史 wall-clock benchmark 和持续运行压力数据。
7. **用户环境验证缺失：** 用户没有本地克隆仓库；Hosted CI 也不能替代用户 Windows 11 / Python 3.12 环境的最终验证。

## 8. 用户协作约束

- 中文沟通，直接、客观、少安慰、少无意义进度播报。
- 用户授权在无需其操作或决策时自主持续推进。
- 需要用户操作时，一次提出最关键的一项，并说明目的、影响和具体步骤。
- 用户未本机克隆/运行仓库，不要假设有本地测试。
- 重要代码、测试或决策完成后更新 `docs/PROJECT_PROGRESS.md`。
- 每次交接覆盖更新本文件 `docs/HANDOFF_CURRENT.md`。
- 不合并 PR #1。
