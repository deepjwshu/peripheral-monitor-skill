---
description: 调研指定月份的键鼠新品并生成 PM 深度分析报告
---

请为月份 `$ARGUMENTS` 执行外设新品调研报告生成。

月份格式支持：2026-01、2026/01、2026.01、2026年1月

执行命令：
```bash
python etl_pipeline.py --month YYYY-MM --fetch --template pm_deep
python scripts/validate_report.py --file output/monthly_report_YYYY_MM.html
```

成功后输出报告路径和数据概况。
