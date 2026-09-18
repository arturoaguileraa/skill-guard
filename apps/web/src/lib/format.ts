/** Compact counts for the UI: 10246 → "10.2k", 1_250_000 → "1.3M"; under 1,000 stays exact. */
export function formatCount(n: number): string {
	const abs = Math.abs(n);
	const trim = (s: string) => s.replace(/\.0$/, "");
	if (abs < 1_000) return String(n);
	// 999,950+ would round to "1000k"; roll it into millions instead.
	if (abs < 999_950) return `${trim((n / 1_000).toFixed(1))}k`;
	return `${trim((n / 1_000_000).toFixed(1))}M`;
}
