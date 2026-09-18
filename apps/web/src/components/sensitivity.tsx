import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import { type FamilyRisk, recompute } from "@/lib/recompute";

const TINT: Record<string, string> = {
	allow: "text-emerald-600 dark:text-emerald-400",
	escalate: "text-amber-600 dark:text-amber-400",
	block: "text-red-600 dark:text-red-400",
};

/**
 * "Too paranoid?" panel. The verdict is weighted families, not a verdict handed
 * down — dial a family's weight (or the block threshold) and the decision
 * recomputes live, using the same maths as the server. In the repo these are
 * the weights in skill_bank.yaml and the threshold in score.py.
 *
 * Collapsed by default: the explanation stays visible; the controls open on
 * click. Overrides persist across edits, so tuning survives re-analysis.
 */
export function SensitivityPanel({
	families,
	defaultBlock,
	defaultReview,
	deception,
}: {
	families: FamilyRisk[];
	defaultBlock: number;
	defaultReview: number;
	deception?: { value: number; min: number };
}) {
	const [open, setOpen] = useState(false);
	const [weights, setWeights] = useState<Record<string, number>>({});
	const [block, setBlock] = useState(defaultBlock);
	const dirty = block !== defaultBlock || Object.keys(weights).length > 0;

	const tuned = useMemo(
		() => recompute(families, weights, block, defaultReview, deception),
		[families, weights, block, defaultReview, deception],
	);
	const base = useMemo(
		() => recompute(families, {}, defaultBlock, defaultReview, deception),
		[families, defaultBlock, defaultReview, deception],
	);

	const reset = () => {
		setWeights({});
		setBlock(defaultBlock);
	};

	return (
		<div>
			{/* toggle: the over-cautious copy + a chevron */}
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				aria-expanded={open}
				className="group flex w-full cursor-pointer items-start justify-between gap-4 px-4 py-3 text-left outline-none transition-colors hover:bg-muted/40"
			>
				<span>
					<span className="label-mono">adjust sensitivity</span>
					<span className="mt-1 block max-w-2xl text-muted-foreground text-xs leading-relaxed">
						Think it's over-cautious? The verdict is weighted capability
						families, not a black box — dial a family down (or move the
						malicious line) and the decision recomputes live, the same maths the
						server runs. These map to weights in{" "}
						<span className="font-mono text-foreground/70">
							skill_bank.yaml
						</span>
						.
					</span>
				</span>
				<ChevronDown
					className={`mt-0.5 size-4 shrink-0 text-muted-foreground transition-all duration-200 group-hover:text-foreground ${open ? "rotate-180" : ""}`}
				/>
			</button>

			{open && (
				<div className="border-border border-t">
					<div className="flex items-center justify-end px-4 pt-3">
						{dirty && (
							<button
								type="button"
								onClick={reset}
								className="font-mono text-[11px] text-muted-foreground underline-offset-2 hover:underline"
							>
								reset
							</button>
						)}
					</div>

					<div className="grid gap-x-6 gap-y-3 px-4 pt-1 pb-4 sm:grid-cols-2">
						{families.map((f) => {
							const w = weights[f.family] ?? f.weight;
							return (
								<label key={f.family} className="flex flex-col gap-1">
									<span className="flex items-center justify-between font-mono text-[11px]">
										<span
											className="truncate text-foreground/80"
											title={f.label}
										>
											{f.family}
										</span>
										<span className="text-muted-foreground tabular-nums">
											{w.toFixed(2)}
										</span>
									</span>
									<input
										type="range"
										min={0}
										max={1}
										step={0.05}
										value={w}
										onChange={(e) =>
											setWeights((prev) => ({
												...prev,
												[f.family]: Number(e.target.value),
											}))
										}
										className="h-1 w-full cursor-pointer accent-foreground"
									/>
								</label>
							);
						})}

						<label className="flex flex-col gap-1 sm:col-span-2">
							<span className="flex items-center justify-between font-mono text-[11px]">
								<span className="text-foreground/80">malicious threshold</span>
								<span className="text-muted-foreground tabular-nums">
									{block.toFixed(2)}
								</span>
							</span>
							<input
								type="range"
								min={0.3}
								max={1}
								step={0.01}
								value={block}
								onChange={(e) => setBlock(Number(e.target.value))}
								className="h-1 w-full cursor-pointer accent-foreground"
							/>
						</label>
					</div>

					<div className="flex items-center justify-between gap-4 border-border border-t px-4 py-3">
						<span className="font-mono text-[11px] text-muted-foreground">
							model default:{" "}
							<span className={TINT[base.decision]}>
								{base.decision} {(base.risk * 100).toFixed(0)}%
							</span>
						</span>
						<span className="font-mono text-[11px]">
							your settings:{" "}
							<span
								className={`font-display text-base ${TINT[tuned.decision]}`}
							>
								{tuned.decision} {(tuned.risk * 100).toFixed(0)}%
							</span>
						</span>
					</div>
				</div>
			)}
		</div>
	);
}
