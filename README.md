# Nexora

Extensible local intent and conversation engine for Home Assistant.

[中文说明](README.zh-CN.md) · [Catalog protocol](docs/catalog.md)

**0.1.0-preview** — development preview, not a stable release. Requires the existing read-only intent library; Nexora does not provide supplier data or control devices.

- Opt-in conversation agent with a configurable fallback agent.
- Numbered menus, nested navigation, paging, session isolation, and date parameters.
- Built-in Utility v1.1.0 catalog covers 63 distinct utility-kind/metric pairs, including two electricity accounts, water, gas, and combined queries. Secondary account is opt-in.
- Execution checks the installed speech-only Intent Script and strict native sentence/slot recognition. No LLM fallback on menu query failure.
- Additional JSON/YAML catalogs under /config/nexora/catalogs/ are loaded at integration setup. No core menu edits required.

## Installation

Add this repository in HACS as an Integration custom repository once a preview release is available (or download the source and copy custom_components/nexora). Restart Core once, add Nexora under Devices & Services, and enter the current fallback conversation agent ID and account labels/alias. Keep the original intent library installed. Test Nexora with conversation.process before switching the IM agent. Uninstall the old proof-of-concept integration separately; no migration is provided.

## Limitations

Only Utility is included in this preview. Account aliases and matching must be supplied locally. The HA strict-recognition internals are targeted at Core 2026.11.3; other versions are not certified. Menu operations use the ordinary CN IM Hub lane and can wait behind an LLM request. No stateful natural-language follow-ups yet. Registry refresh requires integration reload; sessions are in memory and expire after ten minutes. No real HA validation of this preview has been completed at initial commit. See Actions for test status.
