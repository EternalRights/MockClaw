# 大规模优化：让项目真正能用 Spec

## Why
项目核心路径断裂：`mockclaw example` 跑不通（缺 sample.har），start.bat 硬编码路径，README 声称的功能与实际不符（无 LICENSE、引用不存在的文档、假引言），Smart Fallback 只识别 5 个硬编码字段名导致不通用。需要让项目从"半成品"变成"自己每天能用"。

## What Changes
- **修复 `mockclaw example` 核心路径**：将 `tests/gauntlet/flow.har` 复制到 `examples/sample.har`，确保开箱即用
- **修复 `start.bat` 硬编码路径**：改为相对路径 `%~dp0`
- **重写 Smart Fallback 为通用自动分析**：不再硬编码字段名，改为自动对比同一 endpoint 的多个 request body，找出值不同的字段作为 routing key
- **添加 LICENSE 文件**（MIT）
- **重写 README**：删除假引言、删除不存在的截图引用、删除引用不存在的 docs/API.md、修正"2分钟"夸大宣传、修正"0用户"的社区链接
- **删除 Web UI 相关内容**：README 中 Web UI 选项、截图引用

## Impact
- Affected code: `src/core/generator.py`（Smart Fallback 重写）, `src/cli.py`（example 命令）, `start.bat`, `README.md`
- **BREAKING**: Smart Fallback 不再依赖硬编码字段名，改为自动分析。旧代码如果依赖 `["coupon", "coupon_code", "status", "type", "action"]` 这些特定字段名，行为会变化（更通用）

## ADDED Requirements

### Requirement: 开箱即用的 example 命令
系统 SHALL 在 `examples/sample.har` 提供预置的 HAR 文件，确保 `mockclaw example` 无需任何前置步骤即可运行。

#### Scenario: 新用户首次运行
- **WHEN** 用户 clone 仓库后直接运行 `mockclaw example`
- **THEN** 命令成功生成并启动 mock server，无需先运行 dummy_shop 或 recorder

### Requirement: 通用 Smart Fallback 自动分析
系统 SHALL 自动分析同一 endpoint 的多个 request body，找出值不同的字段作为 routing key，不再硬编码特定字段名。

#### Scenario: 自动识别差异字段
- **WHEN** 同一 POST endpoint 有 3 个 HAR entry，request body 分别为 `{"user_id":"a","role":"admin"}`, `{"user_id":"b","role":"user"}`, `{"user_id":"c","role":"guest"}`
- **THEN** 系统自动识别 `role` 为差异字段（3个值不同），`user_id` 也为差异字段，选择区分度最高的字段生成 if/elif/else 路由

#### Scenario: 无差异字段时回退
- **WHEN** 同一 endpoint 的所有 request body 完全相同或只有一个 entry
- **THEN** 系统回退到普通 fallback 模式（返回第一个 response）

### Requirement: 相对路径启动脚本
系统 SHALL 使用相对路径启动，不硬编码绝对路径。

#### Scenario: 其他用户 clone 后启动
- **WHEN** 用户在任意目录 clone 仓库后运行 `start.bat`
- **THEN** 脚本正确找到 `src/brain.py` 并启动

## MODIFIED Requirements

### Requirement: README 准确性
README SHALL 仅描述实际存在的功能和文件，不引用不存在的文档、截图或社区链接。

## REMOVED Requirements

### Requirement: 硬编码字段名 Smart Fallback
**Reason**: 只识别 `["coupon", "coupon_code", "status", "type", "action"]` 5 个字段名，不通用。一个"通用"mock 生成器只认识 coupon_code 是自限性的。
**Migration**: 改为自动分析差异字段，完全向后兼容（原有 coupon_code 场景仍然工作，因为差异字段会被自动识别）。

### Requirement: README 中的假引言和夸大宣传
**Reason**: "Every MockClaw User Ever" 是假引言，"2分钟" 实际需要多个前置步骤，"God-Mode" 过度吹嘘。
**Migration**: 改为真实描述。
