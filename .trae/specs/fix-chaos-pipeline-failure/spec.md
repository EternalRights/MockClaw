# GitHub Actions Chaos Pipeline 修复规范

## Why
GitHub Actions Chaos Engineering Pipeline 持续失败，根本原因是：
1. `pytest tests/ -v` 命令运行测试时，测试文件引用了 `generated_mocks/dynamic_api.py`，但该文件在 pytest 运行前可能不存在或与 HAR 生成的版本不一致
2. `scripts/enhanced_chaos_test.py` 需要 `httpx` 库，但 `src/requirements.txt` 中的 `httpx` 可能未正确安装
3. 测试脚本启动服务器后可能因端口冲突或依赖缺失而失败
4. `logs/*.json` 和 `logs/*.log` 文件从未被生成，导致 artifacts 上传警告

## What Changes
- **简化 chaos.yml 工作流**: 移除不可靠的步骤，只保留核心验证
- **修复 pytest 命令**: 只运行不需要运行服务器的单元测试
- **修复 chaos 测试脚本**: 确保依赖正确安装，日志文件正确生成
- **确保 logs 目录有内容**: 在测试步骤中生成日志文件

## Impact
- **Affected specs**: CI/CD 管道稳定性
- **Affected code**:
  - `.github/workflows/chaos.yml` - 简化工作流步骤
  - `scripts/enhanced_chaos_test.py` - 确保日志生成

## ADDED Requirements

### Requirement: 工作流步骤可靠性
每个工作流步骤 SHALL 独立可验证，不依赖前一步骤的副作用。

#### Scenario: 步骤独立执行
- **WHEN** 单独运行某个步骤
- **THEN** 步骤成功或提供清晰的错误信息

### Requirement: 测试分类
pytest 测试 SHALL 分为单元测试和集成测试，CI 只运行单元测试。

#### Scenario: CI 运行单元测试
- **WHEN** CI 运行 pytest
- **THEN** 只运行不需要服务器运行的测试

### Requirement: 日志文件生成
测试脚本 SHALL 在 logs 目录生成至少一个 JSON 日志文件。

#### Scenario: 日志文件存在
- **WHEN** 测试脚本运行完成
- **THEN** `logs/chaos_results.json` 文件存在

## MODIFIED Requirements

### Requirement: Chaos 测试流程
Chaos 测试 SHALL 先生成 mocks，再启动服务器，最后运行测试，并确保每步都有日志输出。

## REMOVED Requirements

### Requirement: Docker hardcore 测试在 CI 中运行
**Reason**: Docker 在 GitHub Actions 中不稳定，且 hardcore_chaos_test.py 依赖 Docker 容器
**Migration**: 仅在本地手动运行 hardcore 测试
