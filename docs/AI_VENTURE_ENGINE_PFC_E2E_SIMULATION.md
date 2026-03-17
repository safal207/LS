# AI Venture Engine: PFC E2E simulation

Этот сценарий демонстрирует поток **ideas → admission → gate → allocation** для `PortfolioFlowController`.

## Запуск

```bash
PYTHONPATH=python python python/examples/pfc_portfolio_simulation.py
```

## Что показывает сценарий

1. Для 10 идей рассчитывается admission-решение (`accept` / `queue` / `reject`) и expected value.
2. Для первых активных проектов выполняется gate-проверка (`pass` / `hold` / `freeze`).
3. Выполняется перераспределение бюджета по top-tier политике.
4. Печатается итоговое состояние портфеля и `treasury`.

## Программный API

Если нужно запускать не как CLI, используйте:

```python
from modules.venture import run_portfolio_simulation

result = run_portfolio_simulation(treasury=200_000.0, required_capital=20_000.0)
```

`result` содержит:
- `admissions`
- `gate_decisions`
- `allocation_decision`
- `final_state`
