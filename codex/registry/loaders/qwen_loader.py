from __future__ import annotations

from typing import Any, Dict


class QwenLoader:
    def load(self, config: Dict[str, Any]):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(config["path"])
        model = AutoModelForCausalLM.from_pretrained(
            config["path"],
            device_map="auto",
            torch_dtype="auto",
        )
        return {"model": model, "tokenizer": tokenizer}
