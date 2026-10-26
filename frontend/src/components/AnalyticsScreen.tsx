import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { getAnalysisForNews, getAnalysisStatus, getAnalysisTrace, getChatHistory, getFeed, getNews, getRoles, isMockApi, recalculateAnalysis, retryFailedAnalysis, sendChatMessage } from '../api/service';
import type { AnalysisResponse, AnalysisResult, AnalysisStatus, AnalysisTrace, ChatMessage, CompanyProfile, FeedItem, NewsDetail, RoleItem, StatementType } from '../types/api';
import { loadDemoConversation, saveDemoConversation } from '../utils/demoStorage';
import { newRequestKey } from '../utils/requestKey';

interface Props {
  session: { company: CompanyProfile; roleCode: string; roleName: string };
  onExit: () => void;
  onHome: () => void;
  onChangeRole: (roleCode: string, roleName: string) => void;
  themeControl: ReactNode;
}

type Filter = 'all' | 'risk' | 'opportunity';
type DetailTab = 'analysis' | 'chat';
const detailTabs: { id: DetailTab; label: string }[] = [
  { id: 'analysis', label: 'Разбор' },
  { id: 'chat', label: 'Обсуждение' },
];
const dateFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
const impactLabel = { risk: 'Риск', opportunity: 'Возможность', mixed: 'Смешанное влияние', neutral: 'Нейтрально' };
const factorLabels: Record<string, string> = { 'industry.name': 'Отрасль', 'bank_products.loan': 'Кредитные продукты', region: 'Регион', 'revenue.value': 'Выручка' };
const statementLabel: Record<StatementType, string> = { fact: 'Подтверждённый факт', model_inference: 'Вывод AI', hypothesis: 'Гипотеза AI' };
const feedPageSize = 20;
const chatPageSize = 20;

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const byId = new Map([...current, ...incoming].map((message) => [message.message_id, message]));
  return [...byId.values()].sort((left, right) => left.created_at.localeCompare(right.created_at) || left.message_id.localeCompare(right.message_id));
}

function formatFactorValue(value: string | number | boolean | null): string {
  if (value === null) return 'нет данных';
  if (typeof value === 'boolean') return value ? 'есть' : 'нет';
  return String(value);
}

function LoadingDots() {
  return <span className="loading-dots" aria-hidden="true"><span /><span /><span /></span>;
}

function FeedLoading() {
  return <div className="feed-loading">
    <p className="loading-caption" role="status"><LoadingDots /> Подбираем новости для вашей компании…</p>
    <div className="analytics-grid" aria-hidden="true">
      {[0, 1, 2].map((index) => <div className="analytics-event skeleton-event" key={index}>
        <span className="skeleton-line skeleton-date" />
        <span className="skeleton-line skeleton-tag" />
        <span className="skeleton-line skeleton-heading" />
        <span className="skeleton-line skeleton-heading short" />
        <span className="skeleton-line skeleton-copy" />
        <span className="skeleton-line skeleton-copy short" />
        <span className="skeleton-line skeleton-link" />
      </div>)}
    </div>
  </div>;
}

function DetailLoading({ status }: { status: AnalysisStatus | null }) {
  const message = status === 'queued' ? 'Разбор ожидает обработки…' : status === 'running' ? 'Анализируем событие…' : 'Открываем персональный разбор…';
  return <div className="detail-loading">
    <p className="loading-caption" role="status"><LoadingDots /> {message}</p>
    <p className="loading-hint">Загружаем выводы, рекомендации и источники.</p>
    <div aria-hidden="true" className="detail-skeleton">
      {[0, 1, 2].map((index) => <div className="detail-skeleton-section" key={index}>
        <span className="skeleton-line skeleton-section-title" />
        <span className="skeleton-line skeleton-copy" />
        <span className="skeleton-line skeleton-copy short" />
      </div>)}
    </div>
  </div>;
}

function EvidenceLinks({ ids, sources }: { ids: string[]; sources: AnalysisResult['sources'] }) {
  if (ids.length === 0) return null;
  return <span className="detail-evidence">Основание: {ids.map((id, index) => {
    const source = sources.find((item) => item.id === id);
    const label = source?.title ?? source?.document_title ?? (source?.type === 'news' ? 'Новость' : id);
    const page = source?.page ? `, стр. ${source.page}` : '';
    return <span key={id}>{index > 0 ? ', ' : ''}{source?.url
      ? <a href={source.url} target="_blank" rel="noopener noreferrer">{label}{page}</a>
      : <>{label}{page}</>}</span>;
  })}</span>;
}

export function AnalyticsScreen({ session, onExit, onHome, onChangeRole, themeControl }: Props) {
  const { company, roleCode, roleName } = session;
  const [filter, setFilter] = useState<Filter>('all');
  const [roles, setRoles] = useState<RoleItem[]>([{ code: roleCode, name: roleName }]);
  const [reload, setReload] = useState(0);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [feedTotal, setFeedTotal] = useState(0);
  const [rankingMode, setRankingMode] = useState<'chronological' | 'relevance'>('chronological');
  const [scoredTotal, setScoredTotal] = useState(0);
  const [feedDisclaimer, setFeedDisclaimer] = useState<string | null>(null);
  const [feedLoadingMore, setFeedLoadingMore] = useState(false);
  const [feedMoreError, setFeedMoreError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<FeedItem | null>(null);
  const [news, setNews] = useState<NewsDetail | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [pollPaused, setPollPaused] = useState(false);
  const [trace, setTrace] = useState<AnalysisTrace | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatHistoryOffset, setChatHistoryOffset] = useState(0);
  const [chatHistoryLoading, setChatHistoryLoading] = useState(false);
  const [chatOlderLoading, setChatOlderLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<DetailTab>('analysis');
  const [detailError, setDetailError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatStorageScope, setChatStorageScope] = useState<{ companyId: string; roleCode: string; analysisId: string } | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [recalculateLoading, setRecalculateLoading] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const detailRequest = useRef(0);
  const detailAbort = useRef<AbortController | null>(null);
  const feedGeneration = useRef(0);
  const pendingQuestion = useRef<{ analysisId: string; message: string; key: string } | null>(null);
  const pendingRecalculation = useRef<{ newsId: string; key: string } | null>(null);

  const closeDetail = () => {
    detailRequest.current += 1;
    detailAbort.current?.abort();
    pendingQuestion.current = null;
    pendingRecalculation.current = null;
    setSelected(null);
  };

  useEffect(() => () => detailAbort.current?.abort(), []);

  useEffect(() => {
    if (!isMockApi || !chatStorageScope) return;
    saveDemoConversation(chatStorageScope.companyId, chatStorageScope.roleCode, chatStorageScope.analysisId, {
      conversationId,
      messages: chatMessages,
    });
  }, [chatStorageScope, chatMessages, conversationId]);

  useEffect(() => {
    let active = true;
    getRoles()
      .then((response) => { if (active && response.items.length > 0) setRoles(response.items); })
      .catch(() => { /* Текущая роль остаётся доступной при ошибке загрузки списка. */ });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    const generation = ++feedGeneration.current;
    getFeed(company.id, roleCode, filter === 'all' ? undefined : filter, feedPageSize)
      .then((response) => {
        if (!active || generation !== feedGeneration.current) return;
        setItems(response.items);
        setFeedTotal(response.total);
        setRankingMode(response.ranking_mode ?? 'chronological');
        setScoredTotal(response.scored_total ?? 0);
        setFeedDisclaimer(response.disclaimer ?? null);
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить ленту'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [company.id, roleCode, filter, reload]);

  const loadMoreFeed = async () => {
    if (feedLoadingMore || items.length >= feedTotal) return;
    const generation = feedGeneration.current;
    setFeedLoadingMore(true);
    setFeedMoreError(null);
    try {
      const response = await getFeed(company.id, roleCode, filter === 'all' ? undefined : filter, feedPageSize, items.length);
      if (generation !== feedGeneration.current) return;
      setItems((current) => [...current, ...response.items.filter((item) => !current.some((saved) => saved.id === item.id))]);
      setFeedTotal(response.total);
      setRankingMode(response.ranking_mode ?? 'chronological');
      setScoredTotal(response.scored_total ?? 0);
    } catch (reason) {
      if (generation === feedGeneration.current) setFeedMoreError(reason instanceof Error ? reason.message : 'Не удалось загрузить следующую страницу');
    } finally {
      if (generation === feedGeneration.current) setFeedLoadingMore(false);
    }
  };

  const loadLatestHistory = useCallback(async (analysisId: string, requestId: number, signal: AbortSignal, preserve = false) => {
    const count = await getChatHistory(analysisId, company.id, 1, 0, signal);
    const offset = Math.max(0, count.total - chatPageSize);
    const page = count.total ? await getChatHistory(analysisId, company.id, chatPageSize, offset, signal) : count;
    if (requestId !== detailRequest.current || signal.aborted) return;
    if (!preserve) setChatHistoryOffset(offset);
    setChatMessages((current) => preserve ? mergeMessages(current.filter((message) => !message.message_id.startsWith('local_user_')), page.items) : page.items);
  }, [company.id]);

  const activeAnalysisId = analysis?.analysis_id;
  const activeAnalysisStatus = analysis?.status;
  const analysisReady = activeAnalysisStatus === 'completed' && Boolean(analysis?.result);

  useEffect(() => {
    if (!selected || !activeAnalysisId || isMockApi || (activeAnalysisStatus !== 'queued' && activeAnalysisStatus !== 'running') || pollPaused) return;
    const controller = detailAbort.current;
    if (!controller) return;
    const requestId = detailRequest.current;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getAnalysisStatus(activeAnalysisId, company.id, controller.signal);
        if (cancelled || requestId !== detailRequest.current) return;
        setAnalysis(next);
        setAnalysisStatus(next.status);
        setStatusError(null);
        if (next.status === 'completed') { setChatHistoryLoading(true); setLoading(true); setReload((value) => value + 1); return; }
        if (next.status === 'failed') return;
        attempts += 1;
        if (attempts >= 24) { setPollPaused(true); return; }
        timer = setTimeout(() => void poll(), 5000);
      } catch (reason) {
        if (cancelled || controller.signal.aborted || requestId !== detailRequest.current) return;
        setStatusError(reason instanceof Error ? reason.message : 'Не удалось обновить статус разбора');
        setPollPaused(true);
      }
    };
    timer = setTimeout(() => void poll(), 5000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [activeAnalysisId, activeAnalysisStatus, company.id, pollPaused, selected]);

  useEffect(() => {
    if (!selected || !analysisReady || !activeAnalysisId) return;
    const controller = detailAbort.current;
    if (!controller) return;
    const requestId = detailRequest.current;
    void getAnalysisTrace(activeAnalysisId, company.id, controller.signal)
      .then((data) => { if (requestId === detailRequest.current) setTrace(data); })
      .catch(() => { /* Разбор остаётся доступен без трассировки. */ });
    if (isMockApi) return;
    void Promise.resolve().then(() => loadLatestHistory(activeAnalysisId, requestId, controller.signal))
      .catch(() => { if (requestId === detailRequest.current) setChatError('Историю обсуждения не удалось загрузить. Можно задать новый вопрос.'); })
      .finally(() => { if (requestId === detailRequest.current) setChatHistoryLoading(false); });
  }, [activeAnalysisId, analysisReady, company.id, loadLatestHistory, selected]);

  useEffect(() => {
    if (!selected) return;
    previousFocus.current = document.activeElement as HTMLElement;
    closeButton.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeDetail();
      if (event.key !== 'Tab') return;
      const focusable = [...document.querySelectorAll<HTMLElement>('.detail-dialog button:not(:disabled), .detail-dialog input, .detail-dialog a[href]')]
        .filter((element) => !element.closest('[hidden]'));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
      previousFocus.current?.focus();
    };
  }, [selected]);

  const openDetail = async (item: FeedItem) => {
    detailAbort.current?.abort();
    const controller = new AbortController();
    detailAbort.current = controller;
    const requestId = ++detailRequest.current;
    setSelected(item);
    setNews(null);
    setAnalysis(null);
    setAnalysisStatus(null);
    setStatusError(null);
    setPollPaused(false);
    setTrace(null);
    setChatMessages([]);
    setChatHistoryOffset(0);
    setChatHistoryLoading(false);
    setChatOlderLoading(false);
    setChatLoading(false);
    setDetailTab('analysis');
    setDetailError(null);
    setChatError(null);
    setQuestion('');
    setConversationId(null);
    setChatStorageScope(null);
    pendingQuestion.current = null;
    pendingRecalculation.current = null;
    setRecalculateLoading(false);
    try {
      const [newsData, analysisData] = await Promise.all([
        getNews(item.id, controller.signal),
        getAnalysisForNews(company.id, roleCode, item.id, item.analysis_id, (status) => {
          if (requestId === detailRequest.current) setAnalysisStatus(status);
        }, controller.signal),
      ]);
      if (requestId === detailRequest.current) {
        setNews(newsData);
        setAnalysis(analysisData);
        setAnalysisStatus(analysisData.status);
        if (!isMockApi && analysisData.status === 'completed') setChatHistoryLoading(true);
        if (isMockApi && analysisData.status === 'completed') {
          const saved = loadDemoConversation(company.id, roleCode, analysisData.analysis_id);
          setChatMessages(saved?.messages ?? []);
          setConversationId(saved?.conversationId ?? null);
          setChatStorageScope({ companyId: company.id, roleCode, analysisId: analysisData.analysis_id });
        }
      }
    } catch (reason) {
      if (requestId === detailRequest.current && !controller.signal.aborted) setDetailError(reason instanceof Error ? reason.message : 'Не удалось открыть разбор');
    }
  };

  const refreshAnalysis = async () => {
    if (!analysis || !detailAbort.current) return;
    const requestId = detailRequest.current;
    setStatusError(null);
    try {
      const next = await getAnalysisStatus(analysis.analysis_id, company.id, detailAbort.current.signal);
      if (requestId !== detailRequest.current) return;
      setAnalysis(next);
      setAnalysisStatus(next.status);
      setPollPaused(false);
      if (next.status === 'completed') { setChatHistoryLoading(true); setLoading(true); setReload((value) => value + 1); }
    } catch (reason) {
      if (requestId === detailRequest.current) setStatusError(reason instanceof Error ? reason.message : 'Не удалось обновить статус разбора');
    }
  };

  const retryAnalysis = async () => {
    if (!analysis || !detailAbort.current || analysis.status !== 'failed') return;
    const requestId = detailRequest.current;
    setStatusError(null);
    try {
      const next = await retryFailedAnalysis(analysis.analysis_id, company.id, detailAbort.current.signal);
      if (requestId !== detailRequest.current) return;
      setAnalysis(next);
      setAnalysisStatus(next.status);
      setPollPaused(false);
    } catch (reason) {
      if (requestId === detailRequest.current) setStatusError(reason instanceof Error ? reason.message : 'Не удалось повторить разбор');
    }
  };

  const recalculateCurrentAnalysis = async () => {
    if (!selected || !analysis || !detailAbort.current || recalculateLoading) return;
    const requestId = detailRequest.current;
    const signal = detailAbort.current.signal;
    if (pendingRecalculation.current?.newsId !== selected.id) {
      pendingRecalculation.current = { newsId: selected.id, key: newRequestKey() };
    }
    setRecalculateLoading(true);
    setStatusError(null);
    try {
      const next = await recalculateAnalysis(company.id, roleCode, selected.id, pendingRecalculation.current.key, signal);
      if (requestId !== detailRequest.current) return;
      pendingRecalculation.current = null;
      setAnalysis(next);
      setAnalysisStatus(next.status);
      setPollPaused(false);
      setTrace(null);
      setChatMessages([]);
      setConversationId(null);
      setChatHistoryOffset(0);
      setDetailTab('analysis');
    } catch (reason) {
      if (requestId === detailRequest.current && !signal.aborted) setStatusError(reason instanceof Error ? reason.message : 'Не удалось запустить новый разбор');
    } finally {
      if (requestId === detailRequest.current) setRecalculateLoading(false);
    }
  };

  const loadOlderHistory = async () => {
    if (!analysis || !detailAbort.current || chatHistoryOffset <= 0) return;
    const requestId = detailRequest.current;
    const count = Math.min(chatPageSize, chatHistoryOffset);
    const offset = chatHistoryOffset - count;
    setChatOlderLoading(true);
    setChatError(null);
    try {
      const page = await getChatHistory(analysis.analysis_id, company.id, count, offset, detailAbort.current.signal);
      if (requestId !== detailRequest.current) return;
      setChatMessages((current) => mergeMessages(current, page.items));
      setChatHistoryOffset(offset);
    } catch (reason) {
      if (requestId === detailRequest.current) setChatError(reason instanceof Error ? reason.message : 'Не удалось загрузить ранние сообщения');
    } finally {
      if (requestId === detailRequest.current) setChatOlderLoading(false);
    }
  };

  const askQuestion = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim() || !analysis || analysis.status !== 'completed' || chatLoading || chatHistoryLoading) return;
    const sentQuestion = question.trim();
    const requestId = detailRequest.current;
    if (pendingQuestion.current?.analysisId !== analysis.analysis_id || pendingQuestion.current.message !== sentQuestion) {
      pendingQuestion.current = { analysisId: analysis.analysis_id, message: sentQuestion, key: newRequestKey() };
    }
    const requestKey = pendingQuestion.current.key;
    setChatLoading(true);
    setChatError(null);
    try {
      const response = await sendChatMessage(analysis.analysis_id, conversationId, sentQuestion, company.id, requestKey);
      if (requestId !== detailRequest.current) return;
      pendingQuestion.current = null;
      setConversationId(response.conversation_id);
      if (isMockApi) {
        const createdAt = new Date().toISOString();
        setChatMessages((current) => [...current,
          { message_id: `local_user_${response.message_id}`, role: 'user', content: sentQuestion, created_at: createdAt },
          { message_id: response.message_id, role: 'assistant', content: response.answer, evidence_ids: response.evidence_ids, statement_type: response.statement_type, bank_opinion: response.bank_opinion, created_at: createdAt },
        ]);
      } else if (detailAbort.current) {
        try {
          await loadLatestHistory(analysis.analysis_id, requestId, detailAbort.current.signal, true);
        } catch {
          const createdAt = new Date().toISOString();
          setChatMessages((current) => [...current,
            { message_id: `local_user_${response.message_id}`, role: 'user', content: sentQuestion, created_at: createdAt },
            { message_id: response.message_id, role: 'assistant', content: response.answer, evidence_ids: response.evidence_ids, statement_type: response.statement_type, bank_opinion: response.bank_opinion, created_at: createdAt },
          ]);
          setChatError('Ответ получен, но обновить историю не удалось.');
        }
      }
      setQuestion('');
    } catch (reason) {
      if (requestId === detailRequest.current) setChatError(reason instanceof Error ? reason.message : 'Не удалось отправить вопрос');
    } finally {
      if (requestId === detailRequest.current) setChatLoading(false);
    }
  };

  return (
    <div className="analytics-page">
      <header className="analytics-topbar">
        <div className="analytics-brand"><span className="analytics-brandmark">А</span> Альфа-Бизнес</div>
        <div className="analytics-header-actions">{themeControl}{isMockApi && <span className="demo-stand-badge">Демо-данные</span>}<button type="button" className="analytics-exit" onClick={onHome}>На главную</button><button type="button" className="analytics-exit" onClick={onExit}>Сменить профиль</button></div>
      </header>
      <main className="analytics-main">
        <div className="analytics-content">
          <p className="analytics-eyebrow">Новости для вашего бизнеса</p>
          <h1>Персональная аналитика</h1>
          <p className="analytics-subtitle">Риски, возможности и события в вашей отрасли</p>
          <section className="analytics-company" aria-label="Выбранный профиль">
            <span className="analytics-company-icon" aria-hidden="true">▦</span>
            <div className="analytics-company-details"><strong>{company.company_name}</strong><p>{company.industry.name ?? 'Отрасль не указана'} · {company.region ?? 'Регион не указан'}</p></div>
            <div className="analytics-role-control">
              <label htmlFor="active-role">Роль пользователя</label>
              <select
                id="active-role"
                value={roleCode}
                onChange={(event) => {
                  const role = roles.find((item) => item.code === event.target.value);
                  if (!role) return;
                  setLoading(true);
                  setError(null);
                  setItems([]);
                  onChangeRole(role.code, role.name);
                }}
              >
                {roles.map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}
              </select>
            </div>
          </section>
          <section aria-labelledby="events-heading" aria-busy={loading}>
            <h2 id="events-heading">События для вашей компании</h2>
            <div className="analytics-filters" role="group" aria-label="Тип влияния">
              {(['all', 'risk', 'opportunity'] as const).map((value) => (
                <button key={value} type="button" className={filter === value ? 'analytics-filter active' : 'analytics-filter'} onClick={() => { if (value === filter) return; setLoading(true); setError(null); setFilter(value); }} aria-pressed={filter === value}>
                  {{ all: 'Все', risk: 'Риски', opportunity: 'Возможности' }[value]}
                </button>
              ))}
            </div>
            {loading && <FeedLoading />}
            {error && <div className="analytics-state" role="alert">{error} <button type="button" onClick={() => { setLoading(true); setError(null); setReload((value) => value + 1); }}>Повторить</button></div>}
            {!loading && !error && <p className="analytics-feed-meta">{rankingMode === 'relevance'
              ? `По релевантности: оценено ${scoredTotal} из ${feedTotal} новостей.`
              : 'Оценки релевантности пока нет; новости показаны по дате.'}</p>}
            {!loading && !error && items.length === 0 && <p className="analytics-state">{filter === 'all' ? 'Новостей пока нет.' : 'По этому фильтру нет новостей с готовым разбором. Откройте «Все», чтобы оценить влияние других событий.'}</p>}
            {!loading && !error && <div className="analytics-grid">
              {items.map((item) => <article className="analytics-event" key={item.id}>
                <time dateTime={item.published_at ?? undefined}>{item.published_at ? dateFormat.format(new Date(item.published_at)) : 'Дата не указана'}</time>
                <div className="analytics-event-labels"><span className="analytics-topic">{item.topic_label}</span>{item.is_archived && <span className="analytics-archive">Архивная публикация</span>}</div>
                {item.impact_type && <span className={`analytics-pill analytics-pill--${item.impact_type}`}>{impactLabel[item.impact_type]}</span>}
                {item.is_synthetic && <span className="analytics-data-label">Синтетическая новость</span>}
                <h3 title={item.title}>{item.title}</h3>
                <p className="analytics-event-source">Источник: {item.source.name ?? 'не указан'}</p>
                <p className="analytics-event-excerpt">{item.excerpt ?? 'Краткое содержание источника недоступно. Откройте новость, чтобы посмотреть детали.'}</p>
                {item.short_insight ? <p className="analytics-event-insight"><strong>Влияние на компанию:</strong> {item.short_insight}</p> : <p className="analytics-event-pending">Влияние на вашу компанию ещё не оценено.</p>}
                {item.relevance_score !== null && <p className="analytics-event-score">Предварительная релевантность: {Math.round(item.relevance_score * 100)}%</p>}
                {item.relevance_reasons.length > 0 && <div className="analytics-relevance"><p>Возможная связь с компанией: {item.relevance_reasons[0]}</p>{item.relevance_reasons.length > 1 && <span>Ещё причин в разборе: {item.relevance_reasons.length - 1}</span>}</div>}
                <div className="analytics-event-footer"><button type="button" onClick={() => void openDetail(item)}>{item.analysis_id ? 'Открыть разбор' : 'Оценить влияние'} <span aria-hidden="true">→</span></button></div>
              </article>)}
            </div>}
            {!loading && !error && items.length < feedTotal && <div className="analytics-more"><button type="button" disabled={feedLoadingMore} onClick={() => void loadMoreFeed()}>{feedLoadingMore ? 'Загрузка…' : 'Показать ещё новости'}</button></div>}
            {feedMoreError && <p className="analytics-more-error" role="alert">{feedMoreError} <button type="button" onClick={() => void loadMoreFeed()}>Повторить</button></p>}
            {!loading && !error && feedDisclaimer && <p className="analytics-disclaimer">{feedDisclaimer}</p>}
          </section>
        </div>
      </main>
      {selected && <div className="detail-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDetail(); }}>
        <section className="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="detail-title" aria-busy={!news && !detailError}>
          <div className="detail-header"><div>{selected.impact_type && <span className={`analytics-pill analytics-pill--${selected.impact_type}`}>{impactLabel[selected.impact_type]}</span>}<h2 id="detail-title">{selected.title}</h2></div><button ref={closeButton} type="button" className="detail-close" onClick={closeDetail} aria-label="Закрыть разбор">×</button></div>
          {!news && !detailError && <DetailLoading status={analysisStatus} />}
          {detailError && <div role="alert" className="detail-error"><p>{detailError}</p><button type="button" onClick={() => void openDetail(selected)}>Повторить</button></div>}
          {news && <>
            <p className="detail-meta">{news.published_at ? dateFormat.format(new Date(news.published_at)) : 'Дата не указана'} · {news.source.url ? <a href={news.source.url} target="_blank" rel="noopener noreferrer">{news.source.name ?? 'Первоисточник'}</a> : news.source.name ?? 'Источник не указан'} {news.is_synthetic && <span className="analytics-data-label">Синтетическая новость</span>}</p>
            {selected.relevance_reasons.length > 0 && <details className="detail-relevance"><summary>Предварительная релевантность: {selected.relevance_score === null ? 'оценка без балла' : `${Math.round(selected.relevance_score * 100)}%`} · причины</summary><ul>{selected.relevance_reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul></details>}
            <div className="detail-tabs" role="tablist" aria-label="Содержание новости">
              {detailTabs.map((tab) => <button
                key={tab.id}
                id={`detail-tab-${tab.id}`}
                type="button"
                role="tab"
                aria-selected={detailTab === tab.id}
                aria-controls={`detail-panel-${tab.id}`}
                tabIndex={detailTab === tab.id ? 0 : -1}
                disabled={tab.id === 'chat' && !analysis?.result}
                onClick={() => setDetailTab(tab.id)}
                onKeyDown={(event) => {
                  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight' && event.key !== 'Home' && event.key !== 'End') return;
                  event.preventDefault();
                  const nextTab = event.key === 'Home' ? 'analysis' : event.key === 'End' ? 'chat' : detailTab === 'analysis' ? 'chat' : 'analysis';
                  if (nextTab === 'chat' && !analysis?.result) return;
                  setDetailTab(nextTab);
                  document.getElementById(`detail-tab-${nextTab}`)?.focus();
                }}
              >{tab.label}</button>)}
            </div>
            <div id="detail-panel-analysis" role="tabpanel" aria-labelledby="detail-tab-analysis" hidden={detailTab !== 'analysis'}>
              {analysis?.status === 'completed' && <div className="detail-section"><h3>Статус разбора</h3><p role="status">Разбор готов.</p>{!isMockApi && <><p>Если данные компании или материалы банка изменились, можно рассчитать новый результат.</p><button type="button" className="detail-refresh" disabled={recalculateLoading} onClick={() => void recalculateCurrentAnalysis()}>{recalculateLoading ? 'Запускаем…' : 'Пересчитать разбор'}</button>{statusError && <p role="alert">{statusError}</p>}</>}</div>}
              <div className="detail-section"><h3>Что произошло</h3><p>{analysis?.result?.what_happened ?? news.text ?? 'Текст новости недоступен.'}</p>{analysis?.result ? <><span className="detail-claim-type">{statementLabel[analysis.result.statements.find((statement) => statement.field === 'what_happened')?.statement_type ?? 'fact']}</span><EvidenceLinks ids={analysis.result.statements.find((statement) => statement.field === 'what_happened')?.evidence_ids ?? []} sources={analysis.result.sources} /></> : null}</div>
              {analysis?.result ? <>
                <div className="detail-section"><h3>Почему это важно для компании</h3><p>{analysis.result.why_important}</p><span className="detail-claim-type">{statementLabel[analysis.result.statements.find((statement) => statement.field === 'why_important')?.statement_type ?? 'model_inference']}</span><EvidenceLinks ids={analysis.result.statements.find((statement) => statement.field === 'why_important')?.evidence_ids ?? []} sources={analysis.result.sources} /></div>
                {analysis.result.company_factors.length > 0 && <div className="detail-section"><h3>Учтённые данные компании</h3><ul>{analysis.result.company_factors.map((factor) => <li key={factor.field}><strong>{factorLabels[factor.field] ?? factor.field}</strong>: {formatFactorValue(factor.value)} — {factor.impact}</li>)}</ul></div>}
                {(analysis.result.risks.length > 0 || analysis.result.opportunities.length > 0) && <div className="detail-section"><h3>Риски и возможности</h3><ul>{analysis.result.risks.map((risk) => <li key={risk.id}><strong>Риск · {statementLabel[risk.statement_type]}</strong>: {risk.text}<EvidenceLinks ids={risk.evidence_ids} sources={analysis.result!.sources} /></li>)}{analysis.result.opportunities.map((opportunity) => <li key={opportunity.id}><strong>Возможность · {statementLabel[opportunity.statement_type]}</strong>: {opportunity.text}<EvidenceLinks ids={opportunity.evidence_ids} sources={analysis.result!.sources} /></li>)}</ul></div>}
                <div className="detail-section"><h3>Материалы Альфа-Банка по теме</h3>{analysis.result.bank_opinion
                  ? <><p>{analysis.result.bank_opinion.text}</p><p className="detail-source-note">Документ {analysis.result.bank_opinion.document_id}, стр. {analysis.result.bank_opinion.page}. Цитата: «{analysis.result.bank_opinion.quote}»</p><EvidenceLinks ids={analysis.result.bank_opinion.evidence_ids} sources={analysis.result.sources} /></>
                  : <p>Подтверждённых материалов банка по этой теме пока нет.</p>}</div>
                <div className="detail-section detail-recommendations"><h3>Возможные действия</h3>{analysis.result.recommended_actions.length ? <ul>{analysis.result.recommended_actions.map((action, index) => <li key={index}>{action.text}<span className="detail-evidence">Основание: {action.basis_ids.map((id) => [...analysis.result!.risks, ...analysis.result!.opportunities].find((finding) => finding.id === id)?.text ?? id).join('; ')}</span></li>)}</ul> : <p>Обоснованных действий пока нет.</p>}</div>
                <div className="detail-section"><h3>Источники и ограничения</h3><ul>{analysis.result.sources.map((source) => <li key={source.id}>{source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title ?? source.document_title ?? source.url}</a> : source.title ?? source.document_title ?? source.id}{source.page ? `, стр. ${source.page}` : ''}{source.quote && <span className="detail-evidence">Цитата: «{source.quote}»</span>}</li>)}{analysis.result.limitations.map((limitation, index) => <li key={`limit_${index}`}>{limitation}</li>)}</ul></div>
                {trace && <details className="detail-section detail-trace"><summary>Как получен вывод</summary><ol>{trace.steps.map((step) => <li key={`${step.attempt ?? 1}_${step.order}`}><strong>{step.name}</strong> · {step.status}{step.tool ? ` · ${step.tool}` : ''}{step.model ? ` · ${step.model}` : ''}{step.summary ? <span className="detail-trace-summary">{step.summary}</span> : null}<EvidenceLinks ids={step.source_ids} sources={analysis.result!.sources} />{step.validation.performed && <span className="detail-evidence">Проверка: {step.validation.passed ? 'пройдена' : 'не пройдена'}</span>}</li>)}</ol></details>}
                {analysis.disclaimer && <p className="detail-disclaimer">{analysis.disclaimer}</p>}
              </> : <div className="detail-section" role="status"><h3>Статус разбора</h3><p>{analysis?.status === 'failed' ? 'Обработка завершилась с ошибкой.' : analysis?.status === 'running' ? 'Разбор обрабатывается.' : 'Разбор поставлен в очередь.'}</p>{analysis?.status === 'failed' ? <p>Код ошибки: {analysis.error_code ?? 'не указан'}.</p> : <p>{pollPaused ? 'Автоматическое обновление приостановлено.' : 'Проверяем готовность разбора автоматически.'}</p>}{statusError && <p role="alert">Не удалось проверить статус: {statusError}</p>}{analysis?.status === 'failed' && <button type="button" className="detail-refresh" onClick={() => void retryAnalysis()}>Повторить разбор</button>}<button type="button" className="detail-refresh" onClick={() => void refreshAnalysis()}>Проверить статус</button>{analysis?.disclaimer && <p className="detail-disclaimer">{analysis.disclaimer}</p>}</div>}
            </div>
            <div id="detail-panel-chat" role="tabpanel" aria-labelledby="detail-tab-chat" hidden={detailTab !== 'chat'}>
              {analysis?.result && <form className="detail-chat" onSubmit={(event) => void askQuestion(event)}>
                <p className="detail-chat-intro">Задайте вопрос о том, как эта новость влияет на вашу компанию.</p>
                {!isMockApi && chatHistoryOffset > 0 && <button type="button" className="detail-history-more" disabled={chatOlderLoading} onClick={() => void loadOlderHistory()}>{chatOlderLoading ? 'Загрузка…' : 'Показать ранние сообщения'}</button>}
                {chatHistoryLoading && <p role="status">Загружаем историю обсуждения…</p>}
                <div className="detail-chat-history" aria-live="polite">
                  {chatMessages.length === 0
                    ? <p className="detail-chat-empty">Здесь появится обсуждение новости. Начните с вопроса по разбору.</p>
                    : chatMessages.map((message) => <div key={message.message_id} className={message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}><strong>{message.role === 'user' ? 'Вы' : 'Ответ AI'}</strong>{message.role === 'assistant' && message.statement_type && <span className="detail-claim-type">{statementLabel[message.statement_type]}</span>}<p>{message.content}</p>{message.evidence_ids && <EvidenceLinks ids={message.evidence_ids} sources={analysis.result!.sources} />}{message.bank_opinion && <div className="detail-chat-bank"><strong>Подтверждённая позиция Альфа-Банка</strong><p>{message.bank_opinion.text}</p><span className="detail-source-note">Документ {message.bank_opinion.document_id}, стр. {message.bank_opinion.page}. Цитата: «{message.bank_opinion.quote}»</span><EvidenceLinks ids={message.bank_opinion.evidence_ids} sources={analysis.result!.sources} /></div>}</div>)}
                </div>
                {chatError && <p className="detail-chat-error" role="alert">{chatError}</p>}
                <label htmlFor="analysis-question">Ваш вопрос</label>
                <div className="detail-chat-composer"><input id="analysis-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Спросите о влиянии новости" maxLength={10000} /><button type="submit" disabled={chatLoading || chatHistoryLoading || !question.trim()}>{chatLoading ? 'Отправка…' : 'Спросить'}</button></div>
                {analysis.disclaimer && <p className="detail-disclaimer">{analysis.disclaimer}</p>}
              </form>}
            </div>
          </>}
        </section>
      </div>}
    </div>
  );
}
