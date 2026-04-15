export type RenderMode = "http" | "spa";

export type GenerateResponse = {
  run_id: string;
  site_id: string;
  state: string;
  coalesced: boolean;
};

export type RunStatusResponse = {
  run_id: string;
  site_id: string;
  site_root_url: string;
  state: string;
  stage: string;
  pages_detected: number;
  pages_queued: number;
  pages_completed: number;
  completed_reason: "unchanged_root" | "processed" | null;
  error_message: string | null;
  updated_at: string;
};

export type SiteResponse = {
  site_id: string;
  root_url: string;
  created_at: string;
};

export type RunDownloadsResponse = {
  run_id: string;
  bundle_zip_url: string;
  expires_in_seconds: number;
};

function resolveDefaultApiBaseUrl(): string {
  const currentHostname = window.location.hostname;
  const isLocalDevelopmentHost =
    currentHostname === "localhost" || currentHostname === "127.0.0.1";

  if (isLocalDevelopmentHost) {
    return "http://localhost:8000";
  }

  return "https://profound-api.matiasnavarrodev.com";
}

function trimTrailingSlash(urlValue: string): string {
  return urlValue.replace(/\/+$/, "");
}

const apiBaseUrl = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL?.toString() ?? resolveDefaultApiBaseUrl()
);

async function parseJsonResponse<TResponse>(response: Response): Promise<TResponse> {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Request failed (${response.status}): ${errorText}`);
  }
  return (await response.json()) as TResponse;
}

export async function createRun(params: {
  url: string;
  renderMode: RenderMode;
}): Promise<GenerateResponse> {
  const response = await fetch(`${apiBaseUrl}/api/generate`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      url: params.url,
      render_mode: params.renderMode,
    }),
  });
  return parseJsonResponse<GenerateResponse>(response);
}

export async function fetchRunStatus(runId: string): Promise<RunStatusResponse> {
  const response = await fetch(`${apiBaseUrl}/api/runs/${runId}`);
  return parseJsonResponse<RunStatusResponse>(response);
}

export async function fetchRunDownloads(
  runId: string
): Promise<RunDownloadsResponse> {
  const response = await fetch(`${apiBaseUrl}/api/runs/${runId}/downloads`);
  return parseJsonResponse<RunDownloadsResponse>(response);
}

export async function fetchSites(): Promise<SiteResponse[]> {
  const response = await fetch(`${apiBaseUrl}/api/sites?limit=10`);
  return parseJsonResponse<SiteResponse[]>(response);
}

export function connectRunEvents(runId: string): EventSource {
  return new EventSource(`${apiBaseUrl}/api/runs/${runId}/events`);
}
