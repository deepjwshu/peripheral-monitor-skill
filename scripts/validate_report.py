#!/usr/bin/env python3
"""
报告校验脚本

校验 HTML 报告是否包含所有必需的关键组件。

使用方式:
    python scripts/validate_report.py <报告路径>

示例:
    python scripts/validate_report.py output/monthly_report_2026_01.html
"""

import sys
import argparse
from pathlib import Path


def validate_html_report(html_path: str) -> bool:
    """校验HTML报告是否包含所有必需的关键组件

    Args:
        html_path: HTML报告文件路径

    Returns:
        bool: 校验是否通过

    Raises:
        SystemExit: 校验失败时退出程序
    """
    required_components = {
        'nav-bar': '导航栏（包含快速跳转和搜索框）',
        'searchInput': '搜索输入框',
        'product-overview': '产品概览模块（左栏）',
        'product-specs': '硬核参数模块（中栏）',
        'product-analysis': 'PM深度洞察模块（右栏）',
        'PM 深度洞察': 'PM深度洞察标题'
    }

    # 读取 HTML 文件
    html_file = Path(html_path)
    if not html_file.exists():
        print(f"[FAIL] 文件不存在: {html_path}")
        return False

    html_content = html_file.read_text(encoding='utf-8')

    # 检查每个必需组件
    missing_components = []
    for component, description in required_components.items():
        if component not in html_content:
            missing_components.append(f"  ✗ {component}: {description}")

    # 输出结果
    if missing_components:
        print(f"[FAIL] HTML报告校验失败！缺少以下关键组件:")
        for component in missing_components:
            print(component)
        return False
    else:
        print(f"[OK] 所有关键组件校验通过:")
        for component, description in required_components.items():
            print(f"  ✓ {component}: {description}")
        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='校验 HTML 报告是否包含所有必需的关键组件'
    )
    parser.add_argument(
        'report_path',
        type=str,
        help='HTML 报告文件路径'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='严格模式：校验失败时退出码为 1'
    )

    args = parser.parse_args()

    # 执行校验
    success = validate_html_report(args.report_path)

    # 根据严格模式决定退出码
    if args.strict and not success:
        sys.exit(1)

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
