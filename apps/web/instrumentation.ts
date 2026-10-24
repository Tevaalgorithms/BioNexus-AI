/** Runs once at server start: load configuration from SSM (production) or `.env` (local). */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  const { loadParams } = await import("./lib/params");
  await loadParams();
}
