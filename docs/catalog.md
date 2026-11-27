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
