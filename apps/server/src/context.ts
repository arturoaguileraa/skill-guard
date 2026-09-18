import type { Context as ApiContext } from "@jev-analysis/api/context";
import type { Context as HonoContext } from "hono";

export type CreateContextOptions = {
  context: HonoContext;
};

export async function createContext(_options: CreateContextOptions): Promise<ApiContext> {
  return {};
}

export type Context = Awaited<ReturnType<typeof createContext>>;
