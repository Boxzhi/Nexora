# Nexora

面向 Home Assistant 的可扩展本地意图与会话交互引擎。

当前版本：0.1.0-preview（开发预览）。保留现有业务意图库，不提供供应商接口，不控制设备。

发送 help 进入主菜单；1–8 选择，9 下一页，上一页返回前一页，0 返回上一级，退出清除菜单。支持分类名称直接跳转、查询后继续选择、10分钟独立会话及日期参数输入。

内置 Utility v1.1.0 查询目录覆盖63个业务类型与指标组合。现有 Intent Script 必须安装；若未找到 speech-only handler 对应菜单将隐藏。执行时严格识别代表句、核对所有参数及 handler 身份，失败不交给大模型执行。

安装：HACS 自定义仓库（Integration），或将 custom_components/nexora 复制到 HA 配置目录。重启 Core，添加 Nexora 集成，填写原备用代理 ID、主账户显示名称、第二账户显示名称及原意图库可识别的第二账户别名（不填则隐藏）。先在控制台验证，再切换 CN IM Hub 代理。旧技术预览可独立卸载，不迁移配置。

自定义目录放在 /config/nexora/catalogs/，支持 JSON/YAML。修改后重载集成生效。详见 docs/catalog.md。

限制：当前只接入 Utility，仍可能等待 LLM 普通队列；多轮追问、其他业务意图库后续扩展。仅针对 HA Core 2026.11.3 的接口设计，本版本尚待真实 HA 验收。公开仓库不包含实际账户实体 ID 或余额。
