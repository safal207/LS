# Reflection Dashboard — Data & Action Flowchart

Ниже — готовая визуальная диаграмма в формате **Mermaid flowchart**, чтобы вставлять в документацию (GitHub/GitLab/Markdown-рендереры с Mermaid).

```mermaid
flowchart TD
    UI["Frontend UI<br/>(Dashboard operator)"]

    SVC["ReflectionDashboardService<br/>get_dashboard_snapshot()"]

    MM["get_memory_graph()"]
    RR["get_recent_reflections()"]
    MT["get_metrics()"]
    HM["get_heatmap_data()"]

    CS[("cognitive_state<br/>memory_graph<br/>recent_reflections<br/>reflection_dashboard_log<br/>pipeline_activity")]

    SNAP["Snapshot ready<br/>(JSON for frontend)"]

    AP["approve(proposal)"]
    RJ["reject(proposal)"]
    ED["edit(proposal, value)"]

    AH["ReflectionActionHandler"]
    DP["DecisionPipeline<br/>register_action_activity()"]

    ACT[("pipeline_activity updated")]

    UI -- "request snapshot" --> SVC

    SVC --> MM
    SVC --> RR
    SVC --> MT
    SVC --> HM

    MM --> CS
    RR --> CS
    MT --> CS
    HM --> CS

    SVC -- "generate_proposals()" --> DP

    MM --> SNAP
    RR --> SNAP
    MT --> SNAP
    HM --> SNAP
    SVC --> SNAP
    SNAP --> UI

    UI --> AP
    UI --> RJ
    UI --> ED

    AP --> AH
    RJ --> AH
    ED --> AH

    AH --> DP
    DP --> ACT
    ACT --> CS
```

## Краткая интерпретация

- `get_dashboard_snapshot()` агрегирует все блоки данных и формирует единый JSON для UI.
- `approve/reject/edit` проходят через `ReflectionActionHandler`, который применяет изменения в `DecisionPipeline`.
- `DecisionPipeline.register_action_activity()` пишет события в `pipeline_activity`, что затем используется для heatmap/метрик.

## Где использовать

- `docs/` (архитектурные страницы);
- PR-описания для командного обсуждения;
- onboarding-документация операторов Reflection Dashboard.
