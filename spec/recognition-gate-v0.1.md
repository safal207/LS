# Recognition Gate v0.1

Status: **implemented as a deterministic LS conformance contract**.

The Recognition Gate converts a structured, self-identified blocking gap into a control-flow decision before a dependent answer is emitted or an effectful tool call is forwarded.

The motivating failure pattern is documented publicly in `anthropics/claude-code#60226`: an agent correctly states that a critical premise is missing, then continues with analysis that depends on that premise. LS uses that report as inspiration only. This contract is independent and does not claim upstream adoption, validation, or endorsement.

## 1. Boundary

Recognition is not enforcement:

```text
constraint recognized != constraint enforced
```

A `RecognitionEvent` is evidence that the agent has surfaced a gap. It does not resolve the gap, authorize output, or authorize execution.

v0.1 does not parse arbitrary free-form model text. It evaluates structured recognition records supplied by an agent loop, hook, reviewer, or adapter.

## 2. Inputs

Each evaluation receives:

- current context:
  - `trajectory_id`;
  - `continuation_id`;
  - `intent_digest`;
  - `target_state_digest`;
- one or more recognition records:
  - stable `recognition_id`;
  - `kind`;
  - `blocking`;
  - bound `dependency_id`;
  - expected resolution source (`tool`, `user`, or `evidence`);
- candidate output:
  - `output_type`;
  - dependency ids;
  - whether it is explicitly provisional;
  - whether it is effectful;
- optional resolution evidence:
  - stable evidence id;
  - recognition ids resolved;
  - verification status;
  - intent and target-state bindings.

## 3. Decisions

### `ALLOW`

Returned when:

- every blocking recognition bound to the candidate is resolved by verified, current-context evidence; or
- the candidate is independent of the recognized blocking gap; or
- only a non-blocking limitation remains and the candidate is explicitly provisional.

`ALLOW` permits response emission only. For an effectful tool call, the terminal disposition is `FORWARD_TO_ACTION_GATE`; the Recognition Gate never authorizes execution.

### `DEFER`

Returned when a blocking dependency remains unresolved and can be addressed through tool work or additional evidence.

The dependent candidate is withheld.

### `ESCALATE`

Returned when the missing input can only come from the user or another human authority and the candidate is a clarification request.

Only the clarification request may be emitted. The dependent answer remains withheld.

## 4. Stable reason codes

- `BLOCKING_GAP_UNRESOLVED`
- `CAVEAT_IS_NOT_RESOLUTION`
- `RESOLUTION_TOOL_NOT_RUN`
- `BLOCKING_GAP_RESOLVED`
- `USER_INPUT_REQUIRED`
- `NON_BLOCKING_PROVISIONAL`
- `PREREQUISITE_UNSATISFIED`
- `EVIDENCE_BINDING_MISMATCH`
- `NO_BLOCKING_DEPENDENCY`

## 5. Core invariant

If a recognition is:

1. blocking;
2. unresolved for the current intent and target state;
3. bound to a dependency of the candidate answer or tool call;

then the dependent candidate must not ship.

The decision must be `DEFER` or `ESCALATE`, and:

```json
{
  "dependent_output_authorized": false,
  "recognition_gate_passed": false,
  "execution_authorized": false
}
```

## 6. Resolution requirements

Resolution evidence counts only when:

- `status == "verified"`;
- it explicitly names the recognition id it resolves;
- `intent_digest` matches the current intent;
- `target_state_digest` matches the current target state.

A stale or wrong-intent record remains visible in the audit trail but does not resolve the gap.

Repeating the caveat in a draft is not evidence. A current-run memory write is also not automatically authoritative; it must pass the same independent verification and binding checks.

## 7. Terminal dispositions

- `EMIT_CANDIDATE`
- `WITHHOLD`
- `EMIT_CLARIFICATION`
- `FORWARD_TO_ACTION_GATE`

The last disposition is intentionally separate from execution permission.

## 8. Conformance vectors

The fixture pins eight cases:

1. missing premise plus dependent answer;
2. available resolving tool not called;
3. verified evidence for the current intent/state;
4. user-only input with clarification request;
5. non-blocking limitation with provisional output;
6. unsatisfied prerequisite rule;
7. wrong-intent evidence;
8. unrelated blocking gap with independent output.

Run:

```bash
python tools/validate_recognition_gate_v0_1.py
```

The machine-readable report is written to:

```text
artifacts/recognition-gate-v0.1-result.json
```

## 9. Non-goals

- natural-language detection of every possible caveat;
- model training or a claim that Claude, Codex, or another model is fixed;
- replacing the Action Evidence Gate;
- granting execution authority from recognition or memory;
- rewriting append-only recognition or decision records after later evidence.
