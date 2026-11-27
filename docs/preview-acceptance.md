# Nexora v0.5.1-preview 验收

只升级 Nexora，保留原四套 custom_sentences/zh-CN 与 intent_scripts 的8个 YAML、现有配置、CN IM Hub、AI Hub、SGCC Add-on。bindings.yaml 可选。备份后通过 HACS 安装已明确发布的预览版并重启 Core。异常时恢复 v0.5.0-preview 完整目录并重启，不删除配置条目或 .storage。

## 独立验收

- v051_probe.js：只读专项，复核自然语言、场景整合、统一格式、上下文及新增口语。查询实际值可能变化；日志必须保留数据时效、状态限制及未知状态说明。不发送控制或混合控制反例。
- full_probe.js：四套443项注册能力的全量菜单只读遍历；420可见、23隐藏是此前实机参考而非通用门槛。部分数据有效单列 partial_data，不等同于执行错误；review 表示需人工核实。
- HA 集成诊断：发送 help 后，从 Nexora 集成下载诊断；提供隐藏/暂时不可用的原因和模式元数据。无实体 ID、对话原文或私有模板。不主动调用 Intent Script。若目标映射尚未初始化或待刷新，先通过正常菜单更新再核实。
- source_probe.js：可选既有家庭源数据诊断；SGCC 重启恢复不属于此次修复。
- 微信：独立验收口语、场景和连续追问；其他集成直达原生 Intent 时不会同步 Nexora 上下文。

专项先通过再跑全量；源数据不足不宣称数值验收成功。HACS Topics / Brands 仍为独立收录检查，未禁用校验。测试脚本独立 ZIP，不作为 Release 资产，不复制入运行目录。v0.5.1 实机和微信验收需用户执行。
