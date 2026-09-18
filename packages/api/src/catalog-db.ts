import { neon } from "@neondatabase/serverless";

import type { Catalog, CatalogInput } from "./jev";

/**
 * Catalog read path backed by Postgres (Neon). Provider-neutral: it only needs
 * DATABASE_URL, the same variable the worker writes with. Reads are paginated
 * with a keyset cursor over (risk desc, artifact_hash desc) so deep pages stay
 * as cheap as the first.
 */
type Sql = ReturnType<typeof neon>;
let cached: { url: string; sql: Sql } | null = null;

export const hasDatabase = () => Boolean(process.env.DATABASE_URL);

function client(): Sql {
	const url = process.env.DATABASE_URL;
	if (!url) throw new Error("DATABASE_URL is not set");
	// Lazy + keyed on the URL: safe at build time, no module-level side effects.
	if (!cached || cached.url !== url) cached = { url, sql: neon(url) };
	return cached.sql;
}

const THRESHOLDS = { block: 0.8, review: 0.35 } as const;

const escapeLike = (s: string) => s.replace(/[\\%_]/g, "\\$&");

type Row = Record<string, unknown>;

export async function catalogFromDb(input: CatalogInput): Promise<Catalog> {
	const sql = client();
	const limit = input.limit;

	const filters: string[] = [];
	const params: unknown[] = [];
	const bind = (v: unknown) => {
		params.push(v);
		return `$${params.length}`;
	};

	const q = input.q?.trim();
	if (q) {
		const p = bind(`%${escapeLike(q)}%`);
		filters.push(`(a.identity ILIKE ${p} OR a.source_url ILIKE ${p})`);
	}
	if (input.decision) filters.push(`r.decision = ${bind(input.decision)}`);
	const where = filters.length ? `WHERE ${filters.join(" AND ")}` : "";

	// Total for the current filters, before the cursor is applied.
	const totalParams = [...params];

	const pageFilters = [...filters];
	if (input.cursor) {
		const [risk, hash] = input.cursor.split("|");
		const rp = bind(Number(risk));
		const hp = bind(hash ?? "");
		pageFilters.push(`(r.risk, r.artifact_hash) < (${rp}::float8, ${hp})`);
	}
	const pageWhere = pageFilters.length
		? `WHERE ${pageFilters.join(" AND ")}`
		: "";

	const from = "FROM results r JOIN artifacts a ON a.hash = r.artifact_hash";

	const [rows, totalRows, statRows] = await Promise.all([
		sql.query(
			`SELECT r.artifact_hash, r.risk, r.decision, r.families, r.signals,
				r.model, a.identity, a.kind, a.source, a.source_url
			${from} ${pageWhere}
			ORDER BY r.risk DESC, r.artifact_hash DESC
			LIMIT ${limit + 1}`,
			params,
		) as Promise<Row[]>,
		sql.query(
			`SELECT count(*)::int AS n ${from} ${where}`,
			totalParams,
		) as Promise<Row[]>,
		sql.query(
			`SELECT decision, count(*)::int AS n, max(scored_at) AS last
			FROM results GROUP BY decision`,
		) as Promise<Row[]>,
	]);

	const hasMore = rows.length > limit;
	const page = hasMore ? rows.slice(0, limit) : rows;
	const last = page.at(-1);

	const byDecision = Object.fromEntries(
		statRows.map((r) => [String(r.decision), Number(r.n)]),
	);
	const overall = statRows.reduce((s, r) => s + Number(r.n), 0);
	const lastScored = statRows
		.map((r) => (r.last ? new Date(String(r.last)).getTime() : 0))
		.reduce((m, t) => Math.max(m, t), 0);

	return {
		generated_at: (lastScored ? new Date(lastScored) : new Date())
			.toISOString()
			.slice(0, 10),
		model: String(page[0]?.model ?? "jev-latest"),
		thresholds: THRESHOLDS,
		count: overall,
		malicious: byDecision.block ?? 0,
		benign: byDecision.allow ?? 0,
		escalate: byDecision.escalate ?? 0,
		total: Number(totalRows[0]?.n ?? 0),
		next_cursor: hasMore && last ? `${last.risk}|${last.artifact_hash}` : null,
		source: "db",
		items: page.map((r) => ({
			name: String(r.identity ?? String(r.artifact_hash).slice(0, 12)),
			slug: String(r.artifact_hash).slice(0, 16),
			kind: String(r.kind ?? "skill"),
			// Real artifacts have no ground truth: `label` only mirrors the verdict
			// to fit the shared shape; the UI keys off `synthetic` to know that.
			label: r.decision === "block" ? "malicious" : "benign",
			note: String(r.source_url ?? r.source ?? ""),
			risk: Number(r.risk),
			decision: r.decision as "allow" | "escalate" | "block",
			correct: true,
			families: (r.families as Catalog["items"][number]["families"]) ?? [],
			top_signals:
				(r.signals as Catalog["items"][number]["top_signals"]) ?? [],
			synthetic: false,
		})),
	};
}
