import { proxy } from "../proxy";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
async function handle(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, (await context.params).path);
}
export {
  handle as GET,
  handle as POST,
  handle as PATCH,
  handle as DELETE,
  handle as HEAD,
};
