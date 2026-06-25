export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatPrice(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
