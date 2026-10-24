# Changelog

## [0.1.0] - 2026-10-25

首个公开版本。

### 功能

- 一句话记录：离线规则抽取姓名 / 公司 / 职位 / 相对日期，确认后才入库
- 公司与联系方式按时间累积，不覆盖旧值；支持别名搜索
- 关系：六档认识关系 + 介绍关系（不自动补认识边）
- 编辑、归档、快照与一键恢复、JSON 导入导出
- FastAPI 接口层：6 个接口，与 CLI / GUI 共用同一套用例
- Windows 单文件 exe（PyInstaller），内置图标与版本信息

### 工程

- 四层架构（domain / app / infra / interfaces）+ Protocol 端口
- 144 个测试；核心层覆盖率 94%
- GitHub Actions：ruff + mypy --strict + pytest + 核心层 90% 覆盖率门禁

### 已知限制

- LLM 抽取未接入（代码与测试保留，无入口，运行时零出站）
- 设置不持久化；消歧仅「姓名 / 别名精确匹配」；无全局热键与托盘
- 开发期 schema 变更会重建数据库，升级前请先 `export` 或 `snapshot`
