// getRandomValues работает и на HTTP в локальной сети, в отличие от randomUUID.
export function newRequestKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}
