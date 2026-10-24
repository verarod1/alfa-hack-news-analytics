import type { AnalysisResponse, AnalysisStatus, AnalysisTrace, ChatHistoryResponse, ChatResponse, CompanyProfile, DemoProfilesResponse, FeedResponse, NewsDetail, RolesResponse } from '../types/api';
import { fetchAnalysis, fetchAnalysisTrace, fetchChatHistory, fetchCompanyById, fetchDemoProfiles, fetchFeed, fetchNews, fetchRoles, postChatMessage, startAnalysis } from './client';
import { MOCK_COMPANIES, MOCK_DEMO_PROFILES, MOCK_ROLES } from '../mocks/companies';
import { mockChatHistory, mockChatMessage } from '../mocks/chat';
import { mockAnalysis, mockAnalysisTrace, mockFeed, mockNews } from '../mocks/news';

// TODO: Когда заработает backend, создайте frontend/.env.local с VITE_USE_MOCK_API=false
// и перезапустите Vite (или пересоберите Docker-образ). Все методы ниже переключатся на /api/v1.
// VITE_API_BASE_URL нужен только если API доступен не через тот же origin и прокси.
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false';
export const isMockApi = USE_MOCK_API;

// Задержка используется только в демо, чтобы можно было проверить состояния загрузки.
const delay = <T,>(value: T, ms = 0): Promise<T> => new Promise((resolve) => setTimeout(() => resolve(value), ms));

// TODO: Реальный режим вызывает GET /api/v1/demo-profiles; items задают доступные демо-компании и стартовые роли.
export const getDemoProfiles = (): Promise<DemoProfilesResponse> =>
  USE_MOCK_API ? delay({ items: MOCK_DEMO_PROFILES }) : fetchDemoProfiles();

// TODO: Реальный режим вызывает GET /api/v1/roles; backend должен вернуть роли, разрешённые выбранному пользователю.
export const getRoles = (): Promise<RolesResponse> =>
  USE_MOCK_API ? delay({ items: MOCK_ROLES }) : fetchRoles();

// TODO: Реальный режим вызывает GET /api/v1/companies/{company_id}; 404 выводится в форме поиска.
export function getCompanyById(companyId: string): Promise<CompanyProfile> {
  if (!USE_MOCK_API) return fetchCompanyById(companyId);
  const company = MOCK_COMPANIES.find((item) => item.id.toLowerCase() === companyId.trim().toLowerCase());
  return company ? delay(company) : Promise.reject(new Error(`Компания с ID «${companyId}» не найдена`));
}

// TODO: Реальный режим вызывает GET /api/v1/feed с company_id, role, impact_type, limit и offset.
// Используйте items/total из ответа; фильтр и порядок новостей определяет backend.
export function getFeed(companyId: string, role: string, impactType?: 'risk' | 'opportunity', limit = 20, offset = 0): Promise<FeedResponse> {
  if (!USE_MOCK_API) return fetchFeed(companyId, role, impactType, limit, offset);
  const company = MOCK_COMPANIES.find((item) => item.id === companyId);
  const roleName = MOCK_ROLES.find((item) => item.code === role)?.name ?? role;
  const response = mockFeed(companyId, limit, offset, impactType);
  return delay({
    ...response,
    items: response.items.map((item) => ({
      ...item,
      short_insight: role === 'cfo'
        ? `Финансовый аспект: ${item.short_insight ?? 'оцените влияние на бюджет компании.'}`
        : role === 'accountant'
          ? `Для учёта и планирования: ${item.short_insight ?? 'проверьте доступные данные.'}`
          : item.short_insight,
      relevance_reasons: [company?.industry.name ?? 'Отрасль компании', `Роль: ${roleName}`],
    })),
  }, 850);
}

// TODO: Реальный режим вызывает GET /api/v1/news/{news_id} для текста новости и первоисточника.
export const getNews = (newsId: string, signal?: AbortSignal): Promise<NewsDetail> =>
  USE_MOCK_API ? delay(mockNews(newsId), 650) : fetchNews(newsId, signal);

function waitForPoll(signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new DOMException('Запрос отменён', 'AbortError')); return; }
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, 2000);
    const abort = () => { clearTimeout(timer); reject(new DOMException('Запрос отменён', 'AbortError')); };
    signal?.addEventListener('abort', abort, { once: true });
  });
}

// TODO: Если в GET /feed analysis_id=null, реальный режим отправляет POST /api/v1/analyses
// с {company_id, role, news_id}. Затем опрашивает GET /api/v1/analyses/{analysis_id}
// до completed/failed. Если analysis_id уже есть, POST не нужен. Интервал 2 с и лимит 30
// опросов — временная политика фронтенда; согласуйте Retry-After/таймаут с backend.
export async function getAnalysisForNews(
  companyId: string,
  role: string,
  newsId: string,
  analysisId: string | null,
  onStatus?: (status: AnalysisStatus) => void,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  if (USE_MOCK_API) {
    onStatus?.(analysisId ? 'running' : 'queued');
    const mockId = analysisId ?? `analysis_demo_${newsId}`;
    const result = await delay(mockAnalysis(mockId, companyId, role, newsId), 1100);
    if (signal?.aborted) throw new DOMException('Запрос отменён', 'AbortError');
    onStatus?.('completed');
    return result;
  }

  let id = analysisId;
  if (!id) {
    const started = await startAnalysis(companyId, role, newsId, signal);
    id = started.analysis_id;
    if (!id) throw new Error('Сервер не вернул идентификатор разбора.');
    onStatus?.(started.status);
  }
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await fetchAnalysis(id, signal);
    onStatus?.(response.status);
    if (response.status === 'completed') {
      if (!response.result) throw new Error('Сервер завершил разбор без результата.');
      return response;
    }
    if (response.status === 'failed') throw new Error('Не удалось подготовить разбор. Попробуйте ещё раз.');
    await waitForPoll(signal);
  }
  throw new Error('Разбор готовится слишком долго. Попробуйте открыть его позже.');
}

// TODO: Реальный режим вызывает GET /api/v1/analyses/{analysis_id}/trace.
// Показывайте шаги агентного анализа только после completed; source_ids связывают их с источниками.
export const getAnalysisTrace = (analysisId: string, signal?: AbortSignal): Promise<AnalysisTrace> =>
  USE_MOCK_API ? delay(mockAnalysisTrace(analysisId), 250) : fetchAnalysisTrace(analysisId, signal);

// TODO: Реальный режим вызывает GET /api/v1/analyses/{analysis_id}/messages?limit=&offset=.
// Используйте total/offset для пагинации истории; экран пока запрашивает первую страницу из 20 сообщений.
export const getChatHistory = (analysisId: string, limit = 20, offset = 0, signal?: AbortSignal): Promise<ChatHistoryResponse> =>
  USE_MOCK_API ? delay(mockChatHistory(analysisId, limit, offset)) : fetchChatHistory(analysisId, limit, offset, signal);

// TODO: Реальный режим вызывает POST /api/v1/chat/messages с analysis_id, conversation_id
// и message. Возвращённый conversation_id передаётся при следующих вопросах.
export function sendChatMessage(analysisId: string, conversationId: string | null, message: string): Promise<ChatResponse> {
  if (!USE_MOCK_API) return postChatMessage(analysisId, conversationId, message);
  return delay(mockChatMessage(analysisId, conversationId, message));
}
