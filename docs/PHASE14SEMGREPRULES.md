# Phase 14 Semgrep Rules

Файл правил: `semgrep/phase14_rules.yml`.

Проверяются ограничения:

- запрет вызова `updatefrom*`;
- запрет неконтролируемого `collective_state` mutation;
- контроль вызовов `agent.step()`;
- требование context-native обновлений;
- запрет ручного изменения `max_signals_per_tick` вне `_apply_regulator()`.

Запуск:

```bash
semgrep --config semgrep/phase14_rules.yml python/modules/nca
```
