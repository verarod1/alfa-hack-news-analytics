import { MOCK_COMPANIES, MOCK_ROLES } from '../mocks/companies';
import type { ChatMessage, CompanyProfile } from '../types/api';

const profileKey = 'alfa-news-demo:profile:v1';
const conversationKey = (companyId: string, roleCode: string, analysisId: string) =>
  `alfa-news-demo:chat:v1:${encodeURIComponent(companyId)}:${encodeURIComponent(roleCode)}:${encodeURIComponent(analysisId)}`;

export interface DemoSession {
  company: CompanyProfile;
  roleCode: string;
  roleName: string;
}

export interface DemoConversation {
  conversationId: string | null;
  messages: ChatMessage[];
}

function readJson(key: string): unknown {
  try {
    const value = sessionStorage.getItem(key);
    return value ? JSON.parse(value) as unknown : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Демо остаётся доступным, даже если браузер запретил sessionStorage.
  }
}

export function loadDemoSession(): DemoSession | null {
  const saved = readJson(profileKey);
  if (!saved || typeof saved !== 'object') return null;
  const { companyId, roleCode } = saved as Record<string, unknown>;
  const company = MOCK_COMPANIES.find((item) => item.id === companyId);
  const role = MOCK_ROLES.find((item) => item.code === roleCode);
  return company && role ? { company, roleCode: role.code, roleName: role.name } : null;
}

export function saveDemoSession(session: DemoSession): void {
  writeJson(profileKey, { companyId: session.company.id, roleCode: session.roleCode });
}

export function clearDemoSession(): void {
  try {
    sessionStorage.removeItem(profileKey);
  } catch {
    // Если хранилище недоступно, состояние React уже будет сброшено.
  }
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== 'object') return false;
  const message = value as Record<string, unknown>;
  return typeof message.message_id === 'string'
    && (message.role === 'user' || message.role === 'assistant')
    && typeof message.content === 'string'
    && typeof message.created_at === 'string'
    && (message.evidence_ids === undefined
      || (Array.isArray(message.evidence_ids) && message.evidence_ids.every((id) => typeof id === 'string')));
}

// Временное демо-хранилище: ключ включает компанию, роль и конкретный разбор.
// TODO: После MVP замените чтение переписки на GET /api/v1/analyses/{analysis_id}/messages.
// Для продолжения прежнего диалога согласуйте возврат conversation_id вместе с историей.
export function loadDemoConversation(companyId: string, roleCode: string, analysisId: string): DemoConversation | null {
  const saved = readJson(conversationKey(companyId, roleCode, analysisId));
  if (!saved || typeof saved !== 'object') return null;
  const { conversationId, messages } = saved as Record<string, unknown>;
  if ((conversationId !== null && typeof conversationId !== 'string')
    || !Array.isArray(messages) || !messages.every(isChatMessage)) return null;
  return { conversationId, messages };
}

// TODO: После MVP не сохраняйте сообщения в браузере; POST /api/v1/chat/messages должен
// сохранять обе стороны диалога на сервере, а фронтенд — получать историю через GET /messages.
export function saveDemoConversation(companyId: string, roleCode: string, analysisId: string, conversation: DemoConversation): void {
  writeJson(conversationKey(companyId, roleCode, analysisId), conversation);
}
