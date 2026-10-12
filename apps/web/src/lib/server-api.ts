/** Import this module from server-rendered pages only. */
import { apiUrl, PUBLIC_API_URL } from "./api";

export function serverApiUrl(path: string): string {
  return apiUrl(path, process.env.API_INTERNAL_URL || PUBLIC_API_URL);
}
