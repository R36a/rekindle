# TODO

> 约定：消息里 -xxx- 包裹的内容 = 待办/指令，完成后删除对应行。

## 待办

- [ ] T4 LLM 抽取实现：httpx + UTF-8（不经 shell 传中文）；模型 deepseek-flash；自定义字段 + 待办（多人/重复）交给 LLM
- [ ] T5 M2~M4 里程碑：LLM 抽取/消歧/评测、GUI、提醒（见 docs/开发文档.md）
- [ ] 明天做**（示例占位，待明确）

## 已完成

- [x] T1 给 .clinerules 追加「字段可自定义」与「用户消息约定」
- [x] T4（部分）DeepSeek key 实测可用（HTTP 200）
- [x] T2 字段自定义设计方案（docs/设计细节.md §9；AI 只填值不增删字段）
- [x] T2 补充：promise → 待办实体（多人、下一次时间、是否重复）设计（§10）
- [x] T3 规则抽取：extract_rule.py + preview.py + 20 条测试（离线，含单条待办；32 测试全绿）
