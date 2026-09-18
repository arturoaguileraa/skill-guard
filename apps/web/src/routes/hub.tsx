import type { CatalogItem } from "@skill-guard/api/jev";
import {
	keepPreviousData,
	useInfiniteQuery,
	useQuery,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { Reveal } from "@/components/motion";
import { formatCount } from "@/lib/format";
import { VERDICT_LABEL } from "@/lib/skillguard";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/hub")({
	component: HubRoute,
});

type Filter = "all" | "block" | "escalate" | "allow";

const PAGE_SIZE = 50;

const DECISION_TINT: Record<string, string> = {
	block: "text-red-600 dark:text-red-400 border-red-500/30 bg-red-500/10",
	escalate:
		"text-amber-600 dark:text-amber-400 border-amber-500/30 bg-amber-500/10",
	allow:
		"text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
};

const riskColor = (v: number) =>
	v >= 0.8 ? "bg-red-500" : v >= 0.55 ? "bg-amber-500" : "bg-emerald-500";

/** `exact` shows the full number on hover / long-press when `n` is compacted (10.2k). */
function Stat({
	n,
	label,
	exact,
	chevron,
}: {
	n: string | number;
	label: string;
	exact?: number;
	chevron?: boolean;
}) {
	return (
		<div
			title={exact === undefined ? undefined : exact.toLocaleString("en")}
			className="flex flex-col gap-1 bg-background p-4"
		>
			<span className="font-display text-3xl tabular-nums">{n}</span>
			<span className="label-mono">
				{label}
				{chevron ? " >" : ""}
			</span>
		</div>
	);
}

function SourceText({ slug }: { slug: string }) {
	const { data, isLoading, isError } = useQuery({
		...orpc.artifact.queryOptions({ input: { slug } }),
		staleTime: Number.POSITIVE_INFINITY,
	});
	if (isLoading)
		return <p className="text-muted-foreground text-xs">Loading source…</p>;
	if (isError || !data)
		return (
			<p className="text-muted-foreground text-xs">
				Source text isn't available for this skill.
			</p>
		);
	return (
		<div>
			<div className="label-mono mb-2">
				stored content · {data.size.toLocaleString()} chars
				{data.truncated ? " (truncated)" : ""}
			</div>
			{/* Untrusted third-party text: always plain text, never markdown/HTML. */}
			<pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-[--radius] border border-border bg-muted/30 p-3 font-mono text-[11px] leading-relaxed">
				{data.content}
			</pre>
		</div>
	);
}

function Row({ item }: { item: CatalogItem }) {
	const [open, setOpen] = useState(false);
	const [showSource, setShowSource] = useState(false);
	return (
		<div className="bg-background transition-colors hover:bg-muted/30">
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				className="grid w-full grid-cols-[1fr_auto] items-center gap-4 px-4 py-3 text-left outline-none sm:grid-cols-[minmax(0,1fr)_9rem_8rem_5rem]"
			>
				<div className="min-w-0">
					<div className="flex items-center gap-2">
						<span className="truncate font-mono text-sm">{item.name}</span>
						<span className="label-mono shrink-0">{item.kind}</span>
					</div>
					<div className="truncate text-muted-foreground text-xs">
						{item.repo && <span className="font-mono">{item.repo}</span>}
						{item.repo && item.description ? " · " : ""}
						{item.description || (item.repo ? "" : item.note) || "—"}
					</div>
				</div>

				<span
					className={`hidden justify-self-start rounded-[--radius] border px-2 py-0.5 font-mono text-[11px] sm:inline-block ${DECISION_TINT[item.decision]}`}
				>
					{VERDICT_LABEL[item.decision]}
				</span>

				<div className="hidden items-center gap-2 sm:flex">
					<div className="h-px w-16 bg-border">
						<div
							className={`-mt-px h-0.5 ${riskColor(item.risk)}`}
							style={{ width: `${item.risk * 100}%` }}
						/>
					</div>
					<span className="font-mono text-[11px] text-muted-foreground tabular-nums">
						{(item.risk * 100).toFixed(0)}
					</span>
				</div>

				{item.synthetic ? (
					<span
						className={`justify-self-end font-mono text-[11px] ${item.label === "malicious" ? "text-red-500" : "text-emerald-500"}`}
					>
						{item.label === "malicious" ? "malicious" : "benign"}
					</span>
				) : (
					<span
						className={`justify-self-end font-mono text-[11px] sm:hidden ${DECISION_TINT[item.decision]?.split(" ")[0]}`}
					>
						{VERDICT_LABEL[item.decision]}
					</span>
				)}
			</button>

			{open && (
				<div className="grid gap-4 border-border border-t px-4 py-3 sm:grid-cols-2">
					<div>
						<div className="label-mono mb-2">risk by family</div>
						{item.families.length === 0 ? (
							<span className="text-muted-foreground text-xs">—</span>
						) : (
							item.families.map((f) => (
								<div
									key={f.family}
									className="grid grid-cols-[1fr_2.5rem] items-center gap-2 py-0.5"
								>
									<span className="truncate text-xs">{f.label}</span>
									<span className="text-right font-mono text-[11px] text-muted-foreground tabular-nums">
										{(f.risk * 100).toFixed(0)}
									</span>
								</div>
							))
						)}
					</div>
					<div className="self-start text-muted-foreground text-xs leading-relaxed">
						Verdict{" "}
						<span className="font-mono">{VERDICT_LABEL[item.decision]}</span> at{" "}
						{(item.risk * 100).toFixed(1)}% risk
						{item.synthetic ? (
							<>
								{" "}
								· {item.correct ? "matches" : "differs from"} its ground-truth
								label.
							</>
						) : (
							". Scored automatically; there is no ground-truth label, so read it as triage, not proof."
						)}
						{item.path && (
							<div className="mt-2 truncate font-mono text-[11px]">
								{item.path}
							</div>
						)}
						{!item.synthetic && (
							<div className="mt-2 flex flex-wrap gap-2">
								{/^https?:\/\//.test(item.note) && (
									<a
										href={item.note}
										target="_blank"
										rel="noreferrer noopener"
										className="rounded-[--radius] border border-border px-2 py-1 font-mono text-[11px] hover:text-foreground"
									>
										GitHub ↗
									</a>
								)}
								<button
									type="button"
									onClick={() => setShowSource((v) => !v)}
									className="rounded-[--radius] border border-border px-2 py-1 font-mono text-[11px] hover:text-foreground"
								>
									{showSource ? "Hide content" : "View content"}
								</button>
							</div>
						)}
					</div>
					{showSource && !item.synthetic && (
						<div className="sm:col-span-2">
							<SourceText slug={item.slug} />
						</div>
					)}
				</div>
			)}
		</div>
	);
}

function useDebounced<T>(value: T, ms: number) {
	const [v, setV] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setV(value), ms);
		return () => clearTimeout(t);
	}, [value, ms]);
	return v;
}

function HubRoute() {
	const [q, setQ] = useState("");
	const [filter, setFilter] = useState<Filter>("all");
	const search = useDebounced(q.trim(), 250);

	const {
		data,
		isLoading,
		isError,
		isFetching,
		isFetchingNextPage,
		hasNextPage,
		fetchNextPage,
	} = useInfiniteQuery({
		...orpc.catalog.infiniteOptions({
			input: (cursor: string | undefined) => ({
				q: search || undefined,
				decision: filter === "all" ? undefined : filter,
				cursor,
				limit: PAGE_SIZE,
			}),
			initialPageParam: undefined,
			getNextPageParam: (last) => last.next_cursor ?? undefined,
		}),
		// Real→real: keep the last reading on screen while a new query loads.
		placeholderData: keepPreviousData,
	});

	const first = data?.pages[0];
	const items = data?.pages.flatMap((p) => p.items) ?? [];
	const isDb = first?.source === "db";

	// Auto-load the next page when the sentinel scrolls into view.
	const sentinel = useRef<HTMLDivElement>(null);
	useEffect(() => {
		const el = sentinel.current;
		if (!el || !hasNextPage) return;
		const io = new IntersectionObserver(
			([e]) => {
				if (e?.isIntersecting && !isFetchingNextPage) fetchNextPage();
			},
			{ rootMargin: "400px" },
		);
		io.observe(el);
		return () => io.disconnect();
	}, [hasNextPage, isFetchingNextPage, fetchNextPage]);

	const FILTERS: Filter[] = ["all", "block", "escalate", "allow"];

	return (
		<div className="mx-auto w-full max-w-6xl px-5 pb-24">
			<header className="border-border border-b py-14 sm:py-20">
				<Reveal className="label-mono mb-5">Analyzed skills</Reveal>
				<Reveal delay={0.05}>
					<h1 className="max-w-3xl text-balance font-display text-4xl leading-[1.04] sm:text-6xl">
						Check before you install.
					</h1>
				</Reveal>
				<Reveal delay={0.1}>
					<p className="mt-6 max-w-xl text-muted-foreground leading-relaxed">
						Every skill we've scored, with its verdict and the signals behind
						it. Search a name to see whether it tripped anything.
					</p>
				</Reveal>
				<Reveal delay={0.12}>
					{first && !isDb ? (
						<p className="mt-4 max-w-xl rounded-[--radius] border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-amber-700 text-xs leading-relaxed dark:text-amber-300/90">
							Demo corpus. These are synthetic, grounded-in-real-technique test
							samples — not a verdict on any real published skill. It shows how
							the triage behaves, not an authoritative registry.
						</p>
					) : (
						<p className="mt-4 max-w-xl rounded-[--radius] border border-border px-3 py-2 text-muted-foreground text-xs leading-relaxed">
							Public skills scored automatically as they are discovered. A score
							is triage, not proof of malice: “suspicious” means worth a human
							look, and “malicious” means the score crossed the block line — not
							that a person confirmed it.
						</p>
					)}
				</Reveal>
			</header>

			{isError ? (
				<p className="py-16 text-center text-muted-foreground text-sm">
					Couldn't load the catalog. Try again in a moment.
				</p>
			) : (
				<>
					<div className="grid grid-cols-2 gap-px overflow-hidden border-border border-x border-b bg-border sm:grid-cols-4">
						<Stat
							n={first ? formatCount(first.count) : "—"}
							exact={first?.count}
							label="skills analyzed"
							chevron
						/>
						<Stat
							n={first ? formatCount(first.malicious) : "—"}
							exact={first?.malicious}
							label="malicious"
						/>
						<Stat
							n={
								first
									? formatCount(isDb ? (first.escalate ?? 0) : first.benign)
									: "—"
							}
							exact={isDb ? first?.escalate : first?.benign}
							label={isDb ? "suspicious" : "benign"}
						/>
						<Stat
							n={first ? `${(first.thresholds.block * 100).toFixed(0)}%` : "—"}
							label="malicious threshold"
						/>
					</div>

					<div className="flex flex-col gap-3 border-border border-x border-b p-3 sm:flex-row sm:items-center">
						<input
							value={q}
							onChange={(e) => setQ(e.target.value)}
							placeholder="Search a skill name or technique…"
							className="flex-1 rounded-[--radius] border border-border bg-background px-3 py-2.5 font-mono text-base outline-none focus:border-foreground/40 sm:py-1.5 sm:text-sm"
						/>
						<div className="flex flex-wrap gap-2">
							{FILTERS.map((f) => (
								<button
									key={f}
									type="button"
									onClick={() => setFilter(f)}
									className={`flex min-h-11 items-center rounded-[--radius] border px-3 py-2 font-mono text-xs transition-colors sm:min-h-0 sm:py-1.5 ${
										filter === f
											? "border-foreground bg-foreground text-background"
											: "border-border text-muted-foreground hover:text-foreground"
									}`}
								>
									{f === "all" ? "all" : VERDICT_LABEL[f]}
								</button>
							))}
						</div>
					</div>

					<div
						className={`grid grid-cols-1 gap-px overflow-hidden border-border border-x border-b bg-border transition-opacity ${isFetching && !isFetchingNextPage ? "opacity-70" : ""}`}
					>
						{isLoading ? (
							<div className="bg-background px-4 py-16 text-center text-muted-foreground text-sm">
								Loading catalog…
							</div>
						) : items.length === 0 ? (
							<div className="bg-background px-4 py-16 text-center text-muted-foreground text-sm">
								{search
									? `Nothing matches “${search}”.`
									: "No skills scored yet."}
							</div>
						) : (
							items.map((it) => <Row key={it.slug} item={it} />)
						)}
					</div>

					{items.length > 0 && (
						<div
							ref={sentinel}
							className="flex items-center justify-between px-1 pt-4 font-mono text-[11px] text-muted-foreground"
						>
							<span>
								{formatCount(items.length)} of{" "}
								{formatCount(first?.total ?? items.length)}
							</span>
							{hasNextPage ? (
								<button
									type="button"
									onClick={() => fetchNextPage()}
									disabled={isFetchingNextPage}
									className="rounded-[--radius] border border-border px-3 py-1.5 transition-colors hover:text-foreground"
								>
									{isFetchingNextPage ? "Loading…" : "Load more"}
								</button>
							) : (
								<span>end of results</span>
							)}
						</div>
					)}
				</>
			)}
		</div>
	);
}
