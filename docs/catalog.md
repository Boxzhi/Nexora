# Catalog protocol v1

Catalog files use JSON or safe-loaded YAML. Each document contains schema_version: 1, module (id, name, order, version), categories (id, parent, name, order, optional aliases), and capabilities (id, category, name, order, intent, sentence, slots, read_only: true, optional parameter).

IDs are namespaced with module.id and immutable. Category parent defaults to the module ID; cycles and duplicate IDs are rejected. Explicit aliases must be globally unique and may not be reserved navigation commands. Numeric menu snapshots use capability IDs, never position as permanent identity.

The bundled catalog has two configurable account labels. {secondary} in a sentence is replaced by the locally configured existing sentence alias. Such leaves are hidden when no secondary alias is configured. Parameter kinds: month (1–12), year (2000–2099), year_month (YYYY-MM), date (YYYY-MM-DD), month_day (MM-DD). Every parameterized capability declares parameter_slots, mapping year/month/day to its own intent slot names. The Utility catalog uses luxe_utility_year/month/day. Optional parameter_year_offset: -1 is used for last-year month choices. Date inputs use HA local date and reject future dates. Registry is loaded on entry setup/reload, not watched live. Local catalog files are trusted administrator configuration.

Example:
```yaml
schema_version: 1
module:
  id: network
  name: 网络
  order: 200
  version: "1.0.0"
categories:
  - id: network.status
    name: 网络状态
    order: 10
capabilities:
  - id: network.status.online
    category: network.status
    name: 在线设备
    order: 10
    intent: NetworkStatus
    sentence: 在线设备有哪些
    slots: {}
    read_only: true
```

The example is illustrative; install a matching speech-only Intent Script and sentence definitions before it becomes executable. Availability is based on registered handler shape, not provider freshness; strict recognition and complete slot equality are checked immediately before execution. HA private recognition APIs and configured sentence triggers can disable execution; failures never route to a tool-enabled agent.

The public catalog mirrors the source Utility v1.1.0 metric set, not every synonym or unsupported property combination. Water monthly history supports current/previous and this/last year month selection, not arbitrary year/month. No supplier refresh, data copies or actions. Native speech templates remain the source of truth.

## v0.2.0 additions

Optional module.icon is rendered before the module name in the root and in its own title; it is not part of aliases. English help/exit/back/next/prev and their Chinese equivalents are reserved. Choices use 1–20 per page; 0 goes back, 98/99 navigate previous/next pages. Dot-separated paths contain choice numbers only.

The built-in Lights catalog uses the narrowly scoped native_slots: {luxe_light_id: light} field for single_state, brightness and temperature queries only. It requires a strict recognition result from the installed list, with the exact intent and all other fixed slots equal and exactly one light-domain entity slot. Other intents cannot use this facility. Local administrator-supplied lists are authoritative for the alias-to-entity mapping. No entity IDs are published. This is not a generic wildcard or a tool call.

## v0.3.0 requirements and local bindings

Optional requires is a list of declarative checks combined with AND. Supported kinds:

- {kind: native_light, feature: presence|brightness|color_temp}: only for the existing strict single-light native binding, matched to the correct query metric.
- {kind: binding, key: module.binding_id}: reads administrator-provided /config/nexora/bindings.yaml. A null value means confirmed not configured; a nonempty list contains entity IDs. Missing key = unknown, retain. A configured entity temporarily absent/unavailable is not removed.

Do not infer missing configuration by interpreting Intent Script output or parsing arbitrary templates. Local bindings affect menu visibility only; they never alter the executed slots. Example: home.family.person_grandfather: null. No device ID is required in the public catalog. A module with no visible leaves is omitted; old menu snapshots are checked by capability ID before execution. Capability caches are lazy and in memory. Version 1 remains backwards compatible.

## v0.3.1 automatic bindings

Known local speech-only templates are parsed as Jinja AST, never rendered. Structural fingerprints exclude exactly one first-statement literal binding dictionary. Home and Appliance adapters map known slot semantics to entity bindings; unknown schema or unsupported expressions remain visible. The original Home windows stub is hidden; no discovery by contact device class or friendly name. An optional explicit local binding overrides automatic binding presence (not the native light capability check). Utility is unchanged. No runtime template source or binding values are published.
