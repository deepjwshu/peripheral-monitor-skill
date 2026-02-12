# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-12

### Added
- Initial release of peripheral-monitor-skill
- Data spider for in外设 and 外设天下 platforms
- ETL pipeline with data preprocessing and deduplication
- LLM-based product info extraction with DeepSeek V3
- Product merging with similarity-based deduplication
- HTML report generator with PM deep analysis template
- Interactive charts (Chart.js) for sensor and price distribution
- Automatic report validation
- Claude Code skill integration with `/research` slash command
- MCP search service support for parameter completion
- Comprehensive documentation (README, SKILL_SPEC, INSTALL_GUIDE, etc.)

### Features
- One-command execution: `python etl_pipeline.py --month YYYY-MM --fetch --template pm_deep`
- Natural language trigger through Claude Code
- Three-column report layout: Product Overview | Specs | PM Insights
- Responsive dark-themed HTML report
- Mobile-friendly design
- Search and navigation functionality
- Automatic data quality warnings
- Failed item logging

### Technical Specifications
- Python 3.9-3.12 compatible
- Top 15 Schema for mice and keyboards
- Concurrent LLM processing (max_workers=10)
- HTML validation with required component checks

## [Unreleased]

### Planned
- Enhanced data source support
- Custom report templates
- API provider extensibility
- Performance optimizations for large datasets

---

[0.1.0]: https://github.com/your-org/peripheral-monitor-skill/releases/tag/v0.1.0
[Unreleased]: https://github.com/your-org/peripheral-monitor-skill/compare/v0.1.0...HEAD
