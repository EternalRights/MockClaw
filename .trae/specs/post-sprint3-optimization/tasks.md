# Tasks

## Phase 1: Code Quality Fixes

- [x] Task 1: Fix SyntaxWarning in generated code
  - [x] SubTask 1.1: Locate the regex pattern string in `src/core/generator.py` (around line 500)
  - [x] SubTask 1.2: Change `dangerous = [r'\\.\\.', ...]` to use raw strings for all patterns
  - [x] SubTask 1.3: Regenerate test mocks and verify no SyntaxWarning on import

- [x] Task 2: Clean up temporary debug files
  - [x] SubTask 2.1: Identify all debug_*.py files in root directory
  - [x] SubTask 2.2: Identify regenerate_mocks.py and other temporary scripts
  - [x] SubTask 2.3: Delete confirmed temporary files (keep only essential files)

## Phase 2: Documentation Enhancement

- [x] Task 3: Add cross-platform testing examples to README
  - [x] SubTask 3.1: Add Windows PowerShell section with Invoke-RestMethod examples
  - [x] SubTask 3.2: Add Python requests library examples (cross-platform)
  - [x] SubTask 3.3: Add cURL examples for Linux/Mac/Git Bash users
  - [x] SubTask 3.4: Ensure all examples include health check, expired coupon, valid coupon tests

## Phase 3: CLI Robustness Improvement

- [x] Task 4: Implement port occupancy pre-check in serve command
  - [x] SubTask 4.1: Add socket-based port availability check before uvicorn.run()
  - [x] SubTask 4.2: Create user-friendly error message with solutions
  - [x] SubTask 4.3: Provide platform-specific commands (netstat for Windows, lsof for Linux)
  - [x] SubTask 4.4: Add fallback suggestion (e.g., --port 8001)

- [x] Task 5: Improve error handling for server startup failures
  - [x] SubTask 5.1: Catch "Address already in use" exception specifically
  - [x] SubTask 5.2: Distinguish between port conflict and other errors
  - [x] SubTask 5.3: Ensure error messages are actionable (not just technical)

## Phase 4: Verification

- [x] Task 6: Test SyntaxWarning fix
  - [x] SubTask 6.1: Generate mocks from sample HAR file
  - [x] SubTask 6.2: Import generated module and check for warnings
  - [x] SubTask 6.3: Verify PathTraversalMiddleware regex patterns are correct

- [ ] Task 7: Test port detection feature
  - [ ] SubTask 7.1: Start a mock server on port 8000
  - [ ] SubTask 7.2: Try to start another server on same port (should fail gracefully)
  - [ ] SubTask 7.3: Verify error message includes helpful suggestions
  - [ ] SubTask 7.4: Test with alternative port (should succeed)

- [ ] Task 8: Validate documentation examples
  - [ ] SubTask 8.1: Copy PowerShell example and verify it works on Windows
  - [ ] SubTask 8.2: Copy Python example and verify it works cross-platform
  - [ ] SubTask 8.3: Verify all examples produce expected results (expired=400, valid=200)

# Task Dependencies
- [Task 2] depends on [Task 1] - 清理文件前先确保代码修复完成
- [Task 3] can run in parallel with [Task 1, Task 2]
- [Task 4] depends on [Task 1] - CLI 改进应在代码修复后进行
- [Task 5] depends on [Task 4] - 错误处理改进在端口检测之后
- [Task 6] depends on [Task 1] - 验证代码修复效果
- [Task 7] depends on [Task 4, Task 5] - 验证 CLI 改进
- [Task 8] depends on [Task 3] - 验证文档示例
