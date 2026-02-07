from __future__ import annotations

from typing import Any, Dict


class PhiLoader:
    def load(self, config: Dict[str, Any]):
        backend = config.get("backend", "transformers")
        if backend == "ollama":
            import ollama

            return ollama.Client()
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(config["path"])
        model = AutoModelForCausalLM.from_pretrained(
            config["path"],
            torch_dtype="auto",
            device_map="auto",
        )
        return {"model": model, "tokenizer": tokenizer}
