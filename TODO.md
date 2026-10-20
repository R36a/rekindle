# TODO

> 约定：消息里 -xxx- 包裹的内容 = 待办/指令，完成后删除对应行。

## 待办

- [ ] T2 字段可自定义的设计方案：动态 schema、键值存储、动态表单；牵动 models.py / 文档 / 抽取管线
- [ ] T3 规则抽取：extract_rule.py + preview.py + 20 条测试（离线，先按默认字段做）
- [ ] T4 LLM 抽取实现：httpx + UTF-8（不经 shell 传中文）；模型 deepseek-flash（deepseek-chat 已停用）；key 已实测可用
- [ ] T5 M2~M4 里程碑：LLM 抽取/消歧/评测、GUI、提醒（见 docs/开发文档.md）
- [ ] 明天做**（示例占位，待明确）

## 已完成

- [x] T1 给 .clinerules 追加「字段可自定义」与「用户消息约定」
- [x] T4（部分）DeepSeek key 实测可用（HTTP 200）
