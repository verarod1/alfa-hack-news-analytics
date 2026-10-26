import type { ChatHistoryResponse, ChatMessage, ChatResponse } from '../types/api';

const messagesByAnalysis = new Map<string, ChatMessage[]>();
let nextMessageId = 1;

// Структура соответствует GET /analyses/{analysis_id}/messages; данные живут только до перезагрузки страницы.
export function mockChatHistory(analysisId: string, limit = 20, offset = 0): ChatHistoryResponse {
  const messages = messagesByAnalysis.get(analysisId) ?? [];
  return {
    analysis_id: analysisId,
    items: messages.slice(offset, offset + limit),
    total: messages.length,
    limit,
    offset,
  };
}

// Структура ответа соответствует POST /chat/messages.
export function mockChatMessage(analysisId: string, conversationId: string | null, message: string): ChatResponse {
  const messages = messagesByAnalysis.get(analysisId) ?? [];
  const now = new Date().toISOString();
  // Метка времени не даёт ID совпасть с сохранёнными сообщениями после обновления страницы.
  const userId = `msg_demo_${Date.now()}_${nextMessageId++}`;
  const assistantId = `msg_demo_${Date.now()}_${nextMessageId++}`;
  const answer = 'Демонстрационный ответ. Для обоснованного вывода нужны подтверждённые данные компании и источники новости.';
  messages.push(
    { message_id: userId, role: 'user', content: message, created_at: now },
    { message_id: assistantId, role: 'assistant', content: answer, evidence_ids: [], created_at: now },
  );
  messagesByAnalysis.set(analysisId, messages);
  return {
    conversation_id: conversationId ?? `chat_demo_${analysisId}`,
    message_id: assistantId,
    answer,
    evidence_ids: [],
    status: 'completed',
  };
}
