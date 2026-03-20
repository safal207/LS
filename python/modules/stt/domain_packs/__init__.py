"""Domain vocabulary packs for SmartEar / PhoneticCorrector.

Each pack is a named list of domain-specific terms.  Packs can be loaded
individually or combined at ``PhoneticCorrector`` initialisation time.

Usage::

    from stt.domain_packs import load_packs

    vocab = load_packs(["web_dev", "devops"])  # → flat deduplicated list
    corrector = PhoneticCorrector(domain_vocab=vocab)

Available packs:
- ``web_dev``   — Frontend, Backend, Web standards
- ``devops``    — Infra, CI/CD, Cloud, Monitoring
- ``crypto``    — Blockchain, DeFi, Web3, smart contracts
- ``qa``        — Testing, QA methodologies, tools
"""

from __future__ import annotations

from typing import Dict, List

from .web_dev import VOCAB as _WEB_DEV
from .devops import VOCAB as _DEVOPS
from .crypto import VOCAB as _CRYPTO
from .qa import VOCAB as _QA

_REGISTRY: Dict[str, List[str]] = {
    "web_dev": _WEB_DEV,
    "devops":  _DEVOPS,
    "crypto":  _CRYPTO,
    "qa":      _QA,
}

AVAILABLE_PACKS: List[str] = list(_REGISTRY.keys())


def load_packs(names: List[str]) -> List[str]:
    """Return a flat, deduplicated vocabulary list for the given pack names.

    Unknown pack names are skipped with a warning (no crash).
    """
    import logging
    log = logging.getLogger(__name__)

    seen: set = set()
    result: List[str] = []
    for name in names:
        pack = _REGISTRY.get(name)
        if pack is None:
            log.warning("domain_packs: unknown pack %r (available: %s)", name, AVAILABLE_PACKS)
            continue
        for term in pack:
            if term not in seen:
                seen.add(term)
                result.append(term)
    return result
