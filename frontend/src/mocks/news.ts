import type { AnalysisResponse, AnalysisTrace, FeedItem, FeedResponse, NewsDetail } from '../types/api';
import { MOCK_COMPANIES } from './companies';

const source = { id: 'src_demo', name: 'Демо-источник', url: 'https://example.com/article' };

// Данные демонстрационные: заголовки не представляют реальные публикации.
export const MOCK_FEED_ITEMS: FeedItem[] = [
  {
    id: 'news_001',
    title: 'Условия финансирования отрасли могут измениться',
    published_at: '2026-10-20T12:00:00+03:00',
    source,
    relevance_score: 0.89,
    impact_type: 'risk',
    impact_level: 'high',
    short_insight: 'Возможен рост стоимости заёмного финансирования. Оцените действующие кредитные условия.',
    relevance_reasons: ['Отрасль компании', 'Финансовые условия'],
    analysis_id: 'analysis_001',
  },
  {
    id: 'news_002',
    title: 'Возможный рост спроса в отрасли',
    published_at: '2026-10-18T10:30:00+03:00',
    source: { ...source, id: 'src_demo_2', url: 'https://example.com/demand' },
    relevance_score: 0.82,
    impact_type: 'opportunity',
    impact_level: 'medium',
    short_insight: 'Рост спроса может увеличить число заказов; потребность в мощностях стоит проверить.',
    relevance_reasons: ['Отрасль компании'],
    analysis_id: 'analysis_002',
  },
  {
    id: 'news_003',
    title: 'Изменения логистических маршрутов',
    published_at: '2026-10-16T09:00:00+03:00',
    source: { ...source, id: 'src_demo_3', url: 'https://example.com/logistics' },
    relevance_score: 0.76,
    impact_type: 'risk',
    impact_level: 'medium',
    short_insight: 'Возможны задержки поставок и рост затрат на доставку.',
    relevance_reasons: ['Логистические связи'],
    analysis_id: null,
  },
];

const otherCompanyFeeds: Record<string, FeedItem[]> = {
  U_31044: [
    {
      id: 'news_logistics_001', title: 'Изменение маршрутов перевозок может увеличить сроки доставки',
      published_at: '2026-10-20T11:00:00+03:00',
      source: { id: 'src_demo_logistics_1', name: 'Демо-источник', url: 'https://example.com/logistics-routes' },
      relevance_score: 0.91, impact_type: 'risk', impact_level: 'high',
      short_insight: 'Проверьте запас времени в цепочке поставок и условия договоров с перевозчиками.',
      relevance_reasons: ['Логистика компании'], analysis_id: 'analysis_logistics_001',
    },
    {
      id: 'news_logistics_002', title: 'В регионе обсуждают расширение распределительных мощностей',
      published_at: '2026-10-18T10:30:00+03:00',
      source: { id: 'src_demo_logistics_2', name: 'Демо-источник', url: 'https://example.com/distribution' },
      relevance_score: 0.79, impact_type: 'opportunity', impact_level: 'medium',
      short_insight: 'Новые мощности могут сократить плечо доставки; доступность площадок нужно уточнить.',
      relevance_reasons: ['Регион компании'], analysis_id: 'analysis_logistics_002',
    },
  ],
  U_55912: [
    {
      id: 'news_construction_001', title: 'Возможное изменение стоимости строительных материалов',
      published_at: '2026-10-20T09:30:00+03:00',
      source: { id: 'src_demo_construction_1', name: 'Демо-источник', url: 'https://example.com/materials' },
      relevance_score: 0.90, impact_type: 'risk', impact_level: 'high',
      short_insight: 'Проверьте сметы действующих проектов и условия фиксации цен у поставщиков.',
      relevance_reasons: ['Строительная отрасль'], analysis_id: 'analysis_construction_001',
    },
    {
      id: 'news_construction_002', title: 'Планируются новые инвестиционные проекты в строительстве',
      published_at: '2026-10-17T12:00:00+03:00',
      source: { id: 'src_demo_construction_2', name: 'Демо-источник', url: 'https://example.com/projects' },
      relevance_score: 0.81, impact_type: 'opportunity', impact_level: 'medium',
      short_insight: 'Возможен дополнительный спрос; оцените свободные мощности и условия участия.',
      relevance_reasons: ['Строительная отрасль'], analysis_id: 'analysis_construction_002',
    },
  ],
};

const allMockItems = [...MOCK_FEED_ITEMS, ...Object.values(otherCompanyFeeds).flat()];

export function mockFeed(companyId: string, limit = 20, offset = 0, impactType?: 'risk' | 'opportunity'): FeedResponse {
  const companyItems = otherCompanyFeeds[companyId] ?? MOCK_FEED_ITEMS;
  const filtered = impactType
    ? companyItems.filter((item) => item.impact_type === impactType)
    : companyItems;
  return { items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset };
}

export function mockNews(newsId: string): NewsDetail {
  const item = allMockItems.find((entry) => entry.id === newsId);
  if (!item) throw new Error('Новость не найдена');
  return {
    id: item.id,
    title: item.title,
    text: item.short_insight ?? 'Текст новости пока недоступен.',
    published_at: item.published_at,
    source: item.source,
    created_at: item.published_at,
  };
}

export function mockAnalysis(analysisId: string, companyId: string, role: string, newsId?: string): AnalysisResponse {
  const item = allMockItems.find((entry) => entry.analysis_id === analysisId || entry.id === newsId);
  if (!item) throw new Error('Разбор не найден');
  const company = MOCK_COMPANIES.find((entry) => entry.id === companyId);
  const concern = item.short_insight ?? 'Оцените возможное влияние события на компанию.';
  return {
    analysis_id: analysisId,
    status: 'completed',
    company_id: companyId,
    news_id: item.id,
    role,
    result: {
      what_happened: item.title,
      why_important: concern,
      impact_type: item.impact_type,
      impact_level: item.impact_level,
      importance: 'important',
      confidence: 'medium',
      company_factors: company ? [
        { field: 'industry.name', value: company.industry.name, impact: 'Отрасль компании учитывается при оценке значимости события.' },
        ...(company.bank_products.loan && item.id === 'news_001'
          ? [{ field: 'bank_products.loan', value: true, impact: 'Наличие кредитного продукта повышает значимость изменения условий финансирования.' }]
          : []),
      ] : [],
      analyzed_news_ids: [item.id],
      risks: item.impact_type === 'risk' ? [{ id: `risk_${item.id}`, text: concern, severity: item.impact_level, evidence_ids: [`e_${item.id}`] }] : [],
      opportunities: item.impact_type === 'opportunity' ? [{ id: `opportunity_${item.id}`, text: concern, severity: item.impact_level, evidence_ids: [`e_${item.id}`] }] : [],
      bank_opinion: null,
      recommended_actions: [{ text: item.impact_type === 'risk' ? 'Проверьте влияние возможных изменений на текущие планы и договоры.' : 'Проверьте спрос, доступные мощности и потребность в оборотных средствах.', basis_ids: [item.impact_type === 'risk' ? `risk_${item.id}` : `opportunity_${item.id}`] }],
      sources: [{ id: `e_${item.id}`, type: 'news', title: item.title, url: item.source.url, published_at: item.published_at }],
      limitations: ['Демонстрационные данные. Вывод требует проверки по реальным источникам.'],
    },
  };
}

export function mockAnalysisTrace(analysisId: string): AnalysisTrace {
  return {
    analysis_id: analysisId,
    steps: [
      {
        order: 1,
        name: 'retrieve_company_profile',
        status: 'completed',
        model: null,
        tool: 'get_company_profile',
        summary: 'Учтён демонстрационный профиль компании и выбранная роль.',
        source_ids: [],
        validation: { performed: true, passed: true },
      },
      {
        order: 2,
        name: 'analyze_news',
        status: 'completed',
        model: null,
        tool: 'mock_analysis',
        summary: 'Сформирован демонстрационный вывод по новости.',
        source_ids: [`e_${analysisId.replace('analysis_demo_', '').replace('analysis_', 'news_')}`],
        validation: { performed: false, passed: null },
      },
    ],
  };
}
