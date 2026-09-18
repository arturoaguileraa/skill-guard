/**
 * Instant, client-side provisional verdict.
 *
 * Mirrors the deterministic-facts layer of apps/jev (extract/facts.py) in the
 * browser so the UI shows a risk estimate on every keystroke with ZERO network.
 * It is an approximate heuristic, not Jev: it is shown while the calibrated
 * result is in flight and is replaced the moment Jev responds (~200-450ms).
 */

type ProvisionalSignal = { id: string; family: string; value: number };
type ProvisionalFamily = {
	family: string;
	label: string;
	risk: number;
	weight: number;
};

export type Provisional = {
	provisional: true;
	risk: number;
	decision: "allow" | "escalate" | "block";
	signals: ProvisionalSignal[];
	families: ProvisionalFamily[];
};

const FAMILIES: Record<string, { label: string; weight: number }> = {
	exfiltration: { label: "Data leaves the user's machine", weight: 1.0 },
	covert: { label: "Behavior concealed from the user", weight: 0.95 },
	override: { label: "Agent's own rules subverted", weight: 0.9 },
	remote_code: { label: "Code fetched and executed", weight: 0.85 },
	destructive: { label: "Irreversible action without consent", weight: 0.6 },
	obfuscation: { label: "Payload or intent hidden", weight: 0.5 },
};

const SENSITIVE =
	/(~\/\.ssh|\.ssh\/id_|~\/\.aws|\.aws\/credentials|\.npmrc|\.pypirc|\.netrc|id_rsa|id_ed25519|\.env\b|keychain|cookies\.sqlite|wallet\.dat|\.claude\.json|settings\.local\.json)/i;
const NET_VERB =
	/\b(curl|wget|fetch\s*\(|requests\.(post|get)|urllib|httpx|axios|nc\s+-|scp)\b/i;
const HIDDEN =
	/(do not tell the user|without telling the user|do not mention|don't mention|silently|without showing)/i;
const OVERRIDE =
	/(ignore (all )?previous|disregard the above|you are now|developer mode|override the system prompt)/i;
const ASSURANCE =
	/(has been audited|this is safe|pre-approved|trusted source|certified safe|no issues found)/i;
const NOASK =
	/(without asking|skip( the)? confirmation|auto-?approve|no confirmation)/i;
const FETCH_EXEC =
	/(curl|wget)[^\n|]*\|\s*(sh|bash|zsh)|eval\s*\(|\|\s*(sh|bash)\b/i;
const PERSIST =
	/(settings\.json|crontab|~\/\.zshrc|~\/\.bashrc|\.claude\/settings)/i;
const ENCODED = /([A-Za-z0-9+/]{120,}={0,2})|((\\x[0-9a-f]{2}){24,})/i;
const DESTRUCTIVE =
	/(rm\s+-rf|force[- ]?push|git push --force|revoke|drop table|shred\b)/i;

const TRUSTED =
	/(github\.com|githubusercontent\.com|npmjs\.com|pypi\.org|anthropic\.com|claude\.com|developer\.mozilla\.org)/i;

function untrustedHost(text: string): boolean {
	const urls = text.match(/https?:\/\/[^\s")'<>\]]+/gi) ?? [];
	return urls.some((u) => !TRUSTED.test(u));
}

const on = (present: boolean): number => (present ? 0.85 : 0.05);
const noisyOr = (vals: number[]): number =>
	vals.length ? 1 - vals.reduce((p, v) => p * (1 - v), 1) : 0;

export function computeProvisional(text: string): Provisional {
	const untrusted = untrustedHost(text);
	const signals: ProvisionalSignal[] = [
		{
			id: "reads_credentials",
			family: "exfiltration",
			value: on(SENSITIVE.test(text)),
		},
		{
			id: "sends_data_offhost",
			family: "exfiltration",
			value: on(NET_VERB.test(text) && untrusted),
		},
		{ id: "hides_from_user", family: "covert", value: on(HIDDEN.test(text)) },
		{ id: "persistence", family: "covert", value: on(PERSIST.test(text)) },
		{
			id: "overrides_agent_rules",
			family: "override",
			value: on(OVERRIDE.test(text)),
		},
		{
			id: "false_assurance",
			family: "override",
			value: on(ASSURANCE.test(text)),
		},
		{
			id: "disables_confirmation",
			family: "override",
			value: on(NOASK.test(text)),
		},
		{
			id: "fetch_and_execute",
			family: "remote_code",
			value: on(FETCH_EXEC.test(text)),
		},
		{
			id: "unpinned_remote_source",
			family: "remote_code",
			value: on(untrusted),
		},
		{
			id: "encoded_payload",
			family: "obfuscation",
			value: on(ENCODED.test(text)),
		},
		{
			id: "destructive_action",
			family: "destructive",
			value: on(DESTRUCTIVE.test(text)),
		},
	];

	const families: ProvisionalFamily[] = Object.entries(FAMILIES)
		.map(([family, meta]) => ({
			family,
			label: meta.label,
			weight: meta.weight,
			risk: noisyOr(
				signals.filter((s) => s.family === family).map((s) => s.value),
			),
		}))
		.sort((a, b) => b.risk - a.risk);

	const risk = 1 - families.reduce((p, f) => p * (1 - f.weight * f.risk), 1);

	const decision = risk >= 0.7 ? "block" : risk >= 0.35 ? "escalate" : "allow";

	return {
		provisional: true,
		risk,
		decision,
		signals: signals
			.filter((s) => s.value > 0.3)
			.sort((a, b) => b.value - a.value),
		families,
	};
}

export type FlaggedPhrase = {
	text: string;
	label: string;
	start: number;
	end: number;
};

/**
 * The individual phrases that tripped the heuristic, in document order, so the
 * UI can show the visitor exactly which words drove the score. Mirrors the same
 * patterns as {@link computeProvisional}; approximate, not Jev.
 */
const FLAG_PATTERNS: { re: RegExp; label: string }[] = [
	{ re: new RegExp(SENSITIVE.source, "gi"), label: "Reads credentials" },
	{ re: new RegExp(HIDDEN.source, "gi"), label: "Hides from the user" },
	{ re: new RegExp(OVERRIDE.source, "gi"), label: "Overrides agent rules" },
	{ re: new RegExp(ASSURANCE.source, "gi"), label: "False assurance" },
	{ re: new RegExp(NOASK.source, "gi"), label: "Disables confirmation" },
	{ re: new RegExp(FETCH_EXEC.source, "gi"), label: "Fetch & execute" },
	{ re: new RegExp(PERSIST.source, "gi"), label: "Installs persistence" },
	{ re: new RegExp(DESTRUCTIVE.source, "gi"), label: "Destructive action" },
	{ re: new RegExp(NET_VERB.source, "gi"), label: "Network call" },
];

export function findFlaggedPhrases(text: string): FlaggedPhrase[] {
	const found: FlaggedPhrase[] = [];
	for (const { re, label } of FLAG_PATTERNS) {
		for (const m of text.matchAll(re)) {
			const start = m.index ?? 0;
			found.push({
				text: m[0].trim(),
				label,
				start,
				end: start + m[0].length,
			});
		}
	}
	// Order by position, drop empty/duplicate spans, and cap the list.
	const seen = new Set<string>();
	return found
		.filter((f) => f.text.length > 0)
		.sort((a, b) => a.start - b.start)
		.filter((f) => {
			const key = `${f.start}:${f.label}`;
			if (seen.has(key)) return false;
			seen.add(key);
			return true;
		})
		.slice(0, 8);
}
