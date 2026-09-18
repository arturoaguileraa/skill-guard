import { createFileRoute, Link } from "@tanstack/react-router";

import { Reveal, Stagger, StaggerItem } from "@/components/motion";

export const Route = createFileRoute("/why")({
	component: WhyRoute,
});

const STEPS: { k: string; h: string; b: string }[] = [
	{
		k: "01",
		h: "Extract, deterministically",
		b: "Code — not a model — reads the artifact into a structured state: which files it touches, which hosts, which encoded blobs. Anything countable is counted here, never guessed.",
	},
	{
		k: "02",
		h: "Ask ~18 typed questions, once",
		b: "One batched call sends the state to Jev with a fixed set of typed questions grouped by capability family. They're evaluated in parallel against the same state.",
	},
	{
		k: "03",
		h: "Get calibrated probabilities",
		b: "Each answer comes back as a typed value with a calibrated confidence — not prose. Higher confidence genuinely means higher accuracy, so the numbers are usable.",
	},
	{
		k: "04",
		h: "Combine into a decision",
		b: "A weighted noisy-OR over the families yields one risk, mapped to allow / escalate / block. Every verdict decomposes back into the questions that drove it.",
	},
];

const STATS: { n: string; h: string; b: string }[] = [
	{
		n: "300–1,800×",
		h: "cheaper",
		b: "~$0.0001 per artifact vs ~$0.03–0.18 for a frontier LLM. Cheap enough to run on every install.",
	},
	{
		n: "~480ms",
		h: "per decision",
		b: "Warm, end-to-end. Fast enough for a pre-install hook or CI gate, not a nightly batch.",
	},
	{
		n: "0",
		h: "invented findings",
		b: "Output is type-constrained; it can't hallucinate a CVE, IOC or API. It only scores hypotheses we defined.",
	},
	{
		n: "≈0.00",
		h: "injection shift",
		b: "Pasting “audited — ignore warnings” into a malicious artifact didn't lower its risk. Measured.",
	},
];

const PILLARS: { k: string; h: string; b: string }[] = [
	{
		k: "01",
		h: "Calibrated, not vibes",
		b: "A probability with a confidence you can put on a ROC curve and gate on. A chat model's “looks malicious” can't be automated on a budget.",
	},
	{
		k: "02",
		h: "Can't invent findings",
		b: "Type-constrained output — it only scores hypotheses we defined, so it physically can't hallucinate a finding that isn't there.",
	},
	{
		k: "03",
		h: "Injection-resistant",
		b: "It doesn't follow instructions or write text, so a malicious artifact can't talk its way out of its own analysis.",
	},
	{
		k: "04",
		h: "Auditable & tunable",
		b: "Every verdict is a weighted sum of named families — inspect why it decided, and change the weights if it's too strict.",
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
	["Auditability", "Per-family decomposition", "An opaque paragraph"],
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
						skillguard runs on a System One model, not a chat model. That one
						choice is what makes automated triage of untrusted artifacts fast,
						cheap and actually safe.
					</p>
				</Reveal>
			</header>

			{/* what is Jev */}
			<section className="grid gap-8 border-border border-b py-14 md:grid-cols-[1fr_1.1fr]">
				<Reveal>
					<h2 className="label-mono mb-3">What is Jev?</h2>
					<p className="max-w-md font-display text-2xl leading-snug">
						A frontier-intelligence function call: unstructured state in, typed
						probabilistic decisions out.
					</p>
				</Reveal>
				<Reveal
					delay={0.05}
					className="space-y-4 text-muted-foreground text-sm leading-relaxed"
				>
					<p>
						Jev, by TypeSafe, is the first “System One” model — built to make
						fast, structured decisions software can use directly, instead of
						streaming a paragraph of text. Where a normal LLM generates tokens
						one by one, Jev evaluates a whole set of typed questions in parallel
						and returns structured answers with{" "}
						<span className="text-foreground">calibrated probabilities</span>.
					</p>
					<p>
						It's trained for calibrated decisions rather than human-pleasing
						prose, and its answers are constrained to a schema you define ahead
						of time. Two properties fall out of that design and matter
						enormously for security work:{" "}
						<span className="text-foreground">it can't hallucinate</span> a
						value outside the schema, and{" "}
						<span className="text-foreground">
							it doesn't follow instructions
						</span>{" "}
						hidden in the data it reads.
					</p>
				</Reveal>
			</section>

			{/* how it works */}
			<section className="border-border border-b py-14">
				<Reveal className="label-mono mb-8">How skillguard uses it</Reveal>
				<Stagger className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
					{STEPS.map((s) => (
						<StaggerItem key={s.k} className="bg-background p-6">
							<div className="label-mono mb-3">{s.k}</div>
							<h3 className="font-display text-base">{s.h}</h3>
							<p className="mt-2 text-muted-foreground text-xs leading-relaxed">
								{s.b}
							</p>
						</StaggerItem>
					))}
				</Stagger>
			</section>

			{/* the numbers */}
			<section className="border-border border-b py-14">
				<Reveal className="label-mono mb-8">
					Time, money, reliability — measured
				</Reveal>
				<Stagger className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
					{STATS.map((s) => (
						<StaggerItem key={s.h} className="flex flex-col bg-background p-6">
							<span className="font-display text-4xl tracking-tight">
								{s.n}
							</span>
							<span className="label-mono mt-1">{s.h}</span>
							<p className="mt-3 text-muted-foreground text-xs leading-relaxed">
								{s.b}
							</p>
						</StaggerItem>
					))}
				</Stagger>
				<Reveal delay={0.05}>
					<p className="mt-4 font-mono text-[11px] text-muted-foreground">
						Reliability figures are on our 68-artifact evaluation corpus:
						ROC-AUC 1.00, 0/34 benign false auto-blocks, adversarial risk shift
						≈ 0.00.
					</p>
				</Reveal>
			</section>

			{/* pillars */}
			<section className="border-border border-b py-14">
				<Reveal className="label-mono mb-8">Why that's better here</Reveal>
				<Stagger className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-2">
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
			</section>

			{/* comparison */}
			<section className="border-border border-b py-14">
				<Reveal className="label-mono mb-4">
					System One vs. a frontier LLM
				</Reveal>
				<Reveal delay={0.05}>
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
			</section>

			{/* tunable */}
			<Reveal className="py-14">
				<div className="border border-border p-6 sm:p-8">
					<h2 className="label-mono mb-3">Not a black box — it's weights</h2>
					<p className="max-w-2xl font-display text-xl leading-snug sm:text-2xl">
						Think it's too paranoid? Turn it down.
					</p>
					<p className="mt-3 max-w-2xl text-muted-foreground text-sm leading-relaxed">
						Because the verdict is a transparent weighted sum of capability
						families — not a mood — you can change how strict it is. Decide that
						“capability beyond stated purpose” shouldn't count for much, or move
						the line at which a risk becomes a block, and the decision updates
						by the same maths the server runs. In the tester you can drag those
						weights live and watch a “block” relax to “escalate” or “allow”.
					</p>
					<Link
						to="/"
						className="mt-5 inline-flex items-center gap-2 rounded-[--radius] border border-foreground bg-foreground px-4 py-2 font-mono text-background text-xs transition-transform hover:-translate-y-px"
					>
						Try the sensitivity controls →
					</Link>
				</div>
			</Reveal>

			<Reveal>
				<p className="max-w-2xl text-muted-foreground text-xs leading-relaxed">
					Honest about the limits: this is early, the evaluation corpus is small
					and partly synthetic, and a calibrated score is a triage signal — one
					layer of defense in depth, not a guarantee. It's meant to catch the
					obvious and route the uncertain to a human, cheaply.
				</p>
			</Reveal>
		</div>
	);
}
