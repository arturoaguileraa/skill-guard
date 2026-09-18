import { z } from "zod";

/**
 * Client for the Jev microservice (apps/jev). This is the ONLY place the TS
 * side knows Jev exists; everything upstream sees a plain typed `analyze` call.
 * The Python service holds the API key and the question bank.
 */
const JEV_SERVICE_URL = (
	process.env.JEV_SERVICE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export const signalSchema = z.object({
	id: z.string(),
	family: z.string(),
	value: z.number(),
	confidence: z.number(),
	weight: z.number(),
});

export const familyRiskSchema = z.object({
	family: z.string(),
	risk: z.number(),
	weight: z.number(),
	label: z.string(),
});

export const analyzeResultSchema = z.object({
	identity: z.string(),
	risk: z.number(),
	decision: z.enum(["allow", "escalate", "block"]),
	mean_confidence: z.number(),
	integrity_warning: z.string().nullable(),
	families: z.array(familyRiskSchema),
	signals: z.array(signalSchema),
	input_tokens: z.number(),
	cost_usd: z.number(),
	latency_ms: z.number(),
	model: z.string(),
	request_id: z.string().nullable(),
	thresholds: z.object({ block: z.number(), review: z.number() }),
	error: z.string().nullable().optional(),
});

export type AnalyzeResult = z.infer<typeof analyzeResultSchema>;

export async function callJev(
	text: string,
	identity?: string,
): Promise<AnalyzeResult> {
	const res = await fetch(`${JEV_SERVICE_URL}/analyze`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify({ text, identity }),
	});
	if (!res.ok) {
		throw new Error(`jev service ${res.status}: ${await res.text()}`);
	}
	return analyzeResultSchema.parse(await res.json());
}

export const catalogItemSchema = z.object({
	name: z.string(),
	slug: z.string(),
	kind: z.string(),
	label: z.enum(["malicious", "benign"]),
	note: z.string(),
	risk: z.number(),
	decision: z.enum(["allow", "escalate", "block"]),
	correct: z.boolean(),
	families: z.array(
		z.object({ family: z.string(), label: z.string(), risk: z.number() }),
	),
	top_signals: z.array(z.object({ id: z.string(), value: z.number() })),
	synthetic: z.boolean(),
});

export const catalogSchema = z.object({
	generated_at: z.string(),
	model: z.string(),
	thresholds: z.object({ block: z.number(), review: z.number() }),
	count: z.number(),
	malicious: z.number(),
	benign: z.number(),
	items: z.array(catalogItemSchema),
	// Additive (paginated / DB-backed reads). Absent on the static catalog.
	escalate: z.number().optional(),
	total: z.number().optional(),
	next_cursor: z.string().nullable().optional(),
	source: z.enum(["db", "static"]).optional(),
});

export const catalogInputSchema = z
	.object({
		q: z.string().max(100).optional(),
		decision: z.enum(["allow", "escalate", "block"]).optional(),
		cursor: z.string().max(200).optional(),
		limit: z.number().int().min(1).max(100).default(50),
	})
	.default({ limit: 50 });

export type CatalogInput = z.infer<typeof catalogInputSchema>;

export type Catalog = z.infer<typeof catalogSchema>;
export type CatalogItem = z.infer<typeof catalogItemSchema>;

export async function fetchCatalog(input?: CatalogInput): Promise<Catalog> {
	const res = await fetch(`${JEV_SERVICE_URL}/catalog`);
	if (!res.ok)
		throw new Error(`jev service ${res.status}: ${await res.text()}`);
	const all = catalogSchema.parse(await res.json());
	if (!input) return all;

	// Static fallback (no DATABASE_URL): same filter/pagination contract, in memory.
	const needle = input.q?.trim().toLowerCase();
	const matched = all.items.filter(
		(it) =>
			(!input.decision || it.decision === input.decision) &&
			(!needle ||
				it.name.toLowerCase().includes(needle) ||
				it.note.toLowerCase().includes(needle)),
	);
	const start = input.cursor ? Number(input.cursor) || 0 : 0;
	const end = start + input.limit;
	return {
		...all,
		items: matched.slice(start, end),
		total: matched.length,
		next_cursor: end < matched.length ? String(end) : null,
		source: "static",
	};
}
