import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { getAnalysisForNews, getAnalysisTrace, getChatHistory, getFeed, getNews, getRoles, isMockApi, sendChatMessage } from '../api/service';
import type { AnalysisResponse, AnalysisResult, AnalysisStatus, AnalysisTrace, ChatMessage, CompanyProfile, FeedItem, NewsDetail, RoleItem } from '../types/api';
import { loadDemoConversation, saveDemoConversation } from '../utils/demoStorage';

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
    const label = source?.title ?? source?.document_title ?? id;
    return <span key={id}>{index > 0 ? ', ' : ''}{source?.url
      ? <a href={source.url} target="_blank" rel="noopener noreferrer">{label}</a>
      : label}</span>;
  })}</span>;
}

export function AnalyticsScreen({ session, onExit, onHome, onChangeRole, themeControl }: Props) {
  const { company, roleCode, roleName } = session;
  const [filter, setFilter] = useState<Filter>('all');
  const [roles, setRoles] = useState<RoleItem[]>([{ code: roleCode, name: roleName }]);
  const [reload, setReload] = useState(0);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<FeedItem | null>(null);
  const [news, setNews] = useState<NewsDetail | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [trace, setTrace] = useState<AnalysisTrace | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [detailTab, setDetailTab] = useState<DetailTab>('analysis');
  const [detailError, setDetailError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatStorageScope, setChatStorageScope] = useState<{ companyId: string; roleCode: string; analysisId: string } | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const detailRequest = useRef(0);
  const detailAbort = useRef<AbortController | null>(null);

  const closeDetail = () => {
    detailRequest.current += 1;
    detailAbort.current?.abort();
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
    getFeed(company.id, roleCode, filter === 'all' ? undefined : filter)
      .then((response) => { if (active) setItems(response.items); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить ленту'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [company.id, roleCode, filter, reload]);

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
    setTrace(null);
    setChatMessages([]);
    setDetailTab('analysis');
    setDetailError(null);
    setChatError(null);
    setQuestion('');
    setConversationId(null);
    setChatStorageScope(null);
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
        if (analysisData.status === 'completed') {
          // TODO: После MVP реальный режим должен загружать историю через GET /messages.
          // Добавьте conversation_id в ответ истории, чтобы продолжать тот же диалог после перезагрузки.
          void getAnalysisTrace(analysisData.analysis_id, controller.signal)
            .then((data) => { if (requestId === detailRequest.current) setTrace(data); })
            .catch(() => { /* Разбор доступен и без необязательной трассировки. */ });
          if (isMockApi) {
            const saved = loadDemoConversation(company.id, roleCode, analysisData.analysis_id);
            setChatMessages(saved?.messages ?? []);
            setConversationId(saved?.conversationId ?? null);
            setChatStorageScope({ companyId: company.id, roleCode, analysisId: analysisData.analysis_id });
          } else {
            void getChatHistory(analysisData.analysis_id, 20, 0, controller.signal)
              .then((data) => {
                if (requestId !== detailRequest.current) return;
                setChatMessages((current) => {
                  const loadedIds = new Set(data.items.map((message) => message.message_id));
                  return [...data.items, ...current.filter((message) => !loadedIds.has(message.message_id))];
                });
              })
              .catch(() => { /* История может быть недоступна, новый вопрос всё ещё можно задать. */ });
          }
        }
      }
    } catch (reason) {
      if (requestId === detailRequest.current && !controller.signal.aborted) setDetailError(reason instanceof Error ? reason.message : 'Не удалось открыть разбор');
    }
  };

  const askQuestion = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim() || !analysis || analysis.status !== 'completed') return;
    const sentQuestion = question.trim();
    setChatLoading(true);
    setChatError(null);
    try {
      const response = await sendChatMessage(analysis.analysis_id, conversationId, sentQuestion);
      setConversationId(response.conversation_id);
      const createdAt = new Date().toISOString();
      setChatMessages((current) => [...current,
        { message_id: `local_user_${response.message_id}`, role: 'user', content: sentQuestion, created_at: createdAt },
        { message_id: response.message_id, role: 'assistant', content: response.answer, evidence_ids: response.evidence_ids, created_at: createdAt },
      ]);
      setQuestion('');
    } catch (reason) {
      setChatError(reason instanceof Error ? reason.message : 'Не удалось отправить вопрос');
    } finally {
      setChatLoading(false);
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
            <div className="analytics-company-details"><strong>{company.company_name}</strong><p>{company.industry.name} · {company.region}</p></div>
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
            {!loading && !error && items.length === 0 && <p className="analytics-state">По этому фильтру событий пока нет.</p>}
            {!loading && !error && <div className="analytics-grid">
              {items.map((item) => <article className="analytics-event" key={item.id}>
                <time dateTime={item.published_at}>{dateFormat.format(new Date(item.published_at))}</time>
                <span className={`analytics-pill analytics-pill--${item.impact_type}`}>{impactLabel[item.impact_type]}</span>
                <h3>{item.title}</h3>
                <p>{item.short_insight ?? 'Персональный вывод ещё готовится.'}</p>
                <div className="analytics-event-footer"><button type="button" onClick={() => void openDetail(item)}>{item.analysis_id ? 'Открыть разбор' : 'Разобрать новость'} <span aria-hidden="true">→</span></button></div>
              </article>)}
            </div>}
          </section>
        </div>
      </main>
      {selected && <div className="detail-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDetail(); }}>
        <section className="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="detail-title" aria-busy={!news && !detailError}>
          <div className="detail-header"><div><span className={`analytics-pill analytics-pill--${selected.impact_type}`}>{impactLabel[selected.impact_type]}</span><h2 id="detail-title">{selected.title}</h2></div><button ref={closeButton} type="button" className="detail-close" onClick={closeDetail} aria-label="Закрыть разбор">×</button></div>
          {!news && !detailError && <DetailLoading status={analysisStatus} />}
          {detailError && <div role="alert" className="detail-error"><p>{detailError}</p><button type="button" onClick={() => void openDetail({ ...selected, analysis_id: null })}>Повторить разбор</button></div>}
          {news && <>
            <p className="detail-meta">{dateFormat.format(new Date(news.published_at))} · {news.source.name}</p>
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
              <div className="detail-section"><h3>Что произошло</h3><p>{analysis?.result?.what_happened ?? news.text}</p></div>
              {analysis?.result ? <>
                <div className="detail-section"><h3>Почему это важно для компании</h3><p>{analysis.result.why_important}</p></div>
                {analysis.result.company_factors.length > 0 && <div className="detail-section"><h3>Учтённые данные компании</h3><ul>{analysis.result.company_factors.map((factor) => <li key={factor.field}><strong>{factorLabels[factor.field] ?? factor.field}</strong>: {formatFactorValue(factor.value)} — {factor.impact}</li>)}</ul></div>}
                {(analysis.result.risks.length > 0 || analysis.result.opportunities.length > 0) && <div className="detail-section"><h3>Риски и возможности</h3><ul>{analysis.result.risks.map((risk) => <li key={risk.id}>{risk.text}<EvidenceLinks ids={risk.evidence_ids} sources={analysis.result!.sources} /></li>)}{analysis.result.opportunities.map((opportunity) => <li key={opportunity.id}>{opportunity.text}<EvidenceLinks ids={opportunity.evidence_ids} sources={analysis.result!.sources} /></li>)}</ul></div>}
                <div className="detail-section"><h3>Позиция Альфа-Банка</h3>{analysis.result.bank_opinion
                  ? <><p>{analysis.result.bank_opinion.text}</p><p className="detail-source-note">Документ {analysis.result.bank_opinion.document_id}, стр. {analysis.result.bank_opinion.page}. Цитата: «{analysis.result.bank_opinion.quote}»</p></>
                  : <p>Подтверждённая позиция банка по этому событию пока недоступна.</p>}</div>
                <div className="detail-section detail-recommendations"><h3>Рекомендуемые действия</h3><ul>{analysis.result.recommended_actions.map((action, index) => <li key={index}>{action.text}</li>)}</ul></div>
                <div className="detail-section"><h3>Источники и ограничения</h3><ul>{analysis.result.sources.map((source) => <li key={source.id}>{source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title ?? source.url}</a> : source.document_title}</li>)}{analysis.result.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></div>
                {trace && <details className="detail-section detail-trace"><summary>Как получен вывод</summary><ol>{trace.steps.map((step) => <li key={step.order}>{step.summary}</li>)}</ol></details>}
              </> : <p className="detail-section">Разбор ещё не готов.</p>}
            </div>
            <div id="detail-panel-chat" role="tabpanel" aria-labelledby="detail-tab-chat" hidden={detailTab !== 'chat'}>
              {analysis?.result && <form className="detail-chat" onSubmit={(event) => void askQuestion(event)}>
                <p className="detail-chat-intro">Задайте вопрос о том, как эта новость влияет на вашу компанию.</p>
                <div className="detail-chat-history" aria-live="polite">
                  {chatMessages.length === 0
                    ? <p className="detail-chat-empty">Здесь появится обсуждение новости. Начните с вопроса по разбору.</p>
                    : chatMessages.map((message) => <p key={message.message_id} className={message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}><strong>{message.role === 'user' ? 'Вы' : 'Аналитика'}</strong> {message.content}{message.evidence_ids && <EvidenceLinks ids={message.evidence_ids} sources={analysis.result!.sources} />}</p>)}
                </div>
                {chatError && <p className="detail-chat-error" role="alert">{chatError}</p>}
                <label htmlFor="analysis-question">Ваш вопрос</label>
                <div className="detail-chat-composer"><input id="analysis-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Спросите о влиянии новости" /><button type="submit" disabled={chatLoading || !question.trim()}>{chatLoading ? 'Отправка…' : 'Спросить'}</button></div>
              </form>}
            </div>
          </>}
        </section>
      </div>}
    </div>
  );
}
