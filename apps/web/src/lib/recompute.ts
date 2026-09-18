/**
 * Client-side "what-if" re-scoring. The analyze response already carries each
 * family's risk (independent of its weight) plus the real weights and
 * thresholds, so we can recompute the overall verdict under user-adjusted
 * weights with the SAME cross-family formula score.py uses — no black box, no
 * extra Jev call. This powers the "adjust sensitivity" panel.
 */

export type FamilyRisk = {
	family: string;
	label: string;
	risk: number;
	weight: number;
};

export type Decision = "allow" | "escalate" | "block";

export function recompute(
	families: FamilyRisk[],
	weights: Record<string, number>,
	block: number,
	review: number,
	// Same gate as score.py: "malicious" needs evidence of deception; a high
	// risk from capability alone stays "suspicious". Weights do not change it.
	deception?: { value: number; min: number },
): { risk: number; decision: Decision } {
	// risk = 1 - Π(1 - weight_f · familyRisk_f)   (weighted noisy-OR)
	const risk =
		1 -
		families.reduce(
			(p, f) => p * (1 - (weights[f.family] ?? f.weight) * f.risk),
			1,
		);
	const capabilityOnly = deception ? deception.value < deception.min : false;
	const decision: Decision =
		risk >= block
			? capabilityOnly
				? "escalate"
				: "block"
			: risk >= review
				? "escalate"
				: "allow";
	return { risk, decision };
}
