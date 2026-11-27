# Nexora

面向 Home Assistant 的可扩展本地意图与会话交互引擎。

当前版本：v0.2.0-preview（开发预览）。

| 模块 | 对应意图库 | 查询项目 |
| --- | --- | ---: |
| ⚡ 水电气 | Utility v1.1.0 | 136 |
| 💡 灯光 | Lights v1.1.0 | 144 |
| 🔌 家电 | Appliance v1.0.0 | 78 |
| 🏠 全屋状态 | Home v1.0.1 | 85 |
| 合计 | | 443 |

发送 help 或 帮助 打开主菜单；exit 或 退出 关闭；0、back 或 返回 返回上一级；9、next 或 下一页 翻页；prev 或 上一页 返回前页。英文不区分大小写。仅在提示中显示 help、exit 和 prev。一级分类图标由注册目录配置。

保留现有业务意图库及原生 Intent Script。不提供供应商接口，不控制设备。仅显示已注册且符合 speech-only 检查的模块；执行前严格核对 Intent 和槽位，失败不交给大模型执行。单灯实体 ID 由本地已安装句式解析，不写入公开源码。灯具不支持亮度或色温时由原意图反馈实际能力。

安装：HACS 自定义仓库（Integration），或替换 custom_components/nexora。原 Nexora 集成配置保留，重启 Core 一次后验证。自定义目录 /config/nexora/catalogs/ 支持 JSON/YAML，重载集成生效。详见 [注册协议](docs/catalog.md)。

限制：当前菜单仍可能等待 LLM 普通队列；自然语言上下文追问和快速菜单通道后续开发。仅针对 HA Core 2026.11.3，v0.2.0-preview 尚待实际 HA 验收。此前 v0.1.0-preview 已验证水电气 136 项查询链路。

[控制台初步验收脚本](scripts/probe.js)
