# Nexora

Extensible local intent and conversation engine for Home Assistant.

[中文说明](README.zh-CN.md) · [Catalog protocol](docs/catalog.md)

**v0.2.0-preview** — development preview. Requires the corresponding existing read-only intent libraries; Nexora does not provide supplier data or control devices.

## Built-in catalogs

| Module | Source | Query choices |
| --- | --- | ---: |
| ⚡ Utility | 1.1.0 | 136 |
| 💡 Lights | 1.1.0 | 144 |
| 🔌 Appliance | 1.0.0 | 78 |
| 🏠 Home | 1.0.1 | 85 |
| Total | | 443 |

Only modules with registered speech-only handlers appear. Secondary electricity account is opt-in. Lights resolve local entity IDs using the installed strict sentence lists; no household-specific entity IDs are bundled. Appliance and Home representatives match the original fixed slots and sentences. Catalogs describe query combinations, not every synonym.

Send help (帮助), exit (退出), 0 / back (返回), 9 / next (下一页), or prev (上一页). English commands are case insensitive. Menu footers display help and exit only. Root icons are catalog metadata.

## Installation

Add this repository in HACS as an Integration custom repository when available, or copy custom_components/nexora from a fixed commit. Restart Core once. Existing Nexora config entries remain valid. Keep the corresponding original intent libraries installed. Test the agent before switching your IM provider. Additional JSON/YAML catalogs under /config/nexora/catalogs/ are loaded at entry setup/reload.

## Limits and safety

The HA strict-recognition internals are targeted at Core 2026.11.3. Execute only speech-only Intent Scripts after native sentence/slot validation; no LLM fallback on failed menu query. Menu operations still use the ordinary CN IM Hub lane; natural-language contextual follow-ups and fast menu dispatch are future work. Data may be unavailable despite valid query execution. v0.2.0-preview requires fresh live validation; v0.1.0-preview Utility execution was verified in the target HA environment.

Targeted read-only probe: [scripts/probe.js](scripts/probe.js).
