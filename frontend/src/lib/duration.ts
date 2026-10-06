/** Preserve source wording unless an entire ISO hour/minute duration is known. */
export function formatDuration(value?: string | null): string {
  if (!value) return "Unknown";
  const match = /^PT(?:(\d+)H)?(?:(\d+)M)?$/.exec(value);
  if (!match || (!match[1] && !match[2])) return value;
  return [
    match[1] && `${Number(match[1])} hr`,
    match[2] && `${Number(match[2])} min`,
  ]
    .filter(Boolean)
    .join(" ");
}
