# Nexora

Extensible local intent and conversation engine for Home Assistant.

[中文说明](README.zh-CN.md) · [Catalog protocol](docs/catalog.md)

**v0.3.1-preview** — development preview. Requires the corresponding existing read-only intent libraries; Nexora does not provide supplier data or control devices.

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

The HA strict-recognition internals are targeted at Core 2026.11.3. Execute only speech-only Intent Scripts after native sentence/slot validation; no LLM fallback on failed menu query. Menu operations still use the ordinary CN IM Hub lane; fast menu dispatch and context synchronization for upstream fast queries are future work. Basic menu-origin Utility follow-ups are supported. Data may be unavailable despite valid query execution. v0.3.1-preview requires fresh live validation; v0.1.0-preview Utility execution was verified in the target HA environment.

Targeted read-only probe: [scripts/probe.js](scripts/probe.js).

## Dynamic capabilities

443 remains the registered catalog baseline, not a fixed menu count. Light features use strict native alias resolution (cached for five minutes, refreshed lazily) and live supported_color_modes. Unknown and offline targets remain visible; previously confirmed unsupported features remain hidden until valid new metadata appears. Known Home 1.0.1 and Appliance 1.0.0 templates are statically inspected for declared bindings; Lights 1.1.0 retains strict native mapping. No binding file is required. Optional /config/nexora/bindings.yaml is a visibility override only. Unknown template structures and temporarily missing entities retain their menu entries. No supplier refresh, polling or Jinja execution for detection.

Dot-separated paths (e.g. 1.2.1) start at the current menu and cannot cross a query/parameter prompt; invalid paths restore the snapshot. Concise labels omit representative examples. Basic menu-origin Utility context lasts five minutes, separate from ten-minute menu sessions; no fast-lane context capture. Full probe reports visible-query execution separately from omission review.

Static adapters accept only the verified AST structure, excluding the literal binding dictionary. When an intent script is reloaded, the next conversation request observes the new source without polling or a Nexora reload. The known Home windows stub is hidden independently of the toilet-lid contact sensor; changed or unknown business logic is retained conservatively. Utility accounts and historical data are unchanged. No source, entity IDs or private bindings are logged or bundled.
