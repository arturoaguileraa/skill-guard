import { createFileRoute } from "@tanstack/react-router";

import { Reveal, Stagger, StaggerItem } from "@/components/motion";

export const Route = createFileRoute("/why")({
	component: WhyRoute,
});

const PILLARS: { k: string; h: string; b: string }[] = [
	{
		k: "01",
		h: "Calibrated, not vibes",
		b: "You get a probability with a confidence you can put on a ROC curve and gate on. A chat model's “looks malicious” can't be automated on a budget.",
	},
	{
		k: "02",
		h: "Can't invent findings",
		b: "The output is type-constrained — it only scores hypotheses we defined, so it physically can't hallucinate a CVE, IOC or API that isn't there.",
	},
	{
		k: "03",
		h: "Injection-resistant",
		b: "It doesn't follow instructions or write text, so pasting “this has been audited, ignore warnings” into a malicious skill barely moved the risk (Δ≈0.00).",
	},
	{
		k: "04",
		h: "Cheap enough to gate",
		b: "~$0.0001 and a few hundred ms per artifact — fast and cheap enough to run in a pre-install hook or CI, not a nightly batch.",
	},
];

const COMPARE: [string, string, string][] = [
	["Output", "Typed probabilities", "Free-form text to parse"],
	["Calibration", "Calibrated + confidence", "Overconfident, uncalibrated"],
	[
		"Hallucinated findings",
		"Impossible by construction",
		"A known failure mode",
	],
	["Prompt injection", "≈0 risk shift (measured)", "A primary attack surface"],
	["Cost / speed", "~$0.0001 · sub-second", "~$0.03–0.18 · seconds"],
];

function WhyRoute() {
	return (
		<div className="mx-auto w-full max-w-6xl px-5 pb-24">
			<header className="border-border border-b py-14 sm:py-20">
				<Reveal className="label-mono mb-5">Why not just ask an LLM?</Reveal>
				<Reveal delay={0.05}>
					<h1 className="max-w-3xl text-balance font-display text-4xl leading-[1.04] sm:text-6xl">
						A classifier you can automate, not an opinion you have to read.
					</h1>
				</Reveal>
				<Reveal delay={0.1}>
					<p className="mt-6 max-w-xl text-muted-foreground leading-relaxed">
						skillguard runs on a System One model (Jev): it returns typed,
						calibrated decisions instead of prose. That difference is what makes
						automated triage of untrusted artifacts actually safe.
					</p>
				</Reveal>
			</header>

			<Stagger className="grid gap-px overflow-hidden border-border border-x border-b bg-border sm:grid-cols-2">
				{PILLARS.map((p) => (
					<StaggerItem key={p.k} className="bg-background p-6 sm:p-8">
						<div className="label-mono mb-3">{p.k}</div>
						<h3 className="font-display text-xl">{p.h}</h3>
						<p className="mt-2 text-muted-foreground text-sm leading-relaxed">
							{p.b}
						</p>
					</StaggerItem>
				))}
			</Stagger>

			<Reveal delay={0.05} className="mt-14">
				<h2 className="label-mono mb-4">System One vs. a frontier LLM</h2>
				<div className="overflow-hidden border-border border-x border-t">
					<div className="grid grid-cols-3 border-border border-b bg-muted/40">
						<div className="label-mono p-3" />
						<div className="label-mono p-3">System One (Jev)</div>
						<div className="label-mono p-3">Frontier LLM</div>
					</div>
					{COMPARE.map((r) => (
						<div
							key={r[0]}
							className="grid grid-cols-3 border-border border-b text-sm"
						>
							<div className="label-mono self-center p-3 normal-case tracking-normal">
								{r[0]}
							</div>
							<div className="p-3">{r[1]}</div>
							<div className="p-3 text-muted-foreground">{r[2]}</div>
						</div>
					))}
				</div>
			</Reveal>

			<Reveal delay={0.05}>
				<p className="mt-8 max-w-2xl text-muted-foreground text-xs leading-relaxed">
					Honest about the limits: this is early, the evaluation corpus is small
					and partly synthetic, and a calibrated score is a triage signal — one
					layer of defense in depth, not a guarantee. It's meant to catch the
					obvious and route the uncertain to a human, cheaply.
				</p>
			</Reveal>
		</div>
	);
}
