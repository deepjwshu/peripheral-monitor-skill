# MCP 搜索服务配置指南

> 本指南适用于**公司内网环境**，配置二次参数补全的 MCP 搜索能力

---

## 快速开始

### 1. 获取 MCP 服务信息

联系管理员获取以下信息：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| 服务地址 | MCP 服务部署地址 | `http://192.168.0.250:7891` |
| 认证 Token | API 访问令牌 | `Bearer xxxxxxxx` |
| 搜索服务端点 | 搜索服务路径 | `/mcp_web_search` |
| 抓取服务端点 | 网页抓取路径 | `/mcp_web_reader` |

### 2. 配置 `.env` 文件

复制 `.env.example` 并修改：

```bash
# 启用 MCP 搜索服务
MCP_SEARCH_ENABLED=true

# MCP 服务地址（公司内部）
MCP_BASE_URL=http://192.168.0.250:7891

# MCP 认证 Token（从管理员处获取）
MCP_TOKEN=your_actual_token_here

# 可选：自定义端点（通常不需要修改）
MCP_SEARCH_ENDPOINT=http://192.168.0.250:7891/mcp_web_search
MCP_READER_ENDPOINT=http://192.168.0.250:7891/mcp_web_reader
```

### 3. 测试配置

运行测试脚本验证配置：

```bash
python scripts/test_mcp.py
```

预期输出：

```
==================================================
MCP 服务测试脚本
==================================================

[1] 配置检查
  MCP 搜索启用: True
  MCP 服务地址: http://192.168.0.250:7891
  MCP Token: 已配置
  MCP 可用性: ✅ 可用

[2] 搜索功能测试
  测试查询: 罗技G Pro X Superlight 2 传感器
  ✅ 搜索成功!
  ...
```

---

## 配置项说明

### MCP_SEARCH_ENABLED

- **作用**：控制是否启用 MCP 搜索功能
- **可选值**：
  - `true` - 启用 MCP 搜索（用于二次参数补全）
  - `false` - 禁用 MCP 搜索（默认，仅使用本地数据）
- **建议**：公司内网环境设置为 `true`

### MCP_BASE_URL

- **作用**：MCP 服务器的基础 URL
- **格式**：`http://IP:PORT` 或 `https://域名`
- **示例**：
  - `http://192.168.0.250:7891`（公司内部）
  - `http://localhost:7891`（本地测试）

### MCP_TOKEN

- **作用**：MCP 服务的认证令牌
- **获取方式**：联系管理员
- **格式**：通常是 `Bearer xxxxxxxx` 格式，只需填入 `xxxxxxxx` 部分

### MCP_SEARCH_ENDPOINT / MCP_READER_ENDPOINT

- **作用**：指定搜索和网页抓取的服务端点
- **默认值**：
  - `MCP_BASE_URL/mcp_web_search`
  - `MCP_BASE_URL/mcp_web_reader`
- **通常情况**：无需修改，使用默认值即可

### MCP_TIMEOUT

- **作用**：MCP 请求超时时间（秒）
- **默认值**：`30`
- **建议**：网络较慢时可增加到 `60`

---

## 工作原理

### MCP 搜索在流程中的位置

```
爬虫采集
   ↓
数据清洗
   ↓
LLM PM 深度分析
   ↓
二次参数补全 ← MCP 搜索在这里
   ↓
报告生成
```

### MCP 搜索能做什么？

当文章内容中缺少关键参数时，MCP 搜索会：

1. **构建搜索查询**：如 `"罗技G304 传感器 PAW3395"`
2. **调用 MCP 搜索服务**：从公司内部搜索引擎获取结果
3. **LLM 提取参数**：从搜索结果中提取缺失的参数
4. **补全数据**：回填到产品规格中

### 示例

**原始文章内容**：
```
罗技发布了新款 G Pro X Superlight 2 游戏鼠标，
采用轻量化设计，重量仅60g。
```

**检测到缺失参数**：
- ❌ `sensor_solution`（传感器）
- ❌ `polling_rate`（回报率）
- ❌ `product_pricing`（价格）

**MCP 搜索补全**：
- 搜索：`"罗技G Pro X Superlight 2 传感器 Hero 2"`
- 提取：`Hero 2 传感器（32000 DPI）`
- 补全：✅ `sensor_solution: "Hero 2 传感器（32000 DPI）"`

---

## 故障排查

### 测试失败：MCP 服务不可用

**症状**：
```
[1] 配置检查
  MCP 可用性: ❌ 不可用
```

**解决步骤**：

1. 检查 `.env` 文件是否存在
   ```bash
   ls -la .env
   ```

2. 检查 `MCP_TOKEN` 是否配置
   ```bash
   grep MCP_TOKEN .env
   ```

3. 测试 MCP 服务连通性
   ```bash
   curl http://192.168.0.250:7891
   ```

4. 检查 Token 是否有效
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        http://192.168.0.250:7891/mcp_web_search
   ```

### 搜索失败：返回空结果

**症状**：
```
[2] 搜索功能测试
  ❌ 搜索失败!
```

**可能原因**：

1. **Token 无效或过期**
   - 联系管理员获取新 Token
   - 更新 `.env` 文件

2. **服务地址错误**
   - 确认 `MCP_BASE_URL` 是否正确
   - 检查端口号是否正确

3. **网络问题**
   - 确认能访问公司内网
   - 检查防火墙设置

### 报告生成时未使用 MCP 搜索

**症状**：报告参数仍然缺失

**检查点**：

1. 确认 `MCP_SEARCH_ENABLED=true`
   ```bash
   grep MCP_SEARCH_ENABLED .env
   ```

2. 查看 Pipeline 输出日志
   ```
   [步骤 2.1/5] 初始化参数补全器V2（Top 15 Schema）...
   [OK] 参数补全器V2已初始化（Top 15 Schema，MCP搜索: 启用）
   ```

3. 如果显示 `MCP搜索: 禁用`，检查配置

---

## 安全建议

### 1. 保护敏感信息

- ❌ **不要**将 `.env` 文件提交到 Git
- ✅ **应该**将 `.env` 添加到 `.gitignore`
- ✅ **应该**只分享 `.env.example` 模板

### 2. Token 管理

- 定期更新 MCP Token
- 不同环境使用不同 Token（开发/测试/生产）
- Token 泄露后立即撤销并重新申请

### 3. 网络隔离

- MCP 服务仅在**公司内网**使用
- 不要将内部服务地址暴露到公网
- 使用 VPN 连接公司网络后使用

---

## 高级配置

### 自定义 MCP 服务端点

如果你们的 MCP 服务部署路径不同，可以自定义：

```bash
# 非标准路径
MCP_SEARCH_ENDPOINT=http://192.168.0.250:7891/custom/search
MCP_READER_ENDPOINT=http://192.168.0.250:7891/custom/reader
```

### 调整超时时间

网络较慢时增加超时：

```bash
MCP_TIMEOUT=60
```

### 禁用 MCP 搜索

在公司外网使用或测试时，禁用 MCP：

```bash
MCP_SEARCH_ENABLED=false
```

此时二次补全仅使用本地数据，不会调用外部服务。

---

## 联系支持

如果遇到问题：

1. **查看日志**：`etl_pipeline.log`
2. **运行测试**：`python scripts/test_mcp.py`
3. **联系管理员**：获取最新的服务地址和 Token
4. **查看文档**：[README.md](README.md)

---

## 附录：MCP 服务端点参考

### web-search-prime

**方法**：`search/webSearchPrime`

**参数**：
- `search_query`: 搜索关键词
- `content_size`: `low` | `medium` | `high`
- `search_recency_filter`: `oneDay` | `oneWeek` | `oneMonth` | `noLimit`

**返回**：
```json
{
  "results": [
    {
      "title": "文章标题",
      "url": "https://...",
      "content": "文章摘要内容..."
    }
  ]
}
```

### web-reader

**方法**：`read`

**参数**：
- `url`: 目标网页 URL

**返回**：
```json
{
  "content": "网页纯文本内容"
}
```
