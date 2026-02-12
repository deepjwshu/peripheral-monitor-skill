# 给同事的 MCP 配置快速指南

## 公司内网使用 MCP 搜索服务

### 1. 获取 MCP 服务信息

联系管理员获取：
- 服务地址：`http://192.168.0.250:7891`
- 认证 Token：`Bearer xxxxxxxx`

### 2. 修改 `.env` 文件

在项目根目录创建/编辑 `.env` 文件：

```bash
# 启用 MCP 搜索
MCP_SEARCH_ENABLED=true
MCP_BASE_URL=http://192.168.0.250:7891
MCP_TOKEN=你的Token（不含Bearer前缀）

# LLM 配置
LLM_API_KEY=你的LLM_API_Key
LLM_API_BASE=http://192.168.0.250:7777
LLM_MODEL=xdeepseekv3
```

### 3. 测试配置

```bash
python scripts/test_mcp.py
```

### 4. 正常使用

```bash
# 生成报告
python etl_pipeline.py --month 2026-01 --fetch --template pm_deep
```

---

## 详细文档

- 完整配置说明：[MCP_CONFIG.md](MCP_CONFIG.md)
- 项目 README：[README.md](README.md)
