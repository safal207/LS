# VTL v0.10 — Cross-Language Canonical Proof

## Problem

VTL v0.8 and v0.9 introduced signed and freshness-checked proof layers. A signature or digest is only portable when independent runtimes agree on the exact bytes being hashed.

Python's common `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` is deterministic inside Python, but it is not by itself a cross-language canonicalization contract. In particular, object-name ordering can diverge for supplementary-plane Unicode characters, and JavaScript cannot represent arbitrary integers exactly.

## Canonical profile

v0.10 defines:

```text
rfc8785-safe-integer/v0.10
```

It is a deliberately restricted, RFC 8785/JCS-compatible domain:

```text
null
boolean
string
integer within [-9007199254740991, 9007199254740991]
array of supported values
object with unique Unicode-scalar string names and supported values
```

Floating-point forms are outside the profile. This avoids claiming full RFC 8785 number serialization before both runtimes implement the ECMAScript number-to-string rules for every finite IEEE-754 value.

## Canonical bytes

For supported values:

1. object names are sorted lexicographically by UTF-16 code units;
2. insignificant whitespace is removed;
3. strings use JSON escaping for quote, backslash, and control characters;
4. the shortest standard escapes are used for backspace, tab, newline, form-feed, and carriage return;
5. other U+0000..U+001F controls use lowercase `\\u00xx` escapes;
6. all other Unicode scalar values are emitted directly and encoded as UTF-8;
7. Unicode normalization is **not** performed;
8. integers are emitted in base-10 form, with `-0` canonicalized to `0`;
9. the canonical digest is SHA-256 over the exact UTF-8 byte sequence.

## Strict raw-JSON boundary

Canonicalization starts from a semantic JSON value, but v0.10 also supplies strict raw-JSON parsers in Python and Node so malformed input cannot silently collapse into a different semantic object.

The boundary rejects:

```text
duplicate object names       -> DUPLICATE_KEY
floating/exponent numbers    -> UNSUPPORTED_NUMBER
unsafe integers              -> INTEGER_OUT_OF_RANGE
lone UTF-16 surrogates       -> INVALID_UNICODE_SCALAR
invalid JSON                  -> INVALID_JSON
```

Duplicate-key rejection matters because ordinary JSON object parsers frequently keep only the last value, which would make the original byte-level ambiguity invisible after parsing.

## Cross-runtime proof

The fixture is authoritative test data:

```text
fixtures/canonical-proof-v0.10.json
```

Each positive vector contains raw JSON plus expected canonical UTF-8 bytes encoded as base64 and an expected SHA-256 digest.

Independent implementations consume the same fixture:

```text
Python: vtl-canonical-verify
Node:   node reference/canonical-v0.10.mjs
```

CI requires:

```text
Python bytes == expected bytes
Node bytes   == expected bytes
Python digest == expected digest
Node digest   == expected digest
Python structured result == Node structured result
```

The positive profile covers key/whitespace changes, nested object order, alternate escape spelling, composed and decomposed Unicode, supplementary-plane key sorting, control escaping, arrays, safe-integer boundaries, and a VTL-shaped transition payload.

Negative vectors cover floating-point values, exponent notation, unsafe integers, duplicate names, and lone surrogates. A semantic-mutation vector proves that changing an actual field changes the canonical digest.

## Relationship to existing VTL proofs

v0.10 does **not** silently change v0.4/v0.7/v0.8/v0.9 identifiers, digests, signatures, or historical fixtures. Those versions retain their exact published semantics.

Instead, v0.10 establishes a portable canonicalization profile that future receipt/signature versions can opt into explicitly by profile/version. Migration must be versioned because changing canonical bytes changes proof identity.

## Trust ceiling

This profile intentionally does not claim:

- full RFC 8785 floating-point coverage;
- Unicode normalization or confusable detection;
- equivalence between semantically similar but textually different Unicode strings;
- a globally current trust-root oracle;
- transparency-log consensus;
- production KMS/HSM key custody.

It proves a narrower but load-bearing property: for the supported VTL JSON domain, independent Python and Node implementations agree on the exact canonical bytes and digest, and reject inputs that cannot be represented safely across both runtimes.
