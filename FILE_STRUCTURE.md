# 发布包结构说明

## 📦 完整目录结构

```
peripheral-monitor-skill/
│
├── README.md                      # 用户手册（面向使用者）
├── SKILL_SPEC.md                  # 技术规范（面向维护者）
├── ONE_COMMAND_RUN.md             # 一键运行指南
├── .env.example                   # 环境变量示例
├── .gitignore                     # Git 忽略规则
│
├── requirements.txt                # Python 依赖清单
├── config.py                      # 配置文件
│
├── etl_pipeline.py                # 主程序（ETL + 报告生成）
├── spider.py                      # 爬虫程序（可选）
│
├── scripts/                       # 脚本目录
│   ├── validate_report.py        # 报告校验脚本
│   ├── install.sh                # 一键安装脚本 (Linux/macOS)
│   └── install.bat               # 一键安装脚本 (Windows)
│
├── examples/                      # 示例目录
│   ├── QUICKSTART.md             # 快速开始指南
│   ├── input_example.json        # 输入数据示例
│   └── output_example.html       # 输出报告示例（TODO: 添加真实示例）
│
└── output/                        # 输出目录（运行时生成）
    ├── monthly_report_YYYY_MM.html  # PM 深度分析报告
    ├── processed_products.json      # 处理后的产品数据
    └── report_data_YYYY_MM.json     # 原始输入数据
```

---

## 📋 文件清单

### 核心文件（必需）

| 文件 | 说明 | 大小 | 必需性 |
|------|------|------|--------|
| `etl_pipeline.py` | 主程序：数据清洗 → LLM分析 → 报告生成 | ~150KB | ✅ 必需 |
| `config.py` | 配置文件：目标年月、输出路径等 | ~2KB | ✅ 必需 |
| `requirements.txt` | Python 依赖清单 | ~1KB | ✅ 必需 |

### 文档文件（必需）

| 文件 | 说明 | 大小 | 必需性 |
|------|------|------|--------|
| `README.md` | 用户手册：安装、配置、使用 | ~10KB | ✅ 必需 |
| `SKILL_SPEC.md` | 技术规范：流程、Schema、扩展点 | ~25KB | ✅ 必需 |
| `ONE_COMMAND_RUN.md` | 一键运行指南 | ~8KB | ✅ 必需 |

### 配置文件（必需）

| 文件 | 说明 | 大小 | 必需性 |
|------|------|------|--------|
| `.env.example` | 环境变量示例 | ~2KB | ✅ 必需 |
| `.gitignore` | Git 忽略规则 | ~1KB | ⭕ 可选 |

### 脚本文件（推荐）

| 文件 | 说明 | 大小 | 必需性 |
|------|------|------|--------|
| `scripts/validate_report.py` | 报告校验脚本 | ~3KB | ⭐ 推荐 |
| `scripts/install.sh` | 一键安装 (Linux/macOS) | ~2KB | ⭐ 推荐 |
| `scripts/install.bat` | 一键安装 (Windows) | ~2KB | ⭐ 推荐 |

### 示例文件（推荐）

| 文件 | 说明 | 大小 | 必需性 |
|------|------|------|--------|
| `examples/QUICKSTART.md` | 快速开始指南 | ~5KB | ⭐ 推荐 |
| `examples/input_example.json` | 输入数据示例 | ~1KB | ⭐ 推荐 |

### 可选文件

| 文件 | 说明 | 大小 | 必需性 |
|------|------|------|--------|
| `spider.py` | 爬虫程序（可使用已有数据） | ~20KB | ⭕ 可选 |

---

## 🚀 最小发布包（核心文件）

如果你只需要核心功能，可以只发布以下文件：

```
minimal-skill/
├── README.md
├── requirements.txt
├── .env.example
├── config.py
├── etl_pipeline.py
└── output/  (空目录，运行时生成)
```

**使用方法**：
```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
python etl_pipeline.py --template pm_deep
```

---

## 📦 完整发布包（推荐）

包含所有文档、脚本和示例：

```
full-skill/
├── README.md
├── SKILL_SPEC.md
├── ONE_COMMAND_RUN.md
├── .env.example
├── .gitignore
├── requirements.txt
├── config.py
├── etl_pipeline.py
├── spider.py
├── scripts/
│   ├── validate_report.py
│   ├── install.sh
│   └── install.bat
├── examples/
│   ├── QUICKSTART.md
│   └── input_example.json
└── output/  (空目录)
```

---

## 🎯 使用者需要做什么？

### 方式 1: 使用安装脚本（推荐）

```bash
# Linux/macOS
bash scripts/install.sh

# Windows
scripts\install.bat

# 然后编辑 .env 文件填入 API Key
nano .env  # 或 notepad .env
```

### 方式 2: 手动安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建配置
cp .env.example .env

# 3. 编辑配置（填入 API Key）
vim .env

# 4. 准备输入数据
cp examples/input_example.json output/report_data_2026_01.json

# 5. 生成报告
python etl_pipeline.py --template pm_deep
```

---

## 📊 文件大小统计

```
核心程序:
  etl_pipeline.py    ~150 KB
  spider.py          ~20 KB
  config.py          ~2 KB

文档:
  README.md          ~10 KB
  SKILL_SPEC.md      ~25 KB
  ONE_COMMAND_RUN.md ~8 KB

配置与脚本:
  requirements.txt   ~1 KB
  .env.example       ~2 KB
  scripts/*.py       ~5 KB

示例:
  examples/*         ~7 KB

总计: ~230 KB (不含输出文件)
```

---

## 🔄 版本控制建议

### 应该提交到 Git 的文件

- ✅ 所有源代码 (`.py`)
- ✅ 所有文档 (`.md`)
- ✅ 配置示例 (`.env.example`, `requirements.txt`)
- ✅ 脚本 (`scripts/*`)
- ✅ 示例 (`examples/*`)

### 不应该提交的文件

- ❌ `.env` (包含敏感信息)
- ❌ `output/*` (生成的文件)
- ❌ `__pycache__/` (Python 缓存)
- ❌ `*.log` (日志文件)
- ❌ `.venv/` (虚拟环境)

---

## 📝 打包发布流程

### 方式 1: 手动打包

```bash
# 1. 复制核心文件
mkdir -p peripheral-monitor-skill-v1.0.0
cp README.md SKILL_SPEC.md ONE_COMMAND_RUN.md peripheral-monitor-skill-v1.0.0/
cp requirements.txt .env.example .gitignore peripheral-monitor-skill-v1.0.0/
cp config.py etl_pipeline.py spider.py peripheral-monitor-skill-v1.0.0/
cp -r scripts examples peripheral-monitor-skill-v1.0.0/
mkdir peripheral-monitor-skill-v1.0.0/output

# 2. 打包
zip -r peripheral-monitor-skill-v1.0.0.zip peripheral-monitor-skill-v1.0.0/
tar -czf peripheral-monitor-skill-v1.0.0.tar.gz peripheral-monitor-skill-v1.0.0/

# 3. 发布到 GitHub/GitLab
git init
git add .
git commit -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags
```

### 方式 2: 使用 setuptools

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="peripheral-monitor-skill",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'requests>=2.31.0',
        'beautifulsoup4>=4.12.0',
        'lxml>=5.0.0',
        'pandas>=2.1.0',
        'openpyxl>=3.1.0',
    ],
    entry_points={
        'console_scripts': [
            'peripheral-monitor=etl_pipeline:main',
        ],
    },
)
```

```bash
# 构建
python setup.py sdist bdist_wheel

# 上传到 PyPI
twine upload dist/*
```

---

## 🔐 安全建议

### 发布前检查清单

- [ ] 移除所有敏感信息（API Key、密码等）
- [ ] 确认 `.env` 不在提交列表中
- [ ] 确认 `output/` 目录在 `.gitignore` 中
- [ ] 检查代码中是否有硬编码的路径或密钥
- [ ] 添加许可证文件 (LICENSE)

### 运行时安全

- [ ] API Key 通过环境变量传递
- [ ] 不在日志中打印敏感信息
- [ ] 限制输出文件权限
- [ ] 使用 HTTPS 访问 API

---

## 📞 支持与反馈

- **问题反馈**: GitHub Issues
- **功能建议**: GitHub Discussions
- **安全问题**: security@example.com

---

## 📄 许可证

MIT License - 详见 LICENSE 文件
