"""Intent Layer — extracts structured intent from interpreted text.

Pipeline position::

    SmartEar [SelectionStage] → IntentLayer → AgentLoop

Transforms a resolved utterance into a structured intent object:

    IntentResult(
        type="definition",
        entity="React",
        params={"domain": "web_dev"},
        confidence=0.91,
        raw_text="что такое React",
    )
"""

from .intent_layer import IntentLayer, IntentResult, IntentType

__all__ = ["IntentLayer", "IntentResult", "IntentType"]
