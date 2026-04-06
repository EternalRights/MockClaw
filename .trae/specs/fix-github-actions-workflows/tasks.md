# Tasks

## Phase 1: 更新 Actions 版本

- [x] Task 1: 更新 chaos.yml 中的 actions 版本
  - [x] SubTask 1.1: 更新 actions/checkout@v4 到最新版本
  - [x] SubTask 1.2: 更新 actions/setup-python@v5 到最新版本
  - [x] SubTask 1.3: 更新 actions/upload-artifact@v4 到最新版本
  - [x] SubTask 1.4: 更新 peter-evans/create-pull-request@v5 到最新版本

- [x] Task 2: 更新 order_service_test.yml 中的 actions 版本
  - [x] SubTask 2.1: 更新 actions/checkout@v4 到最新版本
  - [x] SubTask 2.2: 更新 actions/setup-python@v5 到最新版本
  - [x] SubTask 2.3: 更新 actions/upload-artifact@v4 到最新版本

## Phase 2: 修复工作流引用

- [x] Task 3: 修复 chaos.yml 中的文件引用
  - [x] SubTask 3.1: 替换 `python regenerate_mocks.py` 为 `python -m src.cli generate tests/gauntlet/flow.har generated_mocks --smart-fallback`
  - [x] SubTask 3.2: 更新 HAR 文件路径检查
  - [x] SubTask 3.3: 确保生成的 mocks 目录路径正确

- [x] Task 4: 修复 order_service_test.yml 中的文件引用
  - [x] SubTask 4.1: 检查 `test_order_service/generate_mocks.py` 是否存在
  - [x] SubTask 4.2: 如果不存在，使用 `python -m src.cli generate` 替代

## Phase 3: 修复 Artifacts 上传

- [x] Task 5: 修复 chaos.yml 中的 artifacts 上传
  - [x] SubTask 5.1: 在上传前创建 logs 目录（如果不存在）
  - [x] SubTask 5.2: 添加 `if-no-files-found: warn` 参数以优雅处理缺失文件
  - [x] SubTask 5.3: 确保测试结果文件正确生成

- [x] Task 6: 修复 order_service_test.yml 中的 artifacts 上传
  - [x] SubTask 6.1: 添加 `if-no-files-found: warn` 参数
  - [x] SubTask 6.2: 确保路径正确

## Phase 4: 添加 Node.js 24 支持

- [x] Task 7: 配置 Node.js 24 环境变量
  - [x] SubTask 7.1: 在所有工作流的 env 部分添加 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'`
  - [x] SubTask 7.2: 验证工作流在 Node.js 24 环境下正常运行

## Phase 5: 验证与测试

- [x] Task 8: 本地验证工作流语法
  - [x] SubTask 8.1: 使用 actionlint 或类似工具验证 YAML 语法
  - [x] SubTask 8.2: 检查所有路径引用

- [x] Task 9: 提交并触发 CI
  - [x] SubTask 9.1: 提交所有更改
  - [x] SubTask 9.2: 推送到 GitHub
  - [x] SubTask 9.3: 验证 GitHub Actions 运行成功

# Task Dependencies
- [Task 3] depends on [Task 1] - 修复引用前先更新版本
- [Task 4] depends on [Task 2] - 修复引用前先更新版本
- [Task 5] depends on [Task 3] - 修复 artifacts 前确保文件正确生成
- [Task 6] depends on [Task 4] - 修复 artifacts 前确保文件正确生成
- [Task 7] depends on [Task 1, Task 2] - 配置环境变量在更新版本后
- [Task 8] depends on [Task 1-7] - 验证在所有修复后进行
- [Task 9] depends on [Task 8] - 提交在本地验证后进行
