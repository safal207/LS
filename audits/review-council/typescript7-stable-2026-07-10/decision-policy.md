# Decision policy

A reviewer suggestion is actionable only when all of the following are true:

1. The cited file and behavior are present at the frozen target head.
2. The consequence affects correctness, reproducibility, security, compatibility, or CI/release reliability.
3. The proposed fix addresses the root cause rather than only duplicating downstream documentation changes.
4. The fix can be validated by targeted checks and the existing repository CI.

Style-only suggestions and findings contradicted by repository scope are recorded as non-actions.
