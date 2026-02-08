# Rust Transport Specification (RTT)

## 0. Purpose
RTT defines the secure transport layer for Web4 protocols (CIP/HCP/LIP). It provides encrypted p2p channels, multiplexing, and identity-bound sessions.

---

## 1. Requirements (normative)
- **End-to-end encryption** for all channels.
- **Mutual authentication** via public key fingerprints.
- **Multiplexed streams** for state vs knowledge vs control.
- **Replay protection** using nonce + timestamp.
- **Heartbeat and reconnect** with session resumption.

---

## 2. Session lifecycle
1. **Key exchange** (ed25519 identity + ephemeral session keys).
2. **Handshake** (nonce, challenge-response, fingerprint verification).
3. **Channel creation** (typed streams).
4. **Heartbeat** (configurable interval).
5. **Rekey** (periodic, rolling).

---

## 3. Channel types
- `state` — presence, lri, ltp updates
- `knowledge` — facts, decisions, DMP traces
- `control` — handshake, errors, metrics

---

## 4. API surface (Rust -> Python)
```rust
pub struct ChannelId(pub u64);

pub trait Transport {
    fn open_channel(&self, kind: ChannelKind) -> ChannelId;
    fn send(&self, channel: ChannelId, bytes: &[u8]) -> Result<(), TransportError>;
    fn receive(&self, channel: ChannelId) -> Result<Vec<u8>, TransportError>;
    fn close_channel(&self, channel: ChannelId);
}
```

---

## 5. Error semantics
- `AuthFailure` → drop session, mark peer untrusted.
- `ReplayDetected` → drop message, keep session.
- `ChannelOverflow` → backpressure + throttle.

---

## 6. Metrics
- latency (p50/p95)
- drop rate
- reconnect count
- verification failures
