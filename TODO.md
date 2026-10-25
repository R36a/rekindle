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

## 幽灵代码清理（2026-10-25，schema v8）

- [x] **删 `models.Alias`**：全仓无构造（`add_alias` 直接写 SQL），死模型；`alias` 表与搜索不受影响
- [x] **删 `person.pinyin` / `person.initials`**：从建库起从未写入，拼音搜索未实现；`Person` 模型、DDL、读写 SQL 一并去掉（v7→v8 用 `ALTER TABLE … DROP COLUMN`）
- [x] **迁移改成逐版本步骤**：`_MIGRATION_STEPS = {6: v6→v7, 7: v7→v8}`，`_upgrade()` 顺序执行；更老的开发库仍走重建（TODO「迁移策略」）
- [x] **旧备份兼容**：`_RETIRED_COLUMNS` 让导入忽略已删除的列（v3 备份里带 pinyin/initials 也能导），不再把整份备份判成「未知列」
- [x] **旧快照可用**：`restore_snapshot` 对旧版本快照先在临时副本上升级再恢复（原文件不动），只有「比程序新」或「太旧无迁移路径」才拒绝
- [ ] **保留 `extract_llm` + `llm_http`**（用户决定不删）：仍无入口，建议后续加一条 `httpx.MockTransport` 契约测试防腐烂

## 字段注册表（2026-10-25 彻底重构）

- [x] **`domain/person_schema.py` = 唯一字段定义**：`PersonField`（key/标签/存储方式/约束/可搜/摘要顺序/CLI/表单宽度），`PERSON_FIELDS` 一项声明
- [x] **schema 由注册表生成**：新增 `infra/schema_sql.py`，`person` 表 DDL 不再手写（迁移脚本仍是显式历史）；有测试比对 `PRAGMA table_info` 与注册表逐列一致
- [x] **搜索 SQL 由注册表生成**：`searchable=True` 的字段自动进 WHERE（列 / 公司历史 / 联系方式三种匹配方式），改字段不必记得改 SQL
- [x] **CLI 参数由注册表生成**：`--name/--company/--role/--wechat…` 全部派生，`_person_values()` 把参数还原成 `record.*` 入参
- [x] **摘要文本由注册表生成**：`_manual_summary` 按 `SUMMARY_FIELDS` 的顺序拼，不再手写「姓名→公司→职位→微信…」
- [x] **表单由注册表生成**：新增 `interfaces/forms.build_grid`，主界面/编辑窗/关系对话框三处共用；标签宽度也只有一个来源
- [x] **字段名统一**：`record.manual/confirm` 的参数由 `name` 改为 `display_name`（与 `Person` / 注册表一致），对外仍是 CLI `--name` 与 HTTP `name`
- [x] **删 `FIELD_LABELS`**：无消费者后，`FIELD_KEYS` 直接从 `DEFAULT_FIELDS` 派生

## 尚未做（有意保留）

- [x] **API 出参**：`_Out` 基类 + `ConfigDict(from_attributes=True)` + `@field_serializer`（date 键 → ISO），删掉 `_person_out` / `_interaction_out` / `_confirm_out`；端点直接返回领域对象（`RecordedCapture` / `ConfirmResult` / `PersonDetail`）
- [ ] **API 入参**：`ManualIn/ConfirmIn` 仍显式声明——对外契约（`name` 别名、必填规则与内部不同），且 `mypy --strict` 需要静态类型，`create_model` 会让类型检查失效
- [ ] **迁移脚本**：v6→v7 这类历史步骤不能从当前注册表重算，保持显式

## 代码重复治理（2026-10-25 体检）

- [x] **P0 `last_contact_at` 单一实现**：新增 `domain/dates.latest_contact`，record 合并与 edit 重算共用；修掉「补录更早的历史记录会让最近联系回退、列表排序错乱」
- [x] **P0 字段集合单一来源**：删掉 `field` 注册表（schema v7，v6→v7 非破坏迁移），key 校验统一走 `domain/fields.FIELD_KEYS`；导入含未注册字段直接拒绝（修掉「编辑保存时静默丢自定义字段」）
- [x] **P0 姓名校验单一实现**：`domain/text.require_name` + `NAME_MAX_LENGTH`，record / edit 共用（`model_copy` 不校验的老坑一并堵上）；空白原话在入口拒绝；CLI / GUI 入口统一捕获 `(RekindleError, ValueError)`
- [x] **P0 日期输入统一**：GUI 主表单改用 `parse_date_input`，支持 今天/昨天/前天/上周（原来只认 ISO）
- [x] **P0 可选文本清洗统一**：新增 `domain/text.clean_optional`，record / edit / GUI / 关系对话框共用
- [x] **P1 联系方式规范化统一**：`record` 与 `edit` 共用 `domain/fields.normalize_fields`（去空白/去空值/去重）
- [x] **P1 日期规则统一**：新增 `domain/dates.at_midnight` / `resolve_day`，record.manual / record.confirm / edit.save_interaction 共用
- [x] **P1 写前快照策略统一**：新增 `interfaces/snapshot_guard.SnapshotGuard`，编辑窗口与关系对话框都改成「一次会话一次」
- [x] **P1 修 `snapshot_keep` 冲突**：统一到 `DEFAULT_SNAPSHOT_KEEP = 10`（P1 已随「删 Settings」移到唯一消费者 `infra/snapshot.py`）
- [x] **P1 常量集中**：新增 `domain/limits.py`（`DEFAULT_LIST_LIMIT` / `MAX_LIST_LIMIT` / `RAW_TEXT_MAX_LENGTH` / `SUMMARY_MAX_LENGTH`），模型、仓储、API、界面共用
- [x] **P1 `record._commit`**：manual / confirm 的「建人 + 写记录 + 完结草稿」合成一份实现；「追加去重」抽成 `domain/fields.merge_fields`（编辑窗「添加」也用它）
- [x] **P1 端口收敛**：5 个 Protocol → 1 个 `Repo`（唯一实现是 SqliteRepo，测试用真实临时库；以前 `get_person` 签名抄了 4 份）
- [x] **P1 删未接线的权限模型**：`Settings` / `Permission` / `PermissionDenied` 与 6 个测试（无任何业务调用方，README 也写着「没有开关」）
- [x] **P1 接口层三份重复**：新增 `interfaces/ui.py`——`make_table`（6 处 Treeview 收敛，顺带补齐 2 张表原本缺失的滚动条）、`read_date`（3 处日期解析，提示词由 `RELATIVE_DAYS` 派生）、`fill_person_choices`（2 处介绍人下拉，「姓名 (#id)」格式只此一处）
- [x] **P1 CLI 字段参数生成**：`--wechat/--qq/--email/--phone` 由 `DEFAULT_FIELDS` 生成，`_contact_fields` 不再写死 4 个 key
- [x] **P1 仓储单人/批量查询统一**：删 `_companies_of` / `_fields_of`，`_load_person` 复用批量版
- [x] **P1 `snapshot._copy_database`**：两处「开两个连接 + backup + close」合并
- [x] **P1 删 `RELATIVE_ORDER`**：`RELATIVE_DAYS` 的 dict 顺序即遍历顺序（这些词两两不互为子串）
- [x] **P2 人员展示格式统一**：并入 `ui.fill_person_choices`
- [x] **P2 UI 错误弹窗**：评估后**不抽**包装——`messagebox.showerror` 本身就是唯一实现，各站点标题与后续动作不同；抽一层只是别名，不消除逻辑
- [x] **P2 API DTO 复制 domain 模型**：出参改为 `from_attributes` 投影 + `field_serializer`，删掉 3 个逐字段搬运函数（api.py 257 → 233 行，行为不变：JSON 形状与之前逐字节一致）
- [x] **P2 关系类型 10 个名字 → 1 张表**：`RELATIONS: dict[RelationKind, RelationSpec]` 一处声明；删掉 `RELATION_KINDS` 与 `RELATION_LABELS`/`RELATION_RANK` 两个平行字典（原来是「推导完再按下标补一行」），`RelationSpec` 不再重复存 kind；新增两条守卫测试（每个 kind 必须登记、DDL 的 CHECK 必须覆盖全部 kind）

## 已完成

- [x] 关系对话框「新建联系人 + 记介绍 + 记关系」改为单事务：新增可嵌套的 `Repo.atomic()`，三步失败任一步都整体回滚（以前会留下「人建了、关系没建」）；含两条测试（`atomic` 嵌套回滚、对话框失败不留半条数据）
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
