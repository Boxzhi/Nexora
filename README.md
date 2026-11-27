# Nexora

Extensible local intent and conversation engine for Home Assistant.

[中文说明](README.zh-CN.md) · [Catalog protocol](docs/catalog.md)

**v0.4.0-preview** — integration test candidate, not a stable release. Requires the corresponding existing read-only intent libraries; Nexora does not provide supplier data or control devices.

## Built-in catalogs

| Module | Source | Query choices |
| --- | --- | ---: |
| ⚡ Utility | 1.1.0 | 136 |
| 💡 Lights | 1.1.0 | 144 |
| 🔌 Appliance | 1.0.0 | 78 |
| 🏠 Home | 1.0.1 | 85 |
| Total | | 443 |

Only modules with registered speech-only handlers appear. Secondary electricity account is opt-in. Lights resolve local entity IDs using the installed strict sentence lists; no household-specific entity IDs are bundled. Appliance and Home representatives match the original fixed slots and sentences. Catalogs describe query combinations, not every synonym.

Send help (帮助), exit (退出), 0 / back (返回), 99 / next (下一页), or 98 / prev (上一页). Menus display up to 20 visible choices per page; 1–20 select a choice, including each segment of a dot-separated path. English commands are case insensitive. Paging controls appear only when applicable. Root icons are catalog metadata.

## Installation

Add this repository in HACS as an Integration custom repository when available, or copy custom_components/nexora from a fixed commit. Restart Core once. Existing Nexora config entries remain valid. Keep the corresponding original intent libraries installed. Test the agent before switching your IM provider. Additional JSON/YAML catalogs under /config/nexora/catalogs/ are loaded at entry setup/reload.

## Limits and safety

The HA strict-recognition internals are targeted at Core 2026.11.3. Execute only speech-only Intent Scripts after native sentence/slot validation; no LLM fallback on failed menu query. The matching CN IM Hub test fork enables three transport lanes: strict native queries, ordered local menu/semantic/guard requests, and ordinary conversations. Without that fork, the agent still supports local menus and semantic matching, but transport concurrency is not guaranteed. Fixed Utility queries can share structured context; arbitrary parameterized and AI context capture are not supported. AI guard is heuristic, not a permissions sandbox; a tool-enabled fallback agent can still execute actions if a message escapes classification. Use a trusted restricted agent for testing. Live validation of this candidate is pending.

Targeted read-only probe: [scripts/probe.js](scripts/probe.js).

## Dynamic capabilities

443 remains the registered catalog baseline, not a fixed menu count. Light features use strict native alias resolution (cached for five minutes, refreshed lazily) and live supported_color_modes. Unknown and offline targets remain visible; previously confirmed unsupported features remain hidden until valid new metadata appears. Known Home 1.0.1 and Appliance 1.0.0 templates are statically inspected for declared bindings; Lights 1.1.0 retains strict native mapping. No binding file is required. Optional /config/nexora/bindings.yaml is a visibility override only. Unknown template structures and temporarily missing entities retain their menu entries. No supplier refresh, polling or Jinja execution for detection.

Dot-separated paths (e.g. 1.2.1) start at the current menu and cannot cross a query/parameter prompt; invalid paths restore the snapshot. Concise labels omit representative examples. Fixed registered Utility context lasts five minutes, separate from ten-minute menu sessions and 30-minute AI mappings. The negotiated CN IM Hub protocol captures exact native Slots after successful execution. Full probe reports visible-query execution separately from omission review.

Static adapters accept only the verified AST structure, excluding the literal binding dictionary. When an intent script is reloaded, the next conversation request observes the new source without polling or a Nexora reload. The known Home windows stub is hidden independently of the toilet-lid contact sensor; changed or unknown business logic is retained conservatively. Utility accounts and historical data are unchanged. No source, entity IDs or private bindings are logged or bundled.

## v0.4.0-preview acceptance

See [integration acceptance and rollback](docs/preview-acceptance.md). The 443 registered / 420 visible / 23 hidden reference is from the previously validated household, not a universal device count. Do not enable a tool-capable AI fallback merely to run the probes.
