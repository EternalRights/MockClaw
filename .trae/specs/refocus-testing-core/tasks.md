# Tasks

- [x] Task 1: 删除与核心测试流程无关的文件
  - [x] 删除 `docker-compose.yml`（引用不存在的服务，从未能运行）
  - [x] 删除 `.github/workflows/order_service_test.yml`（引用不存在的 test_order_service/ 目录）
  - [x] 删除 `sample_data/` 目录（与 tests/gauntlet/flow.har 重复）
  - [x] 删除 `examples/` 目录（只有 README，没有实际 HAR 文件）
  - [x] 删除 `CODE_OF_CONDUCT.md`（模板占位符未填写）
  - [x] 删除 `CONTRIBUTING.md`（引用不存在的 requirements-dev.txt、pre-commit）
  - [x] 删除 `QUICKSTART.md`（与 README 重复，引用已删除功能）
  - [x] 删除 `QUICKSTART_CN.md`（同上）
  - [x] 删除 `CHANGELOG.md`（引用已删除的 resilience.py、hardcore_chaos_test.py 等）

- [x] Task 2: 精简启动脚本
  - [x] 更新 `start.bat`：移除对已删除 web/app.py 的引用，改为仅启动 brain.py
  - [x] 更新 `start.sh`：同上

- [x] Task 3: 更新 README.md
  - [x] 移除 badge 中引用已删除文件的链接（Streamlit、hardcore_chaos_test.py）
  - [x] 移除 Chaos Engineering 部分中引用 `scripts/hardcore_chaos_test.py --use-docker` 的内容
  - [x] 移除 CLI Commands 中 `--hardcore` 选项
  - [x] 移除 Contributing 部分中 `streamlit run web/app.py`
  - [x] 移除 Acknowledgments 中 Streamlit 引用
  - [x] 移除 Roadmap 中过时的 Sprint 3 状态

- [x] Task 4: 更新文档和 CI
  - [x] 更新 `docs/architecture.md`：移除引用 `core/resilience.py` 的行
  - [x] 更新 `.github/workflows/chaos.yml`：移除单独安装 `pytest-asyncio` 的步骤（已在 dev extras 中）
  - [x] 更新 `scripts/gauntlet_recorder.py`：移除引用 `scripts/ci_immortal.bat` 的行

- [x] Task 5: 验证
  - [x] 运行 pytest 确认所有测试通过 (19 passed, 0 failed)
  - [x] 运行生成功能验证端到端流程正常 (2/2 endpoints)

# Task Dependencies
- Task 2, 3, 4 depend on Task 1 (文件删除后更新引用)
- Task 5 depends on all other tasks
