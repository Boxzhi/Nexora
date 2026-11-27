# Nexora v0.5.0-preview 候选验收

只升级 Nexora。保留四套原有 custom_sentences/zh-CN 与 intent_scripts YAML、现有配置、CN IM Hub、AI Hub；bindings.yaml 可选。先备份；通过 HACS 安装明确发布的预览版后重启 Core。未发布前勿把开发分支当正式版本。失败时恢复 v0.4.1-preview 完整目录并重启，不删除配置条目或 .storage。

## 独立验收包

- v050_probe.js：结构化口语、纠错、场景、多项查询、跨对象及跨模块追问、日期和会话隔离；不发送真实控制指令或普通 AI 问答。检查 pass/state_limit/data_gap/fail，不能将源数据缺失视为实测数值通过。
- full_probe.js：沿用 v0.4.1 r2 的菜单全量回归（四套能力目录未变）。443注册、420可见、23隐藏是此前家庭环境参考，非通用门槛。
- source_probe.js：可选源数据核实（原独立 r2 脚本）；无需为 Nexora 修改供应商集成。
- 微信验收：单独测试典型口语、连续追问、help/exit；若原生快路径绕过 Nexora，不保证跨集成上下文共享。

专项先通过，再执行全量回归及微信验证。对部分数据缺失逐项复核；设备关机不等于设备查询失败，也不能证明实际温度数值。诊断仅统计本地路由/耗时，不记录私有实体或对话原文。HACS Topics / Brands 是独立收录条件；不禁用校验。真实 HA 及微信验收尚未完成。脚本由独立 ZIP 交付，不新增到集成运行目录或 Release 资产。
