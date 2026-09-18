import type { CatalogItem } from "@jev-analysis/api/jev";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";

import { Reveal } from "@/components/motion";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/hub")({
	component: HubRoute,
});

type Filter = "all" | "malicious" | "benign";

const DECISION_TINT: Record<string, string> = {
	block: "text-red-600 dark:text-red-400 border-red-500/30 bg-red-500/10",
	escalate:
		"text-amber-600 dark:text-amber-400 border-amber-500/30 bg-amber-500/10",
	allow:
		"text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
};

const riskColor = (v: number) =>
	v >= 0.8 ? "bg-red-500" : v >= 0.35 ? "bg-amber-500" : "bg-emerald-500";

function Stat({ n, label }: { n: string | number; label: string }) {
	return (
		<div className="flex flex-col gap-1 bg-background p-4">
			<span className="font-display text-3xl tabular-nums">{n}</span>
			<span className="label-mono">{label}</span>
		</div>
	);
}

function Row({ item }: { item: CatalogItem }) {
	const [open, setOpen] = useState(false);
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
						{item.note || "—"}
					</div>
				</div>

				<span
					className={`hidden justify-self-start rounded-[--radius] border px-2 py-0.5 font-mono text-[11px] sm:inline-block ${DECISION_TINT[item.decision]}`}
				>
					{item.decision}
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

				<span
					className={`justify-self-end font-mono text-[11px] ${item.label === "malicious" ? "text-red-500" : "text-emerald-500"}`}
				>
					{item.label === "malicious" ? "malware" : "clean"}
				</span>
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
						Verdict <span className="font-mono">{item.decision}</span> at{" "}
						{(item.risk * 100).toFixed(1)}% risk ·{" "}
						{item.correct ? "matches" : "differs from"} its ground-truth label.
					</div>
				</div>
			)}
		</div>
	);
}

function HubRoute() {
	const { data, isLoading, isError } = useQuery(orpc.catalog.queryOptions());
	const [q, setQ] = useState("");
	const [filter, setFilter] = useState<Filter>("all");

	const items = useMemo(() => {
		const all = data?.items ?? [];
		const needle = q.trim().toLowerCase();
		return all.filter((it) => {
			if (filter !== "all" && it.label !== filter) return false;
			if (!needle) return true;
			return (
				it.name.toLowerCase().includes(needle) ||
				it.note.toLowerCase().includes(needle)
			);
		});
	}, [data, q, filter]);

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
						Every artifact we've scored, with its verdict and the signals behind
						it. Search a name to see whether it tripped anything.
					</p>
				</Reveal>
				<Reveal delay={0.12}>
					<p className="mt-4 max-w-xl rounded-[--radius] border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-amber-700 text-xs leading-relaxed dark:text-amber-300/90">
						Demo corpus. These are synthetic, grounded-in-real-technique test
						artifacts — not a verdict on any real published skill. It shows how
						the triage behaves, not an authoritative registry.
					</p>
				</Reveal>
			</header>

			{isError ? (
				<p className="py-16 text-center text-muted-foreground text-sm">
					Couldn't load the catalog. Is the Jev service on :8000?
				</p>
			) : (
				<>
					<div className="grid grid-cols-2 gap-px overflow-hidden border-border border-x border-b bg-border sm:grid-cols-4">
						<Stat n={data?.count ?? "—"} label="artifacts" />
						<Stat n={data?.malicious ?? "—"} label="malicious" />
						<Stat n={data?.benign ?? "—"} label="benign" />
						<Stat
							n={data ? `${(data.thresholds.block * 100).toFixed(0)}%` : "—"}
							label="block threshold"
						/>
					</div>

					<div className="flex flex-col gap-3 border-border border-x border-b p-3 sm:flex-row sm:items-center">
						<input
							value={q}
							onChange={(e) => setQ(e.target.value)}
							placeholder="Search a skill name or technique…"
							className="flex-1 rounded-[--radius] border border-border bg-background px-3 py-1.5 font-mono text-sm outline-none focus:border-foreground/40"
						/>
						<div className="flex gap-2">
							{(["all", "malicious", "benign"] as Filter[]).map((f) => (
								<button
									key={f}
									type="button"
									onClick={() => setFilter(f)}
									className={`rounded-[--radius] border px-3 py-1.5 font-mono text-xs transition-colors ${
										filter === f
											? "border-foreground bg-foreground text-background"
											: "border-border text-muted-foreground hover:text-foreground"
									}`}
								>
									{f}
								</button>
							))}
						</div>
					</div>

					<div className="grid grid-cols-1 gap-px overflow-hidden border-border border-x border-b bg-border">
						{isLoading ? (
							<div className="bg-background px-4 py-16 text-center text-muted-foreground text-sm">
								Loading catalog…
							</div>
						) : items.length === 0 ? (
							<div className="bg-background px-4 py-16 text-center text-muted-foreground text-sm">
								Nothing matches “{q}”.
							</div>
						) : (
							items.map((it) => <Row key={it.slug} item={it} />)
						)}
					</div>
				</>
			)}
		</div>
	);
}
