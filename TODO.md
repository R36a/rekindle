# TODO

> 约定：消息里 -xxx- 包裹的内容 = 待办/指令，完成后删除对应行。

## 待办

- [ ] settings 表持久化（sqlite 仓库，随 infra 一起）
- [ ] 存档系统 + 存档设置实现（§11.2/11.3）
- [ ] T5 M2~M4 里程碑：消歧、GUI、提醒（见 docs/开发文档.md）
- [ ] 明天做**（示例占位，待明确）

## 已完成

- [x] T1 给 .clinerules 追加「字段可自定义」与「用户消息约定」
- [x] T4（部分）DeepSeek key 实测可用（HTTP 200）
- [x] T2 字段自定义设计方案（§9）
- [x] T2 补充：待办实体（多人/时间/重复）设计（§10）
- [x] T3 规则抽取：extract_rule.py + preview.py + 20 测试（离线）
- [x] AI 权限关系原则加入 .clinerules；权限与存档设计（§11）
- [x] 权限设置领域模型 + 代码层开关（Settings/Permission/require）
- [x] T4 LLM 抽取：extract_llm + HttpLlmClient + 45 测试；真机验证通过
