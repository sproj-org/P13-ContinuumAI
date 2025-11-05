export interface QueryRequest {
  message: string;
  filters?: Record<string, any>;
}
export interface QuerySuccess {
  status: 'success';
  results: Array<{ data: any[]; layout?: any; config?: any }>;
}
export interface QueryError {
  status: 'error';
  message: string;
}
export type QueryResponse = QuerySuccess | QueryError;

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function runQuery(body: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  try { return await res.json(); }
  catch { return { status: 'error', message: `Bad response (${res.status})` }; }
}
