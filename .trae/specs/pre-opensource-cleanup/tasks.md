# Tasks

## Phase 1: 代码质量审计与修复

- [x] Task 1: 修复生成代码中的 SyntaxWarning
  - [x] SubTask 1.1: 检查 `src/core/generator.py` 中生成的正则表达式字符串
  - [x] SubTask 1.2: 将 `\.\.` 等转义序列改为原始字符串 `r'\.\.'`
  - [x] SubTask 1.3: 验证生成的代码启动时无警告

- [x] Task 2: 代码风格统一
  - [x] SubTask 2.1: 检查所有 Python 文件的导入语句
  - [x] SubTask 2.2: 移除未使用的导入
  - [x] SubTask 2.3: 统一代码格式（使用 black 或 autopep8）

- [x] Task 3: 文档字符串完善
  - [x] SubTask 3.1: 检查 `src/core/` 下所有公开函数
  - [x] SubTask 3.2: 为缺少文档字符串的函数添加说明
  - [x] SubTask 3.3: 确保文档字符串格式一致（Google 或 NumPy 风格）

## Phase 2: 安全性审计

- [x] Task 4: 敏感信息扫描
  - [x] SubTask 4.1: 扫描所有文件中的硬编码密钥
  - [x] SubTask 4.2: 检查 `.env.example` 是否包含示例值而非真实值
  - [x] SubTask 4.3: 确保 `.gitignore` 包含敏感文件模式

- [x] Task 5: 输入验证审计
  - [x] SubTask 5.1: 检查 `src/core/middleware.py` 中的路径遍历防护
  - [x] SubTask 5.2: 验证所有端点都有适当的输入验证
  - [x] SubTask 5.3: 检查 SQL 注入防护（如有数据库操作）

- [x] Task 6: 依赖安全检查
  - [x] SubTask 6.1: 检查 `src/requirements.txt` 中的依赖版本
  - [x] SubTask 6.2: 运行 `pip-audit` 或类似工具检查已知漏洞
  - [x] SubTask 6.3: 更新有安全问题的依赖

## Phase 3: 目录结构优化

- [x] Task 7: 清理冗余的 mock 目录
  - [x] SubTask 7.1: 列出所有 mock 生成目录
  - [x] SubTask 7.2: 确认哪些目录可以删除
  - [x] SubTask 7.3: 删除确认的冗余目录（最后执行）

- [x] Task 8: 整合根目录测试文件
  - [x] SubTask 8.1: 评估根目录下的测试文件价值
  - [x] SubTask 8.2: 将有价值的测试移动到 `tests/` 目录
  - [x] SubTask 8.3: 删除临时测试文件（最后执行）

- [x] Task 9: 优化示例目录
  - [x] SubTask 9.1: 确保 `examples/` 目录包含清晰的示例
  - [x] SubTask 9.2: 添加示例的 README 说明
  - [x] SubTask 9.3: 删除其他示例目录（最后执行）

## Phase 4: 文档完善

- [x] Task 10: 更新 README.md
  - [x] SubTask 10.1: 确保安装说明准确
  - [x] SubTask 10.2: 添加 Windows PowerShell 示例
  - [x] SubTask 10.3: 更新项目状态和版本信息

- [x] Task 11: 完善贡献指南
  - [x] SubTask 11.1: 检查 `CONTRIBUTING.md` 的完整性
  - [x] SubTask 11.2: 添加代码风格指南
  - [x] SubTask 11.3: 添加 PR 提交规范

- [x] Task 12: 创建 CHANGELOG
  - [x] SubTask 12.1: 整理版本历史
  - [x] SubTask 12.2: 按语义化版本格式记录变更
  - [x] SubTask 12.3: 添加开源准备说明

## Phase 5: 最终验证

- [x] Task 13: 全面测试
  - [x] SubTask 13.1: 运行所有单元测试
  - [x] SubTask 13.2: 运行集成测试
  - [x] SubTask 13.3: 验证 CLI 命令正常工作

- [x] Task 14: 开源前检查清单
  - [x] SubTask 14.1: 检查 LICENSE 文件
  - [x] SubTask 14.2: 检查 CODE_OF_CONDUCT.md
  - [x] SubTask 14.3: 检查 .gitignore 完整性
  - [x] SubTask 14.4: 检查 GitHub Actions 工作流

# Task Dependencies
- [Task 7] depends on [Task 1, Task 2, Task 3] - 清理目录前先确保代码质量
- [Task 8] depends on [Task 2] - 整合测试前先统一代码风格
- [Task 13] depends on [Task 1-12] - 最终测试在所有优化后进行
- [Task 14] depends on [Task 13] - 开源前检查在所有测试通过后进行
