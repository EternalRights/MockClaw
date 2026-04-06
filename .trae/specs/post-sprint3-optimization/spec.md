# Post-Sprint 3 Optimization Spec

## Why
在 Sprint 3 完成后，通过实际使用和 Fresh Install 测试发现了几个影响用户体验的问题：
1. 生成的代码存在 SyntaxWarning 警告
2. Windows PowerShell 下 curl 命令不兼容，缺少跨平台测试示例
3. 端口被占用时错误提示不够友好，用户不知道如何解决
4. 需要进一步提升 CLI 工具的健壮性和用户体验

## What Changes
- 修复生成代码中的正则表达式转义问题 (SyntaxWarning)
- 添加多平台测试示例 (PowerShell, Python, cURL)
- 改进端口占用检测和错误提示
- 优化 CLI serve 命令的启动前检查逻辑
- 清理临时调试文件

## Impact
- Affected specs: 无 (独立优化)
- Affected code:
  - `src/core/generator.py` - 正则表达式字符串修复
  - `src/cli.py` - 端口检测和错误提示改进
  - `README.md` - 添加多平台测试示例

## ADDED Requirements

### Requirement: Code Quality Improvement
系统 SHALL 生成无 SyntaxWarning 的 Python 代码。

#### Scenario: Generate mocks without warnings
- **WHEN** 用户运行 `mockclaw generate flow.har --smart-fallback`
- **THEN** 生成的 dynamic_api.py 文件导入时不应产生任何警告信息

### Requirement: Cross-Platform Testing Support
README SHALL 提供至少三种平台的 API 测试示例。

#### Scenario: User wants to test generated mock server on different platforms
- **WHEN** 用户查看 README 的 "Testing with Different Tools" 章节
- **THEN** 应该看到 PowerShell、Python、cURL 三种完整的测试代码示例
- **AND** 每种示例都包含健康检查、过期优惠券、有效优惠券三个测试用例

### Requirement: Port Occupancy Detection
CLI serve 命令 SHALL 在启动服务器前检测端口是否可用。

#### Scenario: Port already in use
- **WHEN** 用户运行 `mockclaw serve ./my_mocks --port 8000` 且端口 8000 已被占用
- **THEN** 系统应在启动前检测到冲突
- **AND** 显示清晰的错误信息和解决方案（包括替代端口号、查找进程命令等）
- **AND** 区分 Windows 和 Linux 提供不同的排查命令

### Requirement: Clean Debug Files
项目目录不应包含临时调试文件。

#### Scenario: Clean project structure
- **WHEN** 开发者查看项目根目录
- **THEN** 不应看到 debug_*.py、regenerate_mocks.py 等临时调试文件

## MODIFIED Requirements

### Requirement: Smart Fallback Generator
生成器 SHALL 使用正确的字符串格式避免正则表达式警告。

#### Scenario: Generated code has proper regex patterns
- **WHEN** 生成器创建 PathTraversalMiddleware 代码
- **THEN** 所有正则表达式应使用原始字符串 (raw string) 格式
- **AND** 不应出现 `SyntaxWarning: invalid escape sequence` 警告

## REMOVED Requirements

无
