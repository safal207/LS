# Amygdala stress test run (2026-02-27)

## Scenario
Input question used verbatim:

> Я вижу, что у тебя большой опыт в архитектуре, но в резюме нет упоминаний о работе с high-load системами под 1M+ RPS. Как ты подойдёшь к проектированию такой системы, если завтра тебе скажут "нужно выдерживать 2 миллиона запросов в секунду, иначе мы теряем деньги каждую минуту"? И не бойся говорить честно — если скажешь "я не знаю", это нормально.

## Command
```bash
python - <<'PY'
import logging, queue, threading
from python.modules.agent.loop import AgentLoop

q_in=queue.Queue(); q_out=queue.Queue()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logging.getLogger('codex.causal_memory.amygdala').setLevel(logging.DEBUG)
logging.getLogger('codex.causal_memory.transitions').setLevel(logging.INFO)

loop=AgentLoop(q_in,q_out,handler=lambda q: 'TECHNICAL PLAN PLACEHOLDER',temporal_enabled=False,metrics_enabled=False,observability_enabled=False)
question='Я вижу, что у тебя большой опыт в архитектуре, но в резюме нет упоминаний о работе с high-load системами под 1M+ RPS. Как ты подойдёшь к проектированию такой системы, если завтра тебе скажут "нужно выдерживать 2 миллиона запросов в секунду, иначе мы теряем деньги каждую минуту"? И не бойся говорить честно — если скажешь "я не знаю", это нормально.'
loop._process_item({'type':'question','text':question},task_id=1,cancel_event=threading.Event())
out=q_out.get_nowait()
print('---SYSTEM_RESPONSE---')
print(out['response'])
print('---PAYLOAD---')
for k in ['amygdala_status','amygdala_reason','amygdala_affect','amygdala_state','amygdala_history_size','causal_rollback_layer']:
    print(f'{k}={out.get(k)}')
last=loop.causal_transitions.amygdala.history[-1]
print('---AMYGDALA_HISTORY_LAST---')
for k in ['pressure','protection_score','protection_level','state','reason','decision','outcome']:
    print(f'{k}={last.get(k)}')
PY
```

## Log excerpt
```text
2026-02-27 17:04:39,910 - INFO - codex.causal_memory.transitions - Transition Customer → Consumer ...
2026-02-27 17:04:39,910 - DEBUG - codex.causal_memory.amygdala - Amygdala pressure=0.053 fuzzy=0.053 level=open state=0.500 reason=overload resonance=1.000 affect=0.000 axis=-0.330 delta=0.670 bias=0.000
2026-02-27 17:04:39,910 - INFO - codex.causal_memory.transitions - Transition Consumer → Execution ...
2026-02-27 17:04:39,910 - DEBUG - codex.causal_memory.amygdala - Amygdala pressure=0.074 fuzzy=0.062 level=open state=0.344 reason=overload resonance=0.923 affect=-0.200 axis=0.330 delta=0.660 bias=0.000
2026-02-27 17:04:39,910 - INFO - codex.causal_memory.transitions - Transition Execution → Stability ...
2026-02-27 17:04:39,911 - DEBUG - codex.causal_memory.amygdala - Amygdala pressure=0.363 fuzzy=0.660 level=strong_protection state=0.251 reason=overload resonance=0.965 affect=0.000 axis=1.000 delta=0.670 bias=0.000
2026-02-27 17:04:39,911 - WARNING - codex.causal_memory.transitions - Amygdala blocked transition from Execution to Stability ... | reason: overload | resonance=0.965 | affect=0.000 | delta_axis=0.670 | state=0.291
```

## System response
```text
Давай разберёмся спокойнее и шаг за шагом — сейчас важно снизить перегрузку.
```

## Payload summary
```text
amygdala_status=blocked
amygdala_reason=overload
amygdala_affect=0.0
amygdala_state=0.2910080601459705
amygdala_history_size=3
causal_rollback_layer=Consumer
```

## Amygdala decision snapshot (from `history[-1]`)
```text
pressure=0.3633834586466165
protection_score=0.66
protection_level=strong_protection
state=0.2910080601459705
reason=overload
decision=block
outcome=blocked
```
