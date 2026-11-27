# v0.4.0-preview 联合验收候选

仅用于受控测试，不是正式 Release。先备份 HA（包括两个 custom_components 目录、配置条目和 .storage 中相关持久化队列），等待微信现有任务全部完成，避免在替换代码时中断请求。不得删除现有集成配置、原始四套意图库或重建 bindings.yaml。

## 安装与回滚

1. 使用本次提供的 Nexora 精确提交及 CN IM Hub 配套分支源代码；解压后替换对应 custom_components/nexora 和 custom_components/cn_im_hub 目录，禁止将旧文件残留混装。先记录当前已安装的两个版本和来源。不要同时安装同域名的第二个集成。
2. 重启 HA Core，检查两个集成加载和日志；CN IM Hub 配置的对话 Agent 应为 Nexora。先只验收本地查询，不发送设备控制或不可信命令。
3. 如遇启动失败、菜单失效、消息异常：停止测试、等待/终止当前请求，恢复备份的两个完整目录及必要时对应配置/存储备份，重启 Core；回到 v0.3.1-preview 验收基线。不要盲目删除 .storage 或重放未确认消息。

## 验收顺序

- scripts/probe.js：菜单、基本追问、15 灯具单页及多位数字。
- scripts/v04_probe.js：阳台光照度原生参考、六种语义问句、两种歧义澄清、菜单、会话隔离、退出；实际光照会变化，不要求六条数值完全一致。
- scripts/full_probe.js：全量只读遍历；检查 complete、execution_passed、unique_paths、unexpected_paths、navigation_errors。旧环境参考 443 注册 / 420 可见 / 23 隐藏，若设备变化应独立审查隐藏项。国家电网重启后暂时不可用、门锁 unknown 为此前确认的源数据限制。
- 微信：在确认备用代理权限受限之后发送普通问答（如“讲一个短故事”），立即连续发 help、2、按灯具、12。另起测试依次发送“这个月用了多少度电”“上个月呢”“费用呢”“另一个账户呢”；核实四次本地结果及日志 route。测试重复数字应按顺序执行，不应合并。
- 临时开启两个集成 debug 日志核对 local_fast / local_menu / local_semantic / local_guard / normal 和 Nexora 的聚合路由、耗时；测试完成关闭 debug。第三方 Agent 可能记录内容，勿分享账户、消息 token 或实体私有数据。

## 已知限制

AI Hub 普通入口可能运行 HA 内置 Intent 或使用 Assist 工具。当前家庭保护依赖规则，不能作为强制权限边界。普通 AI 仍是既有外部代理；未实现受控 AI 工具协议，不应将此候选用于要求严格只读的 AI 自动化。复杂、多媒体、引用及任意新句式不保证本地匹配。实际 HA/微信并发、外部 API 延迟、HACS 仓库品牌检查和真实可见能力必须另行确认。
