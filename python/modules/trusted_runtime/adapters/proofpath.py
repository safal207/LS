"""ProofPath authorization adapter boundary.

The implementation lives in ``trusted_runtime.authorization`` so the portable
bundle contract and offline verifier remain usable without importing optional
adapter packages.
"""

from ..authorization import ProofPathAuthorizationBundleAdapter, ProofPathConfig

__all__ = ["ProofPathAuthorizationBundleAdapter", "ProofPathConfig"]
