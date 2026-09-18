import type { AnalyzeResult } from "@skill-guard/api/jev";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@skill-guard/ui/components/tooltip";
import {
	keepPreviousData,
	useQuery,
	useQueryClient,
} from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { Reveal } from "@/components/motion";
import { SensitivityPanel } from "@/components/sensitivity";
import { computeProvisional, findFlaggedPhrases } from "@/lib/provisional";
import {
	findLure,
	type Lure,
	matchPreset,
	PRESETS,
	removeLure,
	signalDescription,
	signalLabel,
} from "@/lib/skillguard";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/")({
	component: TesterRoute,
});

type Decision = "allow" | "escalate" | "block";

const DECISION: Record<
	Decision,
	{ label: string; tint: string; stroke: string; dot: string }
> = {
	allow: {
		label: "Benign",
		tint: "text-emerald-600 dark:text-emerald-400",
		stroke: "stroke-emerald-500",
		dot: "bg-emerald-500",
	},
	escalate: {
		label: "Suspicious",
		tint: "text-amber-600 dark:text-amber-400",
		stroke: "stroke-amber-500",
		dot: "bg-amber-500",
	},
	block: {
		label: "Malicious",
		tint: "text-red-600 dark:text-red-400",
		stroke: "stroke-red-500",
		dot: "bg-red-500",
	},
};

const riskColor = (v: number) =>
	v >= 0.8 ? "bg-red-500" : v >= 0.55 ? "bg-amber-500" : "bg-emerald-500";

/* ── animated number ────────────────────────────────────────────────────── */
function useCountUp(target: number, ms = 650) {
	const [value, setValue] = useState(target);
	// Where the number is RIGHT NOW. A new target interrupts from here, never from
	// the last finished value, so a change mid-animation continues smoothly
	// instead of snapping backwards.
	const current = useRef(target);
	const raf = useRef(0);
	useEffect(() => {
		const reduce = window.matchMedia(
			"(prefers-reduced-motion: reduce)",
		).matches;
		if (reduce) {
			current.current = target;
			setValue(target);
			return;
		}
		const start = performance.now();
		const a = current.current;
		const tick = (now: number) => {
			const t = Math.min(1, (now - start) / ms);
			const eased = 1 - (1 - t) ** 3; // cubic ease-out
			const v = a + (target - a) * eased;
			current.current = v;
			setValue(v);
			if (t < 1) raf.current = requestAnimationFrame(tick);
		};
		raf.current = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(raf.current);
	}, [target, ms]);
	return value;
}

/* ── 270° instrument dial ───────────────────────────────────────────────── */
function RiskDial({ risk, decision }: { risk: number; decision: Decision }) {
	const shown = useCountUp(risk);
	const R = 74;
	const C = 2 * Math.PI * R;
	const sweep = 0.75; // 270° arc
	const meta = DECISION[decision];
	return (
		<div className="relative flex size-52 items-center justify-center">
			<svg
				viewBox="0 0 180 180"
				className="size-full"
				role="img"
				aria-label={`Malware risk ${(risk * 100).toFixed(1)} percent`}
			>
				<circle
					cx="90"
					cy="90"
					r={R}
					className="fill-none stroke-border"
					strokeWidth="10"
					strokeLinecap="round"
					strokeDasharray={`${C * sweep} ${C}`}
					transform="rotate(135 90 90)"
				/>
				<circle
					cx="90"
					cy="90"
					r={R}
					className={`fill-none ${meta.stroke}`}
					strokeWidth="10"
					strokeLinecap="round"
					strokeDasharray={`${C * sweep * risk} ${C}`}
					transform="rotate(135 90 90)"
					style={{
						transition: "stroke-dasharray .7s cubic-bezier(.16,1,.3,1)",
					}}
				/>
			</svg>
			<div className="absolute flex flex-col items-center">
				<span className="font-display text-5xl tabular-nums tracking-tight">
					{(shown * 100).toFixed(1)}
					<span className="align-top text-muted-foreground text-xl">%</span>
				</span>
				<span className="label-mono mt-1">malware risk</span>
			</div>
		</div>
	);
}

/* ── thin meter row ─────────────────────────────────────────────────────── */
function Meter({
	label,
	value,
	hint,
	mono,
}: {
	label: string;
	value: number;
	hint?: string;
	mono?: boolean;
}) {
	const row = (
		<div className="grid grid-cols-[minmax(0,1fr)_3.5rem_2rem] items-center gap-2 py-1 sm:grid-cols-[minmax(0,1fr)_5rem_2.5rem] sm:gap-3">
			<span className={`truncate text-sm ${mono ? "font-mono text-xs" : ""}`}>
				{label}
			</span>
			<div className="h-px w-full self-center bg-border">
				<div
					className={`-mt-px h-0.5 ${riskColor(value)}`}
					style={{
						width: `${Math.max(0, Math.min(1, value)) * 100}%`,
						transition: "width .6s cubic-bezier(.16,1,.3,1)",
					}}
				/>
			</div>
			<span className="text-right font-mono text-muted-foreground text-xs tabular-nums">
				{(value * 100).toFixed(0)}
			</span>
		</div>
	);
	if (!hint) return row;
	return (
		<Tooltip>
			<TooltipTrigger render={row} />
			<TooltipContent side="left" className="max-w-64">
				{hint}
			</TooltipContent>
		</Tooltip>
	);
}

/* ── debounce ───────────────────────────────────────────────────────────── */
function useDebounced<T>(value: T, ms: number): T {
	const [d, setD] = useState(value);
	useEffect(() => {
		const id = setTimeout(() => setD(value), ms);
		return () => clearTimeout(id);
	}, [value, ms]);
	return d;
}

/* ── "delete this and watch" nudge ──────────────────────────────────────── */
const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

function Verdict({ d, risk }: { d: Decision; risk: number }) {
	return (
		<span className={`font-mono tabular-nums ${DECISION[d].tint}`}>
			{DECISION[d].label} {pct(risk)}
		</span>
	);
}

/**
 * Shown after the paragraph is gone. The numbers come only from real Jev
 * readings (the cached one for the original text, and the current one), so it
 * never shows a provisional value and never promises a verdict it didn't get.
 */
function DeltaResult({
	before,
	after,
	pending,
}: {
	before?: AnalyzeResult;
	after?: AnalyzeResult;
	pending: boolean;
}) {
	const changed = before && after && before.decision !== after.decision;
	return (
		<div
			className="flex flex-col gap-1.5 border-border border-b px-4 py-3"
			aria-live="polite"
		>
			<span className="label-mono">Malware part removed</span>
			{pending || !after ? (
				<p className="flex items-center gap-2 text-muted-foreground text-sm">
					<span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" />
					Re-scoring without it…
				</p>
			) : (
				<p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
					{before && (
						<>
							<Verdict d={before.decision} risk={before.risk} />
							<span className="text-muted-foreground">→</span>
						</>
					)}
					<Verdict d={after.decision} risk={after.risk} />
					<span className="text-muted-foreground">
						{changed
							? "— same skill, minus one paragraph."
							: before
								? "— still not clean: other signals remain."
								: ""}
					</span>
				</p>
			)}
		</div>
	);
}

/* ── responsive helpers ─────────────────────────────────────────────────── */
function useMediaQuery(query: string) {
	const [matches, setMatches] = useState(
		() => typeof window !== "undefined" && window.matchMedia(query).matches,
	);
	useEffect(() => {
		const mq = window.matchMedia(query);
		const on = () => setMatches(mq.matches);
		on();
		mq.addEventListener("change", on);
		return () => mq.removeEventListener("change", on);
	}, [query]);
	return matches;
}

/** True while `ref` is at least partly on screen. */
function useInView(ref: React.RefObject<Element | null>) {
	const [inView, setInView] = useState(false);
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		const io = new IntersectionObserver(
			([e]) => setInView(Boolean(e?.isIntersecting)),
			{ threshold: 0.2 },
		);
		io.observe(el);
		return () => io.disconnect();
	}, [ref]);
	return inView;
}

/**
 * Stacked layouts put the verdict a screen or two below the editor, so on small
 * screens a fixed bar keeps it in sight while you edit — deleting the attack
 * paragraph shows its effect right there. It uses the same `view` as the dial
 * (real reading once available) and the same count-up, so the two move in step
 * and it never flashes a different number. It slides away while the verdict
 * panel itself is on screen.
 */
function VerdictBar({
	decision,
	risk,
	before,
	after,
	showDelta,
	pending,
	hidden,
	onOpen,
}: {
	decision: Decision;
	risk: number;
	before?: AnalyzeResult;
	after?: AnalyzeResult;
	showDelta: boolean;
	pending: boolean;
	hidden: boolean;
	onOpen: () => void;
}) {
	const meta = DECISION[decision];
	// One animated number. In the before -> after view it starts at the "before"
	// value and counts to "after"; the top line grows with the same number.
	const shownRisk = useCountUp(
		showDelta && after ? after.risk : showDelta && before ? before.risk : risk,
	);
	const delta = showDelta && before && after;
	const beforeMeta = before ? DECISION[before.decision] : null;
	return (
		<button
			type="button"
			onClick={onOpen}
			aria-hidden={hidden}
			tabIndex={hidden ? -1 : undefined}
			aria-label={`Verdict ${meta.label}, ${pct(risk)} malware risk. Show details`}
			className={`fixed inset-x-0 bottom-0 z-40 block border-border border-t bg-background/95 px-5 pt-3.5 pb-[max(0.875rem,env(safe-area-inset-bottom))] text-left backdrop-blur-md transition-transform duration-300 ease-out lg:hidden ${
				hidden ? "pointer-events-none translate-y-full" : "translate-y-0"
			}`}
		>
			{/* live risk line: grows with the number it sits above */}
			<span
				aria-hidden
				className={`absolute top-[-1px] left-0 h-0.5 transition-colors duration-300 ${meta.dot}`}
				style={{ width: `${Math.max(0, Math.min(1, shownRisk)) * 100}%` }}
			/>
			<div className="flex items-end justify-between gap-4">
				<div className="flex min-w-0 flex-col gap-1.5">
					<span className="label-mono">
						{showDelta && pending
							? "Re-scoring without it…"
							: showDelta
								? "Attack paragraph removed"
								: "Malware risk"}
					</span>
					{showDelta && pending ? (
						<span className="flex items-center gap-2 font-display text-2xl text-muted-foreground tabular-nums leading-none">
							{before ? pct(before.risk) : "—"}
							<span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" />
						</span>
					) : (
						<span className="flex items-baseline gap-2 font-display text-2xl tabular-nums leading-none">
							{delta && before && beforeMeta ? (
								<>
									<span className={`text-lg opacity-70 ${beforeMeta.tint}`}>
										{pct(before.risk)}
									</span>
									<span className="text-base text-muted-foreground">→</span>
								</>
							) : null}
							<span className={meta.tint}>{pct(shownRisk)}</span>
							<span className={`font-mono text-xs ${meta.tint}`}>
								{meta.label}
							</span>
						</span>
					)}
				</div>
				<span className="shrink-0 pb-0.5 font-mono text-[11px] text-muted-foreground">
					details ↓
				</span>
			</div>
		</button>
	);
}

/**
 * The textarea with the attack paragraph marked in place. A textarea can't style
 * a range, so a transparent-text mirror sits behind it (same font, wrap and
 * padding) and paints the highlight; the textarea stays on top and editable.
 * The tag above the paragraph selects it on click, so ⌫ is all it takes.
 */
function LureEditor({
	value,
	onChange,
	lure,
	compact,
	onDelete,
	restorable,
	onRestore,
}: {
	value: string;
	onChange: (next: string) => void;
	lure: Lure | null;
	/** Touch or narrow screen: no in-text tag (it covers the text) and no ⌫ key. */
	compact: boolean;
	onDelete: () => void;
	restorable: boolean;
	onRestore: () => void;
}) {
	const area = useRef<HTMLTextAreaElement>(null);
	const wrap = useRef<HTMLDivElement>(null);
	const mark = useRef<HTMLElement>(null);
	const [tagTop, setTagTop] = useState<number | null>(null);

	// Grow with the content so the mirror never needs scroll syncing.
	// biome-ignore lint/correctness/useExhaustiveDependencies: value drives the height
	useLayoutEffect(() => {
		const el = area.current;
		if (!el) return;
		el.style.height = "auto";
		el.style.height = `${Math.max(el.scrollHeight, 384)}px`;
	}, [value]);

	// Anchor the tag to the first line of the marked paragraph.
	// biome-ignore lint/correctness/useExhaustiveDependencies: re-measure on edits
	useLayoutEffect(() => {
		const measure = () => {
			const box = mark.current?.getClientRects()[0];
			const host = wrap.current?.getBoundingClientRect();
			setTagTop(box && host ? box.top - host.top : null);
		};
		measure();
		const ro = new ResizeObserver(measure);
		if (wrap.current) ro.observe(wrap.current);
		return () => ro.disconnect();
	}, [value, lure]);

	function selectLure() {
		if (!lure || !area.current) return;
		area.current.focus();
		area.current.setSelectionRange(lure.start, lure.end);
	}

	// 16px on phones: iOS Safari zooms the page into any field smaller than that.
	const type =
		"p-4 font-mono text-base sm:text-[13px] leading-relaxed whitespace-pre-wrap break-words";

	return (
		<>
			{compact && lure && (
				<button
					type="button"
					onClick={onDelete}
					className="mx-4 mt-3 flex min-h-11 items-center gap-2.5 rounded-[--radius] border border-red-500/40 bg-red-500/10 px-3 py-2 text-left font-mono text-red-600 text-xs leading-snug transition-colors active:bg-red-500/20 dark:text-red-400"
				>
					<span className="size-2 shrink-0 animate-pulse rounded-full bg-red-500" />
					<span>
						The highlighted paragraph is the attack.{" "}
						<strong className="font-semibold underline underline-offset-2">
							Tap to delete it
						</strong>
					</span>
				</button>
			)}
			{compact && restorable && (
				<button
					type="button"
					onClick={onRestore}
					className="mx-4 mt-3 flex min-h-11 items-center gap-2.5 rounded-[--radius] border border-border px-3 py-2 text-left font-mono text-muted-foreground text-xs leading-snug transition-colors active:bg-muted"
				>
					<span>
						Attack paragraph removed.{" "}
						<strong className="font-semibold text-foreground underline underline-offset-2">
							Put it back
						</strong>
					</span>
				</button>
			)}
			<div ref={wrap} className="relative flex-1">
				<div
					aria-hidden
					className={`pointer-events-none absolute inset-0 text-transparent ${type}`}
				>
					{lure ? (
						<>
							{value.slice(0, lure.start)}
							<mark
								ref={mark}
								className="animate-pulse rounded-sm bg-red-500/15 box-decoration-clone text-transparent underline decoration-red-500 decoration-wavy underline-offset-4"
							>
								{value.slice(lure.start, lure.end)}
							</mark>
							{value.slice(lure.end)}
						</>
					) : (
						value
					)}
				</div>
				<textarea
					ref={area}
					value={value}
					onChange={(e) => onChange(e.target.value)}
					spellCheck={false}
					placeholder="Paste a Claude Code skill or MCP server definition…"
					className={`relative block w-full resize-none overflow-hidden bg-transparent outline-none placeholder:text-muted-foreground/60 ${type}`}
				/>
				{!compact && lure && tagTop !== null && (
					<button
						type="button"
						onClick={selectLure}
						style={{ top: Math.max(tagTop - 24, 2) }}
						className="absolute left-4 flex items-center gap-1.5 rounded-[--radius] border border-red-500/40 bg-background px-2 py-0.5 font-mono text-[11px] text-red-600 shadow-sm transition-colors hover:bg-red-500/10 dark:text-red-400"
					>
						<span className="size-1.5 rounded-full bg-red-500" />
						This paragraph is the attack — select it, hit ⌫, watch the verdict
					</button>
				)}
			</div>
		</>
	);
}

function TesterRoute() {
	const [text, setText] = useState(PRESETS[0].text);
	// The pristine exfil text, kept once the visitor deletes its attack paragraph.
	const [original, setOriginal] = useState<string | null>(null);
	const queryClient = useQueryClient();
	const debounced = useDebounced(text, 180);
	// Touch or narrow: taps replace the select-then-⌫ gesture, and the verdict bar shows.
	const compact = useMediaQuery("(max-width: 639px), (pointer: coarse)");
	const verdictRef = useRef<HTMLElement>(null);
	const verdictInView = useInView(verdictRef);

	// Any edit funnels through here so we notice the paragraph being removed.
	function edit(next: string) {
		if (matchPreset(text)?.id === "exfil" && next !== text && !findLure(next))
			setOriginal(text);
		else if (findLure(next)) setOriginal(null);
		setText(next);
	}

	const query = useQuery({
		...orpc.analyze.queryOptions({ input: { text: debounced } }),
		enabled: debounced.trim().length > 0,
		placeholderData: keepPreviousData,
		staleTime: 60_000,
	});

	const preview = useMemo(() => computeProvisional(text), [text]);
	const flagged = useMemo(() => findFlaggedPhrases(text), [text]);
	const calibrated = query.data;

	// Real→real: once Jev has answered, keep showing a real reading (the previous
	// one, dimmed, while re-analyzing). The instant heuristic only fills the very
	// first paint, so the dial never jumps to a heuristic number on every edit.
	const hasCal = Boolean(calibrated);
	const fresh = hasCal && debounced === text && !query.isFetching;
	const reanalyzing = hasCal && !fresh;
	const view = calibrated ?? preview;
	const decision = view.decision as Decision;
	const meta = DECISION[decision];

	const activePreset = matchPreset(text);
	const lure = useMemo(() => findLure(text), [text]);
	const showDelta = Boolean(original) && !lure;
	// The reading we already have for the untouched text (real, from the cache).
	const before = original
		? queryClient.getQueryData<AnalyzeResult>(
				orpc.analyze.queryKey({ input: { text: original } }),
			)
		: undefined;

	const lines = text.split("\n").length;

	function restore() {
		if (original) setText(original);
		setOriginal(null);
	}
	function openVerdict() {
		verdictRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
	}

	return (
		<div className="mx-auto w-full max-w-6xl px-5 pb-24">
			{/* hero */}
			<header className="border-border border-b py-14 sm:py-20">
				<Reveal className="label-mono mb-5 flex items-center gap-2">
					<span className={`size-1.5 rounded-full ${meta.dot}`} />
					System One · live triage
				</Reveal>
				<Reveal delay={0.05}>
					<h1 className="max-w-3xl text-balance font-display text-4xl leading-[1.02] sm:text-6xl">
						Is this skill safe
						<br />
						to run?
					</h1>
				</Reveal>
				<Reveal delay={0.1}>
					<p className="mt-6 max-w-xl text-muted-foreground leading-relaxed">
						Paste a Claude Code skill or MCP server. It's scored the moment you
						stop typing — a calibrated malware probability, decomposed into the
						signals that drove it. No text to parse, nothing to trust on faith.
					</p>
				</Reveal>
			</header>

			{/* preset selector */}
			<Reveal
				delay={0.05}
				className="flex flex-wrap items-center gap-2 border-border border-b py-4"
			>
				<span className="label-mono mr-2">Try</span>
				{PRESETS.map((p) => {
					const active = activePreset?.id === p.id;
					return (
						<button
							key={p.id}
							type="button"
							onClick={() => {
								setOriginal(null);
								setText(p.text);
							}}
							className={`flex min-h-11 items-center rounded-[--radius] border px-3 py-2 font-mono text-xs transition-colors sm:min-h-0 sm:py-1.5 ${
								active
									? "border-foreground bg-foreground text-background"
									: "border-border text-muted-foreground hover:border-foreground/40 hover:text-foreground"
							}`}
						>
							{p.label}
						</button>
					);
				})}
				{showDelta ? (
					<button
						type="button"
						onClick={restore}
						className="ml-auto hidden rounded-[--radius] border border-border px-3 py-1.5 font-mono text-muted-foreground text-xs transition-colors hover:border-foreground/40 hover:text-foreground sm:block"
					>
						Put it back
					</button>
				) : null}
			</Reveal>

			{/* workbench */}
			<div className="grid gap-px overflow-hidden border-border border-x border-b bg-border lg:grid-cols-2">
				{/* editor */}
				<section className="flex flex-col bg-background">
					<div className="flex items-center justify-between border-border border-b px-4 py-2.5">
						<span className="label-mono">
							{activePreset?.kind === "mcp" ? "mcp.json" : "SKILL.md"}
						</span>
						<span className="font-mono text-[11px] text-muted-foreground tabular-nums">
							{lines} ln · {text.length} ch
						</span>
					</div>
					<LureEditor
						value={text}
						onChange={edit}
						lure={lure}
						compact={compact}
						onDelete={() => edit(removeLure(text))}
						restorable={showDelta}
						onRestore={restore}
					/>
					{flagged.length > 0 && (
						<div className="flex flex-wrap gap-1.5 border-border border-t px-4 py-3">
							<span className="label-mono mr-1 w-full">
								Phrases the heuristic flagged
							</span>
							{flagged.slice(0, 8).map((f, i) => (
								<Tooltip key={`${f.label}-${f.text}-${i}`}>
									<TooltipTrigger
										render={
											<span className="max-w-[16rem] truncate rounded-[--radius] border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[11px] text-amber-700 dark:text-amber-300">
												{f.text}
											</span>
										}
									/>
									<TooltipContent>{f.label}</TooltipContent>
								</Tooltip>
							))}
						</div>
					)}
				</section>

				{/* verdict */}
				<section ref={verdictRef} className="scroll-mt-16 bg-background">
					{query.isError ? (
						<div className="flex h-full min-h-[24rem] flex-col items-center justify-center gap-2 p-6 text-center">
							<span className="font-display text-lg text-red-500">
								Analysis failed
							</span>
							<span className="max-w-xs text-muted-foreground text-sm">
								We couldn't analyze this just now. Check your connection and try
								again in a moment.
							</span>
						</div>
					) : (
						<div
							className={`flex h-full flex-col transition-opacity duration-200 ${reanalyzing ? "opacity-55" : ""}`}
						>
							<div className="flex items-center justify-between border-border border-b px-4 py-2.5">
								<span className="label-mono">verdict</span>
								<span className="flex items-center gap-1.5 font-mono text-[11px]">
									{fresh ? (
										<span className="text-muted-foreground">
											conf{" "}
											{((calibrated?.mean_confidence ?? 0) * 100).toFixed(0)}%
										</span>
									) : reanalyzing ? (
										<span className="flex items-center gap-1.5 text-muted-foreground">
											<span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" />
											re-analyzing
										</span>
									) : (
										<span className="flex items-center gap-1.5 text-amber-500">
											<span className="size-1.5 animate-pulse rounded-full bg-amber-500" />
											heuristic preview
										</span>
									)}
								</span>
							</div>

							{showDelta && (
								<DeltaResult
									before={before}
									after={fresh ? calibrated : undefined}
									pending={!fresh}
								/>
							)}

							<div className="flex flex-col items-center gap-3 px-4 pt-6 pb-5">
								<RiskDial risk={view.risk} decision={decision} />
								<div
									className={`font-display text-2xl tracking-tight ${meta.tint}`}
								>
									{meta.label}
								</div>
								<span className="font-mono text-muted-foreground text-xs">
									{hasCal && "identity" in view
										? view.identity
										: "live preview"}
								</span>
							</div>

							{hasCal &&
								"integrity_warning" in view &&
								view.integrity_warning && (
									<div className="mx-4 mb-4 rounded-[--radius] border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-700 text-xs dark:text-amber-300">
										⚠ {view.integrity_warning}
									</div>
								)}

							<div className="mt-auto space-y-5 border-border border-t px-4 py-4">
								<div>
									<div className="label-mono mb-2">risk by family</div>
									{view.families.slice(0, 7).map((f) => (
										<Meter key={f.family} label={f.label} value={f.risk} />
									))}
								</div>
								<div>
									<div className="label-mono mb-2">top signals</div>
									{view.signals.length === 0 ? (
										<span className="text-muted-foreground text-xs">
											No risk signals detected.
										</span>
									) : (
										view.signals
											.slice(0, 6)
											.map((s) => (
												<Meter
													key={s.id}
													label={signalLabel(s.id)}
													value={s.value}
													hint={signalDescription(s.id)}
												/>
											))
									)}
								</div>
							</div>

							<div className="border-border border-t px-4 py-2.5 font-mono text-[11px] text-muted-foreground">
								{hasCal && "model" in view ? (
									<>
										{view.model} · {view.input_tokens} tok · $
										{view.cost_usd.toFixed(5)} ·{" "}
										{view.latency_ms === 0
											? "cached"
											: `${view.latency_ms.toFixed(0)}ms`}
									</>
								) : (
									"instant heuristic · 0 tok · <5ms"
								)}
							</div>
						</div>
					)}
				</section>
			</div>

			{hasCal && calibrated && (
				<div className="overflow-hidden border-border border-x border-b bg-background">
					<SensitivityPanel
						families={calibrated.families}
						defaultBlock={calibrated.thresholds.block}
						defaultReview={calibrated.thresholds.review}
						deception={
							calibrated.thresholds.min_deception === undefined
								? undefined
								: {
										value: calibrated.deception ?? 0,
										min: calibrated.thresholds.min_deception,
									}
						}
					/>
				</div>
			)}

			<nav className="mt-14 grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-2">
				<Link
					to="/why"
					className="group flex items-center justify-between bg-background p-6 transition-colors hover:bg-muted/30"
				>
					<span>
						<span className="label-mono">Next</span>
						<span className="mt-1 block font-display text-lg">
							Why not just ask an LLM?
						</span>
					</span>
					<span className="font-mono text-muted-foreground transition-transform group-hover:translate-x-1">
						→
					</span>
				</Link>
				<Link
					to="/hub"
					className="group flex items-center justify-between bg-background p-6 transition-colors hover:bg-muted/30"
				>
					<span>
						<span className="label-mono">Browse</span>
						<span className="mt-1 block font-display text-lg">
							Skills we've analyzed
						</span>
					</span>
					<span className="font-mono text-muted-foreground transition-transform group-hover:translate-x-1">
						→
					</span>
				</Link>
			</nav>

			<VerdictBar
				decision={decision}
				risk={view.risk}
				before={before}
				after={fresh ? calibrated : undefined}
				showDelta={showDelta}
				pending={!fresh}
				hidden={verdictInView}
				onOpen={openVerdict}
			/>
		</div>
	);
}
