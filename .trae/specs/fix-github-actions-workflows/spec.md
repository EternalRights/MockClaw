# GitHub Actions 工作流修复规范

## Why
GitHub Actions 工作流出现多个问题：Node.js 20 弃用警告、工作流执行失败（引用已删除的文件）、以及 artifacts 上传失败。需要修复这些问题以确保 CI/CD 管道正常运行。

## What Changes
- **更新 GitHub Actions 版本**: 迁移到支持 Node.js 24 的 actions 版本
- **修复工作流引用**: 更新已删除文件的引用路径
- **修复 artifacts 上传**: 确保 logs 目录存在或正确处理缺失情况
- **添加环境变量**: 设置 FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true 以提前使用 Node.js 24

## Impact
- **Affected specs**: CI/CD 管道的稳定性和兼容性
- **Affected code**:
  - `.github/workflows/chaos.yml` - 更新 actions 版本和修复路径引用
  - `.github/workflows/order_service_test.yml` - 更新 actions 版本

## ADDED Requirements

### Requirement: GitHub Actions Node.js 24 兼容性
所有 GitHub Actions 工作流 SHALL 使用支持 Node.js 24 的 actions 版本，以避免弃用警告。

#### Scenario: Node.js 版本兼容
- **WHEN** GitHub Actions 运行工作流
- **THEN** 无 Node.js 20 弃用警告

#### Scenario: Actions 版本更新
- **WHEN** 检查工作流文件
- **THEN** 所有 actions 使用最新稳定版本

### Requirement: 工作流执行稳定性
GitHub Actions 工作流 SHALL 正确执行所有步骤，无因文件缺失导致的失败。

#### Scenario: 文件引用正确
- **WHEN** 工作流引用脚本或文件
- **THEN** 引用的文件存在于代码库中

#### Scenario: 错误处理完善
- **WHEN** 可选步骤失败
- **THEN** 工作流继续执行并提供清晰的错误信息

### Requirement: Artifacts 上传可靠性
Artifacts 上传步骤 SHALL 正确处理文件存在和缺失的情况。

#### Scenario: 文件存在时上传
- **WHEN** logs 目录包含文件
- **THEN** artifacts 成功上传

#### Scenario: 文件缺失时优雅处理
- **WHEN** logs 目录不存在或为空
- **THEN** 工作流不因 artifacts 上传失败而中断

## MODIFIED Requirements

### Requirement: 工作流环境配置
工作流 SHALL 配置正确的环境变量以支持 Node.js 24 迁移。

#### Scenario: 环境变量设置
- **WHEN** 工作流启动
- **THEN** FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true 已设置

## REMOVED Requirements

### Requirement: 旧的文件引用
**Reason**: `regenerate_mocks.py` 已在代码清理中删除
**Migration**: 使用 `python -m src.cli generate` 命令替代
