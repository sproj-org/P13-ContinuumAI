const DEFAULT_API_BASE = "http://localhost:8000/api";

export function getApiBaseUrl(): string {
  const rawBase = process.env.NEXT_PUBLIC_API_URL?.trim() || DEFAULT_API_BASE;
  const withoutTrailingSlash = rawBase.replace(/\/+$/, "");

  return withoutTrailingSlash.endsWith("/api")
    ? withoutTrailingSlash
    : `${withoutTrailingSlash}/api`;
}
