# GitHub Actions 工作流 HAR 文件缺失修复规范

## Why
GitHub Actions 工作流失败，因为引用的 HAR 文件 (`tests/gauntlet/flow.har` 和 `sample_data/flow.har`) 不存在。需要创建示例 HAR 文件或更新工作流以处理缺失情况。

## What Changes
- **创建示例 HAR 文件**: 生成一个基本的 HAR 文件用于测试
- **更新工作流**: 添加 HAR 文件缺失时的优雅处理
- **确保 logs 目录**: 在测试前创建 logs 目录以避免 artifacts 上传失败
- **移除 Node.js 警告**: 由于 GitHub Actions 的 actions 还未完全迁移到 Node.js 24，警告是预期的，可以忽略

## Impact
- **Affected specs**: CI/CD 管道的稳定性
- **Affected code**:
  - `.github/workflows/chaos.yml` - 添加 HAR 文件检查和 logs 目录创建
  - `tests/gauntlet/flow.har` - 创建示例 HAR 文件
  - `sample_data/flow.har` - 创建示例 HAR 文件

## ADDED Requirements

### Requirement: HAR 文件可用性
工作流 SHALL 能够访问有效的 HAR 文件进行测试。

#### Scenario: HAR 文件存在
- **WHEN** 工作流运行
- **THEN** HAR 文件存在于预期位置

#### Scenario: HAR 文件缺失处理
- **WHEN** HAR 文件不存在
- **THEN** 工作流提供清晰的错误信息并优雅失败

### Requirement: Logs 目录存在
测试脚本 SHALL 创建 logs 目录以确保 artifacts 上传成功。

#### Scenario: Logs 目录创建
- **WHEN** 测试开始前
- **THEN** logs 目录已创建

#### Scenario: Artifacts 上传成功
- **WHEN** 测试完成后
- **THEN** 至少有一个日志文件可供上传

## MODIFIED Requirements

### Requirement: 工作流错误处理
工作流 SHALL 提供清晰的错误信息，帮助开发者快速定位问题。

#### Scenario: HAR 文件缺失错误
- **WHEN** HAR 文件不存在
- **THEN** 错误信息明确指出文件路径和解决方案

## REMOVED Requirements

### Requirement: Node.js 20 弃用警告消除
**Reason**: GitHub Actions 的官方 actions（checkout, setup-python, upload-artifact）尚未完全迁移到 Node.js 24，警告是 GitHub 的预期行为，无法在工作流层面消除
**Migration**: 忽略警告，等待 GitHub 在 2026 年秋季完成迁移
