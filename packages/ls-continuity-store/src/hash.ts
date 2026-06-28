import crypto from "node:crypto";

export function sha256Hex(value: Uint8Array | string): string {
  const hasher = crypto.createHash("sha256");
  hasher.update(value);
  return hasher.digest("hex");
}

export function sha256Ref(value: Uint8Array | string): string {
  return `sha256:${sha256Hex(value)}`;
}
