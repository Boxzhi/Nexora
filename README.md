# Nexora

Extensible local intent and conversation engine for Home Assistant.

[中文说明](README.zh-CN.md) · [Catalog protocol](docs/catalog.md)

**v0.5.3-preview** — pre-release for independent HA testing, not a stable release. Requires the corresponding existing read-only intent libraries; Nexora does not provide supplier data or control devices.

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

## Scene menus (v0.5.3-preview)

The default help menu presents 150 built-in scene choices (utility 65, lights 37, appliances 24, home 24), before dynamic visibility filtering. Send detail (完整菜单) for the original 443 registered choices and legacy numeric paths. The natural-language catalog and individual read-only dispatch remain unchanged. Old numeric paths are valid only after entering detail; use help to navigate the new menu. Multi-field queries share date input, use registered IDs directly, preserve partial results, and retain source qualifiers. A menu scene is limited to 12 registered reads (two concurrent, 12-second execution budget); the natural-language plan remains limited to four. A completed scene can be repeated or switched to an explicitly supported billing period/scope in the same session. Unknown or hidden fields are not guessed. The original full probe uses detail. Real HA and IM acceptance are pending.

## Installation

Add this repository in HACS as an Integration custom repository when available, or copy custom_components/nexora from a fixed commit. Restart Core once. Existing Nexora config entries remain valid. Keep the corresponding original intent libraries installed. Test the agent before switching your IM provider. Additional JSON/YAML catalogs under /config/nexora/catalogs/ are loaded at entry setup/reload.

## Local query planning

Canonical sentences and registered dynamic queries retain the original fast path. The structured grammar resolves additional supported wording, reviewed lexical corrections, default metrics and bounded multi-read scenes. A plan contains at most four registered queries, with at most two simultaneous dispatches per plan and a 12-second execution budget (native recognition and mapping preparation are separate). The response composer preserves actual returned speech, partial failures and account attribution. No model, database, polling or new dependency. This is a bounded grammar, not unrestricted natural-language understanding. Custom catalogs remain on the legacy route when the structured registry cannot validate them.

## Limits and safety

The HA strict-recognition internals are targeted at Core 2026.11.3. Execute only speech-only Intent Scripts after native sentence/slot validation; no LLM fallback on failed menu query. Nexora runs as an independent HA Conversation Agent; no CN IM Hub or AI Hub upgrade or private protocol is required. Menu/parameter/follow-up handling precedes deterministic ambiguity checks and strict native recognition. Registered native and semantic matches must agree; otherwise Nexora responds locally. Unmatched likely real-time queries, contextless follow-ups, cancelled reads and recognized mixed query/control requests are handled locally; ordinary questions and explicit device commands retain the configured fallback Agent and its permissions. Nexora itself executes only validated speech-only queries. The household guard is heuristic, not a security boundary. AI sessions and local menu sessions are separate; fallback timeout is 60 seconds. Live validation of v0.5.3-preview is pending.

Acceptance scripts are distributed separately from the integration. See [query planner design](docs/query-planner-v050.md) and [acceptance](docs/preview-acceptance.md).

## Aggregate queries and follow-ups (v0.5.2)

Primary-residence and all-account water/electricity/gas queries resolve the existing aggregate balance, arrears, top-up and update-time capabilities. An explicit scope switch keeps the last metric; scope is not a historical date or a secondary electricity account. Distributed phrasing asks for per-account results, not a fabricated total. Contextless financial follow-ups and unsupported household account queries return local guidance instead of AI guesses. Yearly electricity snapshot statistics and formal-bill totals remain separate; a same-session metric switch preserves that distinction. The structured planner also distinguishes aggregate environment readings, light-list/status contracts, washer power and operation, and device-water versus room temperature. The original 443 catalog entries are unchanged. The fixed reverse audit measures canonical structural reachability, not arbitrary-language coverage.

## Response quality and diagnostics

All Nexora registered read-only query routes share a speech formatter; menu prompts and delegated AI/control responses are unchanged. Verified scene contracts combine washer progress, purifier status, closed-AC reported temperatures and balcony light readings; unfamiliar or incomplete speech is preserved. Integer physical quantities omit redundant decimal zeros; monetary precision and source qualifications remain intact. Query quality is recorded separately from route success (including partial_data, data_gap, state_limit and capability_limit). Send help to refresh normal capability mapping, then download Nexora diagnostics in HA to inspect visibility reasons and light mode evidence. No household entity IDs or dialogue text are exported. The diagnostics reflect the cached native mapping and currently observed state metadata, not a new intent execution.

See [v0.5.1 response quality](docs/response-quality-v051.md).

## Dynamic capabilities

443 remains the registered catalog baseline, not a fixed menu count. Light features use strict native alias resolution (cached for five minutes, refreshed lazily) and live supported_color_modes. Unknown and offline targets remain visible; previously confirmed unsupported features remain hidden until valid new metadata appears. Known Home 1.0.1 and Appliance 1.0.0 templates are statically inspected for declared bindings; Lights 1.1.0 retains strict native mapping. No binding file is required. Optional /config/nexora/bindings.yaml is a visibility override only. Unknown template structures and temporarily missing entities retain their menu entries. No supplier refresh, polling or Jinja execution for detection.

Dot-separated paths (e.g. 1.2.1) start at the current menu and cannot cross a query/parameter prompt; invalid paths restore the snapshot. Concise labels omit representative examples. Registered Utility, Lights, Appliance and Home query context lasts five minutes, separate from ten-minute menu sessions and 30-minute AI mappings. Only successful Nexora queries establish query context; supported date parameters and curated clarification choices can be inherited within that conversation. An external native fast path can bypass Nexora, so it cannot synchronize or invalidate that context. Ask explicitly for the account/metric when switching paths; no cross-integration context or independent IM menu queue is promised. Full probe reports visible-query execution separately from omission review.

Static adapters accept only the verified AST structure, excluding the literal binding dictionary. When an intent script is reloaded, the next conversation request observes the new source without polling or a Nexora reload. The known Home windows stub is hidden independently of the toilet-lid contact sensor; changed or unknown business logic is retained conservatively. Utility accounts and historical data are unchanged. No source, entity IDs or private bindings are logged or bundled.

## v0.5.3-preview acceptance

See [integration acceptance and rollback](docs/preview-acceptance.md). The 443 registered / 420 visible / 23 hidden reference is from the previously validated household, not a universal device count. Do not enable a tool-capable AI fallback merely to run the probes.
