# TODO

> 约定：消息里 -xxx- 包裹的内容 = 待办/指令，完成后删除对应行。

## 方向

- 只做两件事：**快速记人、快速查人**。
- 提醒 / 待办已按产品决策移除（2026-10-22），不再开发。
- LLM 抽取暂停：代码与测试保留，界面不接入。

## 迁移策略（开发期）

> 决策（2026-10-24）：**开放开发期暂不做增量迁移**。
> 当前使用人数为 0，schema 变更时直接重建库是可接受的；发布前再实现按版本逐步迁移。
> 发布门槛：第一个公开版本前必须完成迁移框架 + 旧快照恢复测试；一旦有外部测试者/用户，立即按“有用户”处理。

## 待办

- [ ] settings 表持久化（sqlite 仓库，随 infra 一起）
- [x] 快照列表与一键恢复（恢复前自动备份当前数据；版本不一致拒绝）
- [ ] 消歧打分：候选生成 + score 公式 + 阈值（§3.3）；当前只有「别名 / 姓名精确匹配」
- [ ] 全局热键（记人呼出）+ 托盘常驻
- [ ] 导出 / 导入的 GUI 按钮（现在只有 CLI）
- [ ] 添加方式：多行批量粘贴（预览 / 重名候选 / 导入不算联系，P0）
- [ ] 添加方式：CSV 导入（列映射 / 编码 / 逐行报告，P1）
- [ ] 添加方式：vCard 导入（手机通讯录，P1）
- [ ] 添加方式：名片 OCR（P3，暂不做）
- [x] 关系图：person_relation + 详情页「认识的人」/「通过谁认识」+ 主界面「通过谁认识」+ 关系对话框内联新建（v6；只记 introduced，不自动建认识边）
- [ ] 关系图：二度查询与引荐路径（v6 已就绪，待做）
- [ ] 关系标签（朋友/同事/客户/同学）与待补全视图（v6 已就绪，待做）
- [ ] 增量迁移（**发布前**；开发期允许重置库，见「迁移策略」）
- [ ] 明天做**（示例占位，待明确）

## 代码重复治理（2026-10-25 体检）

- [x] **P0 `last_contact_at` 单一实现**：新增 `domain/dates.latest_contact`，record 合并与 edit 重算共用；修掉「补录更早的历史记录会让最近联系回退、列表排序错乱」
- [x] **P0 字段集合单一来源**：删掉 `field` 注册表（schema v7，v6→v7 非破坏迁移），key 校验统一走 `domain/fields.FIELD_KEYS`；导入含未注册字段直接拒绝（修掉「编辑保存时静默丢自定义字段」）
- [x] **P0 姓名校验单一实现**：`domain/text.require_name` + `NAME_MAX_LENGTH`，record / edit 共用（`model_copy` 不校验的老坑一并堵上）；空白原话在入口拒绝；CLI / GUI 入口统一捕获 `(RekindleError, ValueError)`
- [x] **P0 日期输入统一**：GUI 主表单改用 `parse_date_input`，支持 今天/昨天/前天/上周（原来只认 ISO）
- [x] **P0 可选文本清洗统一**：新增 `domain/text.clean_optional`，record / edit / GUI / 关系对话框共用
- [x] **P1 联系方式规范化统一**：`record` 与 `edit` 共用 `domain/fields.normalize_fields`（去空白/去空值/去重）
- [x] **P1 日期规则统一**：新增 `domain/dates.at_midnight` / `resolve_day`，record.manual / record.confirm / edit.save_interaction 共用
- [x] **P1 写前快照策略统一**：新增 `interfaces/snapshot_guard.SnapshotGuard`，编辑窗口与关系对话框都改成「一次会话一次」
- [x] **P1 修 `snapshot_keep` 冲突**：统一到 `domain/models.DEFAULT_SNAPSHOT_KEEP = 10`，infra 与 Settings 共用
- [ ] **P2 `Settings.snapshot_dir` 与实现不一致**：Settings 写 `user_data/snapshots`，实际是「数据库同目录 / snapshots」，且未接入
- [ ] **P1 常量集中**：`limit=50`（4 处）、`summary[:500]`（4 处）、`raw_text 2000`
- [ ] **P1 `record.manual` / `record.confirm` 的提交块 20 行重复**：抽 `_commit`；顺带把「追加去重」合并到 `fields.normalize_values`
- [ ] **P2 API DTO 复制 domain 模型**：`PersonOut` / `ConfirmOut` + 3 个 `_x_out` 逐字段搬运（64 行），用 `from_attributes` + `field_serializer`
- [ ] **P2 人员展示格式统一**：`person_label`（gui / relation_dialog / editor 三种拼法）
- [ ] **P2 UI 错误弹窗抽 helper**：4 个文件 20 处 `try/except + messagebox.showerror`
- [ ] **P2 接口层三份重复**：介绍人下拉框（gui / editor）、Treeview+滚动条（6 处）、「日期解析+报错」（3 处）

## 已完成

- [x] v0.3 收窄：移除提醒与待办（模型 / 表 / 命令 / GUI / 测试），旧库自动重建
- [x] 快捷查找：GUI 搜索框（Ctrl+F 定位、Esc 清空）+ 最近联系优先 + 别名可搜
- [x] v0.2 离线原型：sqlite 仓储（迁移 + 显式事务 + 唯一约束）
- [x] 记录用例：remember（草稿）→ confirm（字段覆盖 / 单事务 / 幂等）
- [x] CLI：remember / confirm / list / show / alias / discard / export / import
- [x] GUI（Tkinter 最小版）
- [x] 必测 1（未确认不入库）、必测 2（重复确认只一条）、必测 6（导出导入往返）
- [x] 离线姓名识别：高频姓氏 + 已导入人脉的姓氏做校验（客户/同事不再被当人名）
- [x] 姓名识别优先级：已有人脉姓名 > 常见大姓 > 常见小姓；无提示词时全文扫描
- [x] 公司改为「日期 → 公司」历史；同一人换公司不覆盖旧记录
- [x] 初始属性字段：微信 / QQ / 邮箱 / 电话（field 注册表 + person_field 键值表，可搜索）
- [x] 不写句子直接入库：姓名必填、日期默认入库当天、自动生成「用户输入了：…」
- [x] 联系方式改为数组：同一字段可追加多个值，去重且不覆盖旧值
- [x] 应用内编辑：资料/公司历史/联系方式/交往记录；归档；编辑前自动快照（保留 10 份）
- [x] 测试 135 个全绿；ruff 与 mypy --strict 通过
- [x] T1 给 .clinerules 追加「字段可自定义」与「用户消息约定」
- [x] T4（部分）DeepSeek key 实测可用（HTTP 200）
- [x] T2 字段自定义设计方案（§9）
- [x] T3 规则抽取：extract_rule.py + 20 测试（离线）
- [x] AI 权限关系原则加入 .clinerules；权限与存档设计（§11）
- [x] 权限设置领域模型 + 代码层开关（Settings/Permission/require）
- [x] T4 LLM 抽取：extract_llm + HttpLlmClient + 6 个单测；DeepSeek 真机验证（HTTP 200），但**未接入界面**
