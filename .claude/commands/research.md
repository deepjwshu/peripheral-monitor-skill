---
description: 调研指定月份的键鼠新品并生成 PM 深度分析报告
---

请为月份 `$ARGUMENTS` 执行外设新品调研报告生成。

月份格式支持：2026-01、2026/01、2026.01、2026年1月、今年1月

**月份规范化规则**：
1. 提取年份和月份数字（支持中文、英文、数字）
2. 月份补零（如 `1` → `01`）
3. 年份默认为当前年份（如果未指定）
4. 最终格式化为 `YYYY-MM`

**执行步骤**：

1. 将 `$ARGUMENTS` 规范化为 `YYYY-MM` 格式
2. 执行以下命令（替换 `YYYY-MM` 为规范化后的月份）：
```bash
python etl_pipeline.py --month YYYY-MM --fetch --template pm_deep
python scripts/validate_report.py --file output/monthly_report_YYYY_MM.html
```

3. 成功后输出报告路径和数据概况：
```
✅ 外设新品调研报告已生成！

📊 数据概况：
  - 抓取记录数：{N} 条
  - 去重后产品数：{M} 款

📄 报告路径：output/monthly_report_YYYY_MM.html
```
