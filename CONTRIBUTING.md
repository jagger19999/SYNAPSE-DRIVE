# 贡献指南 (Contributing Guidelines)

感谢您有兴趣为驾驶多模态数据采集同步软件项目做出贡献！我们欢迎各种类型的贡献，包括错误修复、新功能、文档改进等。

## 🚀 如何开始贡献

### 1. Fork 项目
1. 点击 GitHub 上的 "Fork" 按钮
2. 将项目克隆到您的本地环境
```bash
git clone https://github.com/your-username/multimodal-sync.git
cd multimodal-sync
```

### 2. 设置开发环境
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e .[dev]
```

### 3. 创建分支
```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-description
```

## 📝 贡献类型

### 🐛 错误报告
- 使用 [Issue Template](https://github.com/your-username/multimodal-sync/issues/new/choose)
- 提供详细的错误描述和复现步骤
- 包含系统环境信息（操作系统、Python版本等）
- 提供错误日志和相关截图

### ✨ 新功能
- 先创建 Issue 讨论新功能的必要性
- 确保新功能与项目目标一致
- 编写相应的测试用例
- 更新相关文档

### 📖 文档改进
- 修复拼写错误和语法问题
- 改进代码注释和文档字符串
- 添加使用示例和教程
- 翻译文档到不同语言

### 🧪 测试
- 添加单元测试和集成测试
- 提高测试覆盖率
- 修复测试用例中的问题
- 优化测试性能

## 🔧 开发规范

### 代码风格
- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) Python编码规范
- 使用 [Black](https://black.readthedocs.io/) 进行代码格式化
- 使用 [Flake8](https://flake8.pycqa.org/) 进行代码检查
- 添加类型提示（Type Hints）

### 提交信息
- 使用清晰、有意义的提交信息
- 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范
- 提交信息格式：`类型: 简短描述`

提交类型：
- `feat`: 新功能
- `fix`: 错误修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

示例：
```
feat: 添加Tobii眼动仪数据预处理功能
fix: 修复LSL数据流连接超时问题
docs: 更新安装指南中的依赖版本要求
```

### 测试要求
- 所有新功能必须包含相应的测试用例
- 确保所有测试在提交前通过
- 保持测试覆盖率不低于80%
- 运行测试命令：`pytest tests/`

## 📋 提交流程

### 1. 代码检查
```bash
# 格式化代码
black src/ tests/

# 代码检查
flake8 src/ tests/

# 类型检查
mypy src/

# 运行测试
pytest tests/
```

### 2. 提交更改
```bash
git add .
git commit -m "feat: 您的提交信息"
```

### 3. 推送到您的Fork
```bash
git push origin feature/your-feature-name
```

### 4. 创建Pull Request
1. 访问 GitHub 上的您的Fork
2. 点击 "New Pull Request"
3. 填写PR模板，描述您的更改
4. 确保CI/CD检查通过
5. 等待代码审查

## 🎯 Pull Request 模板

### 功能PR模板
```markdown
## 功能描述
简要描述这个PR的功能

## 变更类型
- [ ] 新功能 (feat)
- [ ] 错误修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 代码重构 (refactor)
- [ ] 性能优化 (perf)
- [ ] 测试相关 (test)

## 测试
- [ ] 添加了新的测试用例
- [ ] 所有现有测试通过
- [ ] 手动测试完成

## 文档
- [ ] 更新了相关文档
- [ ] 添加了代码注释
- [ ] 更新了API文档

## 检查清单
- [ ] 代码遵循项目编码规范
- [ ] 自测通过
- [ ] 文档已更新
- [ ] 没有引入新的依赖
```

## 🎨 设计原则

### 代码质量
- **可读性**: 代码应该易于理解和维护
- **可测试性**: 代码应该易于测试
- **可扩展性**: 设计应该支持未来的功能扩展
- **性能**: 关注性能，但不要过早优化

### 架构原则
- **模块化**: 功能应该模块化，降低耦合度
- **配置化**: 支持通过配置文件调整行为
- **错误处理**: 完善的错误处理和日志记录
- **兼容性**: 保持向后兼容性

## 📞 联系方式


[王杰](851590822@qq.com)





## 📄 许可证

通过贡献代码，您同意您的贡献将在与项目相同的 [MIT 许可证](../LICENSE) 下发布。

## 🙏 感谢

感谢您为驾驶多模态数据采集同步软件项目做出的贡献！您的每一份贡献都将帮助科研社区更好地进行驾驶行为研究。
