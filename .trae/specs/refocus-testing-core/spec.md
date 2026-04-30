# 回归测试开发核心定位 - 精简优化 Spec

## Why
项目在多轮迭代中膨胀了大量与"测试开发"核心场景无关的内容：虚构的 Docker 微服务架构、引用不存在文件的 CI workflow、空目录占位、过时文档、重复的示例数据目录等。需要回归核心定位：**HAR -> Mock Server -> 测试**。

## What Changes
- **删除 `docker-compose.yml`** — 引用不存在的服务（capture、redis、mock-server Node.js），brain 服务入口 `main:app` 也不对
- **删除 `.github/workflows/order_service_test.yml`** — 引用不存在的 `test_order_service/` 目录和脚本
- **删除 `sample_data/` 目录** — 与 `examples/` 和 `tests/gauntlet/` 功能重复，且 `sample_data/flow.har` 与 `tests/gauntlet/flow.har` 内容重复
- **删除 `examples/` 目录** — 只有 README.md，没有实际 sample.har 文件（README 中引用的文件不存在）
- **删除 `CODE_OF_CONDUCT.md`** — 模板内容，占位符 `[INSERT CONTACT METHOD]` 未填写，对测试工具无意义
- **删除 `CONTRIBUTING.md`** — 引用不存在的 `requirements-dev.txt`、`pre-commit`，对测试工具过于正式
- **删除 `QUICKSTART.md` 和 `QUICKSTART_CN.md`** — 与 README 的 Quick Start 重复，且内容过时（引用 `--hardcore`、`streamlit` 等已删除功能）
- **删除 `CHANGELOG.md`** — 内容过时（引用 resilience.py、hardcore_chaos_test.py 等已删除内容）
- **精简 `start.bat` / `start.sh`** — 引用 `web/app.py`（已删除的 Streamlit），改为仅启动 brain.py
- **更新 `README.md`** — 移除引用已删除功能的 badge 和内容
- **更新 `docs/architecture.md`** — 移除引用已删除的 resilience.py
- **更新 `chaos.yml`** — 移除对 `pytest-asyncio` 的单独安装（已在 dev extras 中）
- **精简 `gauntlet_recorder.py`** — 移除引用已删除的 `ci_immortal.bat`

## Impact
- Affected code: docker-compose.yml, CI workflows, 文档, 启动脚本, recorder
- **BREAKING**: 删除 docker-compose.yml（从未能正常工作）
- **BREAKING**: 删除 order_service_test.yml workflow（引用不存在的目录）

## MODIFIED Requirements

### Requirement: 项目结构
项目 SHALL 仅保留与核心流程直接相关的文件：HAR 解析 -> Mock 生成 -> Mock 服务 -> 测试验证。

### Requirement: README
README SHALL 不引用已删除的功能（--hardcore、streamlit、hardcore_chaos_test.py）。

## REMOVED Requirements

### Requirement: Docker Compose 微服务架构
**Reason**: docker-compose.yml 引用 5 个服务但其中 3 个不存在（capture、redis、mock-server），brain 入口 `main:app` 也不对。这是一个从未能运行的配置。
**Migration**: 如未来需要容器化，应从零设计基于实际代码的 Dockerfile。

### Requirement: order_service_test CI workflow
**Reason**: 引用 `test_order_service/` 目录和脚本，该目录不存在。
**Migration**: 无需迁移。

### Requirement: sample_data 目录
**Reason**: 与 `tests/gauntlet/flow.har` 内容重复。
**Migration**: 使用 `tests/gauntlet/flow.har` 作为标准测试数据。

### Requirement: examples 目录
**Reason**: 只有 README.md，没有实际的 sample.har 文件。
**Migration**: `mockclaw example` 命令已从 `tests/gauntlet/flow.har` 复制。

### Requirement: CODE_OF_CONDUCT.md / CONTRIBUTING.md / QUICKSTART*.md / CHANGELOG.md
**Reason**: 模板/过时/重复内容，对测试开发工具无实际价值。
**Migration**: 无需迁移。
