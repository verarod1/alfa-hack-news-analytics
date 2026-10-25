import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { getRoles } from '../api/service';
import type { RoleItem } from '../types/api';
import type { DemoSession } from '../utils/demoStorage';
import './BankHome.css';

interface Props {
  session: DemoSession;
  onOpenAnalytics: () => void;
  onChangeProfile: () => void;
  onChangeRole: (roleCode: string, roleName: string) => void;
  themeControl: ReactNode;
}

const mainLinks = [
  { icon: '↔', label: 'Платежи в работе' },
  { icon: '▤', label: 'Реестры платежей' },
  { icon: '▣', label: 'Выписка' },
  { icon: '▤', label: 'Счета' },
  { icon: '♟', label: 'Контрагенты' },
];

const serviceLinks = [
  { icon: '%', label: 'Кредитные продукты' },
  { icon: '▣', label: 'Депозиты', badge: 'НОВОЕ' },
  { icon: '◉', label: 'ВЭД' },
];

const extraLinks = [
  { icon: '▦', label: 'Бухгалтерия' },
  { icon: '♜', label: 'Госзакупки' },
  { icon: '▰', label: 'Зарплатный проект' },
];

const shortcuts = [
  { icon: '✦', label: 'Платёж по шаблону' },
  { icon: '▣', label: 'Сформировать выписку' },
  { icon: '1C', label: 'Импорт платежей из 1С' },
  { icon: '✚', label: 'Выставить счёт' },
  { icon: '◉', label: 'Предоставить сведения о ВО' },
];

const tasks = [
  { label: 'Оплатить', count: '1', urgent: true },
  { label: 'Подписать', count: '7' },
  { label: 'Отправить', count: '7' },
  { label: 'Доработать', count: '4' },
  { label: 'Отклонённые', count: '7' },
  { label: 'Черновики', count: '5' },
  { label: 'В работе у банка', count: '8' },
];

// TODO: При встраивании в действующий Альфа-Бизнес этот демонстрационный
// банковский каркас заменяется его шапкой, меню и блоками счетов/операций.
// В реальном меню и на главной нужно сохранить обе точки входа в аналитику.
export function BankHome({ session, onOpenAnalytics, onChangeProfile, onChangeRole, themeControl }: Props) {
  const [roles, setRoles] = useState<RoleItem[]>([{ code: session.roleCode, name: session.roleName }]);

  useEffect(() => {
    let active = true;
    // TODO: getRoles() уже переключается на GET /api/v1/roles при VITE_USE_MOCK_API=false.
    // Backend должен отдавать только роли, разрешённые текущему пользователю.
    getRoles().then((response) => {
      if (active && response.items.length > 0) setRoles(response.items);
    }).catch(() => { /* При ошибке остаётся текущая роль. */ });
    return () => { active = false; };
  }, []);

  return <div className="bank-home-page">
    <header className="bank-home-header">
      <div className="bank-home-brand"><span className="bank-home-brandmark" aria-hidden="true">А</span><strong>Альфа-Бизнес</strong></div>
      <div className="bank-home-toolbar">
        <span className="bank-home-search"><span aria-hidden="true">⌕</span> Поиск</span>
        <span className="bank-home-toolbar-divider" aria-hidden="true" />
        <span className="bank-home-toolbar-icon" aria-hidden="true">▦</span>
        <span className="bank-home-toolbar-icon" aria-hidden="true">✉</span>
        <span className="bank-home-toolbar-icon" aria-hidden="true">◆</span>
        <span className="bank-home-toolbar-divider" aria-hidden="true" />
        <div className="bank-home-profile"><strong>{session.company.company_name}</strong><small>Текущая компания</small></div>
        <label className="bank-home-role-control" htmlFor="bank-home-role"><span>Роль</span><select id="bank-home-role" value={session.roleCode} onChange={(event) => {
          const role = roles.find((item) => item.code === event.target.value);
          if (role) onChangeRole(role.code, role.name);
        }}>{roles.map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}</select></label>
        <button type="button" className="bank-home-change-profile" onClick={onChangeProfile}>Сменить компанию</button>
        {themeControl}
        <span className="bank-home-demo-tag">Демо</span>
      </div>
    </header>

    <div className="bank-home-layout">
      <aside className="bank-home-sidebar" aria-label="Меню Альфа-Бизнеса">
        <div className="bank-home-new-payment"><span aria-hidden="true">+</span> Новый платёж</div>
        <div className="bank-home-sidebar-list" aria-label="Банковские разделы">
          {mainLinks.map((item) => <div className="bank-home-sidebar-row" key={item.label}><span aria-hidden="true">{item.icon}</span>{item.label}</div>)}
        </div>
        <div className="bank-home-sidebar-heading"><h2>Мои сервисы</h2><span aria-hidden="true">+</span></div>
        <button type="button" className="bank-home-analytics-link" onClick={onOpenAnalytics}><span className="bank-home-link-icon" aria-hidden="true">✦</span> Персональная аналитика</button>
        <div className="bank-home-sidebar-list" aria-label="Другие сервисы">
          {serviceLinks.map((item) => <div className="bank-home-sidebar-row" key={item.label}><span aria-hidden="true">{item.icon}</span>{item.label}{item.badge && <small>{item.badge}</small>}</div>)}
        </div>
        <div className="bank-home-sidebar-rule" />
        <div className="bank-home-sidebar-list bank-home-sidebar-secondary">
          {extraLinks.map((item) => <div className="bank-home-sidebar-row" key={item.label}><span aria-hidden="true">{item.icon}</span>{item.label}</div>)}
        </div>
        <div className="bank-home-sidebar-bottom"><span>🛒<small>Все сервисы</small></span><span>Ⓐ<small>Кэшбэк</small></span></div>
      </aside>

      <main className="bank-home-main">
        <div className="bank-home-shortcuts" aria-label="Быстрые действия">
          {shortcuts.map((item) => <div className="bank-home-shortcut" key={item.label}><span className="bank-home-shortcut-icon" aria-hidden="true">{item.icon}</span><strong>{item.label}</strong></div>)}
          <div className="bank-home-shortcut-more" aria-hidden="true"><span>+</span><span>⌄</span></div>
        </div>

        <section className="bank-home-tasks" aria-label="Статусы документов">
          {tasks.map((item) => <div className="bank-home-task" key={item.label}><span>{item.label}</span><strong className={item.urgent ? 'is-urgent' : ''}>{item.count}</strong></div>)}
        </section>

        <section className="bank-home-analytics-card" aria-labelledby="bank-home-analytics-title">
          <span className="bank-home-analytics-mark" aria-hidden="true">✦</span>
          <div><span className="bank-home-analytics-eyebrow">НОВОСТИ ДЛЯ ВАШЕГО БИЗНЕСА</span><h2 id="bank-home-analytics-title">Персональная аналитика</h2><p>Риски и возможности с учётом вашей компании и роли</p></div>
          <button type="button" onClick={onOpenAnalytics}>Перейти к новостям <span aria-hidden="true">→</span></button>
        </section>

        <div className="bank-home-summary">
          <section className="bank-home-account-card" aria-label="Демонстрационный вид счёта">
            <div className="bank-home-balance">
              <span>Рублёвый счёт <span className="bank-home-edit" aria-hidden="true">✎</span></span>
              <strong>207 590,00 ₽</strong>
              <small>•••• •••• •••• 9876</small>
              <div className="bank-home-own-funds">Свои деньги: <b>107 590,00 ₽</b></div>
            </div>
            <div className="bank-home-credit"><span>КРЕДИТ ДЛЯ БИЗНЕСА</span><strong><i aria-hidden="true">+</i> 5 000 000 ₽</strong><small>1,9% — на весь срок</small></div>
            <div className="bank-home-card-mini"><span className="bank-home-mini-logo">А</span><span>Альфа-Бизнес<br />••5123</span></div>
            <div className="bank-home-account-footer"><span>Скопировать реквизиты</span><span>Тариф Удачный выбор</span></div>
          </section>
          <aside className="bank-home-promos" aria-label="Демонстрационные баннеры">
            <div className="bank-home-promo bank-home-promo-blue"><strong>Закажите карту</strong><p>Для ежедневных задач вашего бизнеса</p><span aria-hidden="true">▰</span></div>
            <div className="bank-home-promo bank-home-promo-peach"><strong>Деньги сверху</strong><p>Бонусы за привычные операции</p><span aria-hidden="true">✦</span></div>
          </aside>
        </div>

        <section className="bank-home-operations" aria-labelledby="bank-home-operations-title">
          <div className="bank-home-operations-head"><h2 id="bank-home-operations-title">История операций</h2><span aria-hidden="true">⌃</span></div>
          <div className="bank-home-operations-filters">
            <div className="bank-home-date"><span aria-hidden="true">‹</span> Сегодня <span aria-hidden="true">› ▦</span></div>
            <div className="bank-home-operation-search">Название контрагента, ИНН или КПП <span aria-hidden="true">⌕</span></div>
          </div>
          <div className="bank-home-operation-tools"><div><span>☷</span><span>Входящие</span><span>Исходящие</span><span>Тип платежа ⌄</span><span>Карта ⌄</span><span>Сумма ⌄</span></div><div><span>Скачать ОСВ</span><span className="bank-home-operation-download">Скачать выписку</span></div></div>
          <div className="bank-home-operation-placeholders" aria-hidden="true"><span /><span /><span /><span /></div>
        </section>
      </main>
    </div>
  </div>;
}
