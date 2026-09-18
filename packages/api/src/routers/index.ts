import type { RouterClient } from "@orpc/server";
import { z } from "zod";

import { publicProcedure } from "../index";
import {
	analyzeResultSchema,
	callJev,
	catalogSchema,
	fetchCatalog,
} from "../jev";

export const appRouter = {
	healthCheck: publicProcedure.handler(() => {
		return "OK";
	}),

	/**
	 * Analyze a pasted skill/MCP artifact. The web app calls this on every
	 * (debounced) edit; it forwards to the Jev microservice and returns the
	 * calibrated, auditable reading.
	 */
	analyze: publicProcedure
		.input(z.object({ text: z.string(), identity: z.string().optional() }))
		.output(analyzeResultSchema)
		.handler(({ input }) => callJev(input.text, input.identity)),

	/** The catalog of skills/MCP servers we've already analyzed (the hub). */
	catalog: publicProcedure.output(catalogSchema).handler(() => fetchCatalog()),
};

export type AppRouter = typeof appRouter;
export type AppRouterClient = RouterClient<typeof appRouter>;
