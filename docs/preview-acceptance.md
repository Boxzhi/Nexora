# Nexora v0.4.0-preview 独立验收候选

仅用于测试，不是正式 Release。本次只替换 Nexora，不升级 CN IM Hub、AI Hub，不修改其他集成、四套意图库、微信绑定、配置条目或 bindings.yaml。

## 安装与回滚

1. 备份 HA，记录当前 Nexora 来源及版本；下载 Nexora 固定提交源码，完整替换 custom_components/nexora，避免混装旧文件。
2. 重启 HA Core；核实 Nexora 加载、Conversation Agent 及日志。先验收本地查询，不发送实际设备控制指令。
3. 如遇异常，仅恢复备份的 Nexora 完整目录并重启 Core。无需删除集成、清空 .storage 或重新绑定微信。

## 验收顺序

- scripts/probe.js：菜单、基本追问、15 灯具单页及多位数字。
- scripts/v04_probe.js：阳台光照度原生参考、语义问句、歧义澄清、菜单、会话隔离、退出。光照值会变化，不要求完全相同。
- scripts/full_probe.js：全量只读遍历；检查 complete、execution_passed、unique_paths、unexpected_paths、navigation_errors。旧家庭环境参考 443 注册 / 420 可见 / 23 隐藏，设备变化应独立审查。国家电网初始化延迟与门锁 unknown 为此前确认的源数据限制。
- 可选微信兼容检查：保持现有 CN IM Hub，使用 help、数字菜单、按灯具、12、exit，以及普通问答（如“讲个短故事”）。如果 CN IM Hub 的原生快速通道绕过 Nexora，则不保证跨集成追问，也不保证菜单绕过同发送者的慢速 AI 对话。不要用真实设备控制命令作为测试用例。
- 可选临时开启 Nexora debug 日志，核对 local_menu、local_native、local_semantic、guard、ai 路由及耗时，测试后关闭 debug。无需修改 CN IM Hub 日志配置。

## 限制

业务上下文只记录由 Nexora 自身成功执行的固定水电气查询。外部代理直接执行的 Intent 无法同步或使旧上下文失效；切换路径后请明确账户和指标。AI fallback 仍由用户原有 Agent 配置及权限决定；实时查询识别是启发式规则，不是强制只读沙箱。Nexora 不保证第三方代理不会执行控制或产生错误回答。AI 超时为协作式取消，不意味着远端一定终止。真实环境及 HACS 发布检查仍需核实。
