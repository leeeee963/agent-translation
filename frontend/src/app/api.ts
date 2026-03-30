import type { Language, Job, PromptConfig, GlossaryTerm, LibraryDomain, LibraryTerm } from "./types/translation";

async function request<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  let payload: unknown = null;
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    payload = await response.text();
  }
  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: string }).detail
        : null) ||
      (typeof payload === "string" ? payload : null) ||
      `请求失败 (${response.status})`;
    throw new Error(message);
  }
  return payload as T;
}

export async function fetchLanguages(): Promise<Language[]> {
  const data = await request<{ languages: Language[] }>("/api/languages");
  return data.languages || [];
}

export async function fetchPrompt(): Promise<PromptConfig> {
  return request<PromptConfig>("/api/prompt");
}

export async function savePrompt(content: string): Promise<void> {
  await request("/api/prompt", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function submitJobs(
  files: File[],
  targetLanguages: string[],
  useGlossary: boolean = true,
  libraryDomainIds: number[] = [],
): Promise<string[]> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("target_languages", targetLanguages.join(","));
  formData.append("use_glossary", useGlossary ? "true" : "false");
  if (libraryDomainIds.length > 0) {
    formData.append("library_domain_ids", libraryDomainIds.join(","));
  }
  const data = await request<{ job_ids: string[] }>("/api/jobs", {
    method: "POST",
    body: formData,
  });
  return data.job_ids || [];
}

export async function fetchJobs(): Promise<Job[]> {
  const data = await request<{ jobs: Job[] }>("/api/jobs");
  return data.jobs || [];
}

export async function cancelJob(jobId: string): Promise<void> {
  await request(`/api/jobs/${jobId}`, { method: "DELETE" });
}

export async function deleteJobs(jobIds: string[]): Promise<{ deleted: number }> {
  return request<{ deleted: number }>("/api/jobs/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function updateGlossaryTerm(
  jobId: string,
  termId: string,
  patch: { strategy?: GlossaryTerm["strategy"]; targets?: Record<string, string>; save_to_library?: boolean },
): Promise<GlossaryTerm> {
  const data = await request<{ term: GlossaryTerm }>(
    `/api/jobs/${jobId}/glossary/${termId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    },
  );
  return data.term;
}

export async function reextractGlossary(jobId: string): Promise<void> {
  await request(`/api/jobs/${jobId}/glossary/reextract`, { method: "POST" });
}

export async function confirmGlossary(
  jobId: string,
  termIds?: string[],
  updateLibraryTermIds?: string[],
): Promise<void> {
  await request(`/api/jobs/${jobId}/glossary/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      term_ids: termIds ?? null,
      update_library_term_ids: updateLibraryTermIds ?? null,
    }),
  });
}

export interface LLMConfig {
  api_key_masked: string;
  base_url: string;
  model: string;
}

export async function fetchLLMConfig(): Promise<LLMConfig> {
  return request<LLMConfig>("/api/llm-config");
}

export async function saveLLMConfig(config: {
  api_key?: string;
  base_url?: string;
  model?: string;
}): Promise<void> {
  await request("/api/llm-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

// ── Terminology Library API ──────────────────────────────────────────

export async function fetchLibraryDomains(): Promise<LibraryDomain[]> {
  const data = await request<{ domains: LibraryDomain[] }>("/api/library/domains");
  return data.domains || [];
}

export async function createLibraryDomain(name: string, description?: string): Promise<LibraryDomain> {
  return request<LibraryDomain>("/api/library/domains", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description || "" }),
  });
}

export async function updateLibraryDomain(id: number, data: { name?: string; description?: string }): Promise<void> {
  await request(`/api/library/domains/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteLibraryDomain(id: number): Promise<void> {
  await request(`/api/library/domains/${id}`, { method: "DELETE" });
}

export async function fetchLibraryTerms(
  domainId: number,
  params?: { search?: string; offset?: number; limit?: number },
): Promise<{ terms: LibraryTerm[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set("search", params.search);
  if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));
  if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();
  return request<{ terms: LibraryTerm[]; total: number }>(
    `/api/library/domains/${domainId}/terms${qs ? `?${qs}` : ""}`,
  );
}

export async function createLibraryTerm(
  domainId: number,
  term: { source: string; targets: Record<string, string>; strategy?: string; ai_category?: string; context?: string },
): Promise<{ id: number }> {
  return request<{ id: number }>(`/api/library/domains/${domainId}/terms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(term),
  });
}

export async function updateLibraryTerm(
  termId: number,
  data: { source?: string; targets?: Record<string, string>; strategy?: string; context?: string },
): Promise<void> {
  await request(`/api/library/terms/${termId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteLibraryTerm(termId: number): Promise<void> {
  await request(`/api/library/terms/${termId}`, { method: "DELETE" });
}

export async function deleteLibraryTermsBatch(termIds: number[]): Promise<{ deleted: number }> {
  return request<{ deleted: number }>("/api/library/terms/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term_ids: termIds }),
  });
}

export async function importLibraryTerms(domainId: number, file: File): Promise<{ inserted: number; updated: number }> {
  const formData = new FormData();
  formData.append("file", file);
  return request<{ inserted: number; updated: number }>(`/api/library/domains/${domainId}/import`, {
    method: "POST",
    body: formData,
  });
}

export function getExportUrl(domainId: number, format: "csv" | "tsv" | "json" = "csv"): string {
  return `/api/library/domains/${domainId}/export?format=${format}`;
}
