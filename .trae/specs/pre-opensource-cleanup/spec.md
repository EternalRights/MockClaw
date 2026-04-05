# 开源前代码优化规范

## Why
MockClaw 项目即将开源，当前代码库存在大量冗余代码、重复的测试目录、以及潜在的安全漏洞。为了提供高质量的开源项目，需要进行全面的代码清理和优化。

## What Changes
- **清理冗余目录**: 删除多个重复的 mock 生成目录（beginner_mocks, example_mocks, my_first_mocks 等）
- **整合测试文件**: 将根目录下的散乱测试文件整合到 tests/ 目录
- **修复安全漏洞**: 修复生成的代码中的 SyntaxWarning 和潜在安全问题
- **优化代码结构**: 统一代码风格，移除未使用的导入和函数
- **完善文档**: 确保所有公开 API 都有完整的文档字符串

## Impact
- **Affected specs**: 整个项目的代码质量和可维护性
- **Affected code**:
  - `src/core/generator.py` - 修复生成的代码中的安全问题
  - `src/cli.py` - 优化命令行工具
  - 根目录下的冗余测试文件 - 移动或删除
  - 多个重复的 mock 目录 - 删除

## ADDED Requirements

### Requirement: 代码质量标准
系统 SHALL 符合以下开源代码质量标准：
- 所有 Python 文件使用一致的代码风格（PEP 8）
- 所有公开函数和类都有完整的文档字符串
- 无未使用的导入和变量
- 无明显的安全漏洞

#### Scenario: 代码风格检查
- **WHEN** 运行代码风格检查工具
- **THEN** 所有文件符合 PEP 8 标准

#### Scenario: 文档完整性
- **WHEN** 检查公开 API
- **THEN** 所有函数和类都有文档字符串

### Requirement: 安全性审计
系统 SHALL 通过基础安全性审计：
- 无硬编码的敏感信息（API 密钥、密码等）
- 生成的代码无语法警告
- 路径遍历防护正确实现
- 输入验证完整

#### Scenario: 敏感信息扫描
- **WHEN** 扫描代码库
- **THEN** 无硬编码的敏感信息

#### Scenario: 语法警告检查
- **WHEN** 启动生成的 mock 服务器
- **THEN** 无 SyntaxWarning 输出

### Requirement: 目录结构规范
项目 SHALL 保持清晰的目录结构：
- `src/` - 核心源代码
- `tests/` - 所有测试文件
- `scripts/` - 辅助脚本
- `docs/` - 文档
- `examples/` - 示例文件
- 根目录下无冗余的生成目录

#### Scenario: 目录清理
- **WHEN** 检查项目根目录
- **THEN** 无重复的 mock 生成目录（如 beginner_mocks, example_mocks 等）

## MODIFIED Requirements

### Requirement: 生成的代码质量
生成的 mock 服务器代码 SHALL 符合以下标准：
- 无语法警告
- 包含正确的安全中间件
- 使用原始字符串处理正则表达式
- 正确的错误处理

#### Scenario: 生成代码无警告
- **WHEN** 生成 mock 服务器
- **THEN** 启动时无 SyntaxWarning

## REMOVED Requirements

### Requirement: 冗余测试目录
**Reason**: 多个重复的 mock 生成目录造成混乱，不利于开源项目的清晰性
**Migration**: 保留 `examples/` 目录作为示例，删除其他所有生成的 mock 目录

### Requirement: 根目录散乱测试文件
**Reason**: 根目录下的测试文件不符合项目结构规范
**Migration**:
- 有价值的测试移动到 `tests/` 目录
- 临时测试文件直接删除
