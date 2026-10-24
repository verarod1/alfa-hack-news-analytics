// src/api/client.ts
import type {
  CompanyProfile,
  DemoProfilesResponse,
  RolesResponse,
  ApiErrorResponse,
  FeedResponse,
  NewsDetail,
  AnalysisResponse,
  StartAnalysisResponse,
  ChatResponse,
  AnalysisTrace,
  ChatHistoryResponse,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // TODO: Если backend потребует токен интернет-банка, добавьте его здесь из
  // согласованного механизма авторизации. Не храните секреты или API-ключи в VITE_*.
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    let errorMessage = `Ошибка сервера (HTTP ${response.status})`;
    try {
      const errData: ApiErrorResponse = await response.json();
      if (errData?.error?.message) {
        errorMessage = errData.error.message;
      }
    } catch {
      // Оставляем стандартное сообщение
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

export async function fetchDemoProfiles(): Promise<DemoProfilesResponse> {
  return request<DemoProfilesResponse>('/demo-profiles');
}

export async function fetchCompanyById(companyId: string): Promise<CompanyProfile> {
  return request<CompanyProfile>(`/companies/${encodeURIComponent(companyId.trim())}`);
}

export async function fetchRoles(): Promise<RolesResponse> {
  return request<RolesResponse>('/roles');
}

export async function fetchFeed(companyId: string, role: string, impactType?: 'risk' | 'opportunity', limit = 20, offset = 0): Promise<FeedResponse> {
  const params = new URLSearchParams({
    company_id: companyId,
    role,
    limit: String(limit),
    offset: String(offset),
  });
  if (impactType) params.set('impact_type', impactType);
  return request<FeedResponse>(`/feed?${params.toString()}`);
}

export const fetchNews = (newsId: string, signal?: AbortSignal) => request<NewsDetail>(`/news/${encodeURIComponent(newsId)}`, { signal });
export const fetchAnalysis = (analysisId: string, signal?: AbortSignal) => request<AnalysisResponse>(`/analyses/${encodeURIComponent(analysisId)}`, { signal });
export const startAnalysis = (companyId: string, role: string, newsId: string, signal?: AbortSignal) => request<StartAnalysisResponse>('/analyses', { method: 'POST', body: JSON.stringify({ company_id: companyId, role, news_id: newsId }), signal });
export const postChatMessage = (analysisId: string, conversationId: string | null, message: string) => request<ChatResponse>('/chat/messages', { method: 'POST', body: JSON.stringify({ analysis_id: analysisId, conversation_id: conversationId, message }) });
export const fetchAnalysisTrace = (analysisId: string, signal?: AbortSignal) => request<AnalysisTrace>(`/analyses/${encodeURIComponent(analysisId)}/trace`, { signal });
export function fetchChatHistory(analysisId: string, limit = 20, offset = 0, signal?: AbortSignal): Promise<ChatHistoryResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return request<ChatHistoryResponse>(`/analyses/${encodeURIComponent(analysisId)}/messages?${params}`, { signal });
}
