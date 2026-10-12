/** Browser endpoint, fixed by Next.js at build time. */
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

/** Keep every request under the configured API prefix. */
export function apiUrl(path: string, base: string = PUBLIC_API_URL): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}
