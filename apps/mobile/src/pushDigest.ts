// SHA-256 of UTF-8 endpoint/token, matching the backend subscription IDs.
// Kept local so React Native does not depend on Web Crypto availability.
export function pushSubscriptionId(value: string): string {
  const encoded = encodeURIComponent(value).replace(/%([0-9A-F]{2})/g, (_, byte: string) => String.fromCharCode(parseInt(byte, 16)));
  const bytes = Array.from(encoded, (character) => character.charCodeAt(0));
  const bits = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  const high = Math.floor(bits / 0x100000000), low = bits >>> 0;
  for (const word of [high, low]) for (let shift = 24; shift >= 0; shift -= 8) bytes.push((word >>> shift) & 255);
  const primes: number[] = [];
  for (let n = 2; primes.length < 64; n++) if (primes.every((prime) => n % prime !== 0)) primes.push(n);
  const fraction = (number: number) => ((number - Math.floor(number)) * 0x100000000) >>> 0;
  const state = primes.slice(0, 8).map((prime) => fraction(Math.sqrt(prime)));
  const constants = primes.map((prime) => fraction(Math.cbrt(prime)));
  const rotate = (number: number, count: number) => (number >>> count) | (number << (32 - count));
  for (let offset = 0; offset < bytes.length; offset += 64) {
    const words: number[] = [];
    for (let i = 0; i < 16; i++) {
      const j = offset + 4 * i;
      words.push(((bytes[j] << 24) | (bytes[j + 1] << 16) | (bytes[j + 2] << 8) | bytes[j + 3]) >>> 0);
    }
    for (let i = 16; i < 64; i++) {
      const x = words[i - 15], y = words[i - 2];
      words.push((words[i - 16] + (rotate(x, 7) ^ rotate(x, 18) ^ (x >>> 3)) + words[i - 7] + (rotate(y, 17) ^ rotate(y, 19) ^ (y >>> 10))) >>> 0);
    }
    let [a, b, c, d, e, f, g, h] = state;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25)) + ((e & f) ^ (~e & g)) + constants[i] + words[i]) >>> 0;
      const t2 = ((rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    [a, b, c, d, e, f, g, h].forEach((word, i) => { state[i] = (state[i] + word) >>> 0; });
  }
  return state.map((word) => word.toString(16).padStart(8, "0")).join("");
}
