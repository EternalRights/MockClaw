# Tasks

- [x] Task 1: 修复 mockclaw example 核心路径
  - [x] 创建 `examples/` 目录，将 `tests/gauntlet/flow.har` 复制为 `examples/sample.har`
  - [x] 更新 `src/cli.py` 的 `example` 命令：直接使用 `examples/sample.har`，不再 fallback 到 gauntlet 目录或要求用户先跑 recorder

- [x] Task 2: 修复 start.bat 硬编码路径
  - [x] 将 `cd /d D:\MockClaw` 改为 `cd /d "%~dp0"`（自动定位到脚本所在目录）

- [x] Task 3: 重写 Smart Fallback 为通用自动分析
  - [x] 重写 `_generate_smart_route()` 函数，移除硬编码字段名 `["coupon", "coupon_code", "status", "type", "action"]`
  - [x] 实现自动差异分析算法：对比同一 endpoint 的所有 request body，找出值不同的字段
  - [x] 选择区分度最高的字段（值种类最多的字段）作为 routing key
  - [x] 生成 if/elif/else 路由，保持与现有生成代码格式一致
  - [x] 无差异字段时回退到普通 fallback

- [x] Task 4: 添加 LICENSE 文件
  - [x] 创建 `LICENSE` 文件，使用 MIT 许可证，年份 2024-2026，版权所有者 MockClaw Contributors

- [x] Task 5: 重写 README.md
  - [x] 删除假引言 "Every MockClaw User Ever"
  - [x] 删除截图引用 `![MockClaw Web UI](docs/screenshots/web-ui.png)`
  - [x] 删除引用不存在的 `docs/API.md`，改为 `docs/architecture.md`
  - [x] 删除 Web UI 选项（Option 1），CLI 作为唯一推荐方式
  - [x] 删除 Docker Deployment 部分（docker-compose.yml 已删除）
  - [x] 删除 Benchmarks 表格（虚假数据）
  - [x] 删除 "Join the Community" 部分（假链接 @MockClaw、假 GitHub Issues URL）
  - [x] 删除 "God-Mode" 和 "under 2 minutes" 夸大宣传
  - [x] 修正 "60-Second Quick Start" 为真实步骤
  - [x] 修正 Contributing 部分：删除引用已删除的 CONTRIBUTING.md
  - [x] Smart Fallback 示例代码改为展示通用自动分析能力

- [x] Task 6: 端到端验证
  - [x] 运行 pytest 确认所有测试通过 (19 passed, 0 failed)
  - [x] 验证 Smart Fallback 对非 coupon_code 字段也能生成路由 (role 字段测试通过)
  - [x] 验证 examples/sample.har 存在且可用 (3 endpoints)
  - [x] 验证 LICENSE 文件存在
  - [x] 验证 start.bat 使用相对路径

# Task Dependencies
- Task 3 是核心改动，其他任务独立
- Task 6 depends on all other tasks
