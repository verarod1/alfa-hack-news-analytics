// src/types/api.ts

export type ClientType = 'CLIENT' | 'PROSPECT' | 'CLOSE_CLIENT';

export interface Industry {
  code: string | null;
  name: string | null;
}

export interface Revenue {
  value: number | null;
  unit: string;
  year?: number;
}

export interface ForeignTrade {
  has_data: boolean | null;
  countries: string[] | null;
}

export interface BankProducts {
  rko: boolean | null;
  guarantee: boolean | null;
  loan: boolean | null;
  leasing: boolean | null;
  deposit: boolean | null;
  payroll: boolean | null;
  factoring: boolean | null;
}

/**
 * Полный профиль компании (ответ GET /api/v1/companies/{company_id})
 */
export interface CompanyProfile {
  id: string;
  company_name: string;
  industry: Industry;
  region: string | null;
  city: string | null;
  age_range: string | null;
  employees_range: string | null;
  business_stage: string | null;
  client_type: ClientType | null;
  revenue: Revenue;
  foreign_trade: ForeignTrade;
  bank_products: BankProducts;
  group_id: string | null;
  organization_type: string | null;
  ownership_form: string | null;
  key_owner_flag: boolean | null;
  employees_spark_range: string | null;
}

/**
 * Элемент списка демо-профилей (ответ GET /api/v1/demo-profiles)
 */
export interface DemoProfileItem {
  company_id: string;
  company_name: string;
  role: string;
  role_name: string;
}

export interface DemoProfilesResponse {
  items: DemoProfileItem[];
}

/**
 * Доступная должность ЛПР (ответ GET /api/v1/roles)
 */
export interface RoleItem {
  code: string;
  name: string;
}

export interface RolesResponse {
  items: RoleItem[];
}

/**
 * Стандартный формат ошибки API
 */
export interface ApiErrorDetail {
  field: string;
  reason: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: ApiErrorDetail[];
  };
  request_id: string;
}

export type ImpactType = 'risk' | 'opportunity' | 'mixed' | 'neutral';
export type ImpactLevel = 'low' | 'medium' | 'high' | 'unknown';
export type AnalysisStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface NewsSource {
  id: string | null;
  name: string | null;
  url: string | null;
}

export interface FeedItem {
  id: string;
  title: string;
  published_at: string | null;
  source: NewsSource;
  is_synthetic?: boolean;
  relevance_score: number | null;
  impact_type: ImpactType | null;
  impact_level: ImpactLevel | null;
  short_insight: string | null;
  relevance_reasons: string[];
  analysis_id: string | null;
}

export interface FeedResponse {
  disclaimer?: string;
  ranking_mode?: 'chronological' | 'relevance';
  scored_total?: number;
  items: FeedItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface NewsDetail extends Pick<FeedItem, 'id' | 'title' | 'published_at' | 'source'> {
  text: string | null;
  created_at: string;
}

export interface AnalysisResult {
  what_happened: string;
  why_important: string;
  impact_type: ImpactType;
  impact_level: ImpactLevel;
  importance: string | null;
  confidence: string | null;
  statements?: { field: string; text: string; statement_type: string; evidence_ids: string[] }[];
  company_factors: { field: string; value: string | number | boolean | null; impact: string }[];
  analyzed_news_ids: string[];
  risks: { id: string; text: string; severity: string | null; evidence_ids: string[]; statement_type?: string }[];
  opportunities: { id: string; text: string; severity: string | null; evidence_ids: string[]; statement_type?: string }[];
  bank_opinion: { text: string; document_id: string; page: number; quote: string; evidence_ids: string[] } | null;
  recommended_actions: { text: string; basis_ids: string[] }[];
  sources: Array<{
    id: string;
    type: 'news' | 'bank_analytics';
    title?: string;
    url?: string;
    published_at?: string;
    document_id?: string;
    document_title?: string;
    page?: number;
    quote?: string;
  }>;
  limitations: string[];
}

export interface AnalysisResponse {
  analysis_id: string;
  status: AnalysisStatus;
  company_id: string;
  news_id: string;
  role: string;
  result: AnalysisResult | null;
  error_code?: string | null;
  attempt_count?: number;
  disclaimer?: string;
}

export interface StartAnalysisResponse {
  analysis_id: string;
  status: AnalysisStatus;
  result: null;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  evidence_ids: string[];
  status: AnalysisStatus;
}

export interface AnalysisTrace {
  analysis_id: string;
  steps: Array<{
    order: number;
    name: string;
    status: AnalysisStatus;
    model: string | null;
    tool: string | null;
    summary: string | null;
    attempt?: number;
    source_ids: string[];
    validation: { performed: boolean; passed: boolean | null };
  }>;
}

export interface ChatMessage {
  message_id: string;
  role: 'user' | 'assistant';
  content: string;
  evidence_ids?: string[];
  created_at: string;
}

export interface ChatHistoryResponse {
  analysis_id: string;
  items: ChatMessage[];
  total: number;
  limit: number;
  offset: number;
}
