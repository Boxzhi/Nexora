# Nexora v0.5.2-preview 验收

仅升级 Nexora，保留原四套 custom_sentences/zh-CN 与 intent_scripts 的8个 YAML、现有配置、CN IM Hub、AI Hub、SGCC Add-on。bindings.yaml 可选。备份后通过 HACS 安装已发布预览版并重启 Core。异常时恢复 v0.5.1-preview 完整目录并重启，不删除配置条目或 .storage。

## 验收顺序

- v052_probe.js：26轮独立只读专项；重点为综合余额、欠费、充值、账户范围切换、时间更新、单账户追问、年度统计与正式账单、全屋环境、设备状态、独立会话和退出。数据随真实状态变化，不按固定旧数值判断。保留数据时效与不可用说明；不发送设备控制或混合控制反例。
- 微信：在同一会话逐条发送“我家水电气余额还有多少”“有没有欠费的”“需要充值吗”“所有账户呢”“余额呢”。核对实际账户及指标。若 HA 专项通过但微信追问失败，核实实际路由与 conversation_id；外部原生 Intent 直达不共享 Nexora 上下文。
- full_probe.js：四套443项注册能力的当前可见菜单只读遍历；420可见、23隐藏是此前实机参考而非通用门槛。partial_data 与 data_gap 不是执行错误，也不等于完整数据验收。
- HA 集成诊断：发送 help 后可下载 Nexora 诊断，检查能力及聚合路由统计，不触发新查询。
- source_probe.js：可选源状态诊断；SGCC 重启恢复不属于本版修复。

脚本独立交付，不作为 Release 附件，不复制入运行目录。HACS Topics / Brands 仍为独立收录检查，未绕过。v0.5.2 实机及微信验收需用户执行。
