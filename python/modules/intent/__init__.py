"""Intent + WHY layers — structured intent and causal intent extraction.

Pipeline position::

    SmartEar [SelectionStage]
        → IntentLayer   (what does the user want?)
        → WhyLayer      (why are they asking this?)
        → AgentLoop

IntentLayer output::

    IntentResult(type="definition", entity="React",
                 params={"domain": "web_dev"}, confidence=0.91)

WhyLayer output::

    WhyIntent(goal="evaluate_knowledge", pressure_level="low",
              expected_answer_type="conceptual", follow_up_expected=False,
              hints=["Дай чёткое определение ...", ...], confidence=0.82)
"""

from .intent_layer import IntentLayer, IntentResult, IntentType
from .why_layer import WhyLayer, WhyIntent, Goal, Pressure, AnswerType

__all__ = [
    "IntentLayer", "IntentResult", "IntentType",
    "WhyLayer", "WhyIntent", "Goal", "Pressure", "AnswerType",
]
