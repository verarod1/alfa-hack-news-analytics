// src/components/DemoLaunchpad.tsx
import React, { useState, useEffect } from 'react';
import type { CompanyProfile, RoleItem } from '../types/api';
import { formatRevenue, formatCompanyProducts } from '../mocks/companies';
import { getCompanyById, getDemoProfiles, getRoles } from '../api/service';

interface DemoLaunchpadProps {
  onSelectProfile?: (company: CompanyProfile, roleCode: string, roleName: string) => void;
  themeControl?: React.ReactNode;
}

export const DemoLaunchpad: React.FC<DemoLaunchpadProps> = ({ onSelectProfile, themeControl }) => {
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [initialCompanies, setInitialCompanies] = useState<CompanyProfile[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);

  const [selectedRoles, setSelectedRoles] = useState<Record<string, string>>({});

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getDemoProfiles(), getRoles()])
      .then(async ([profiles, roleResponse]) => {
        const ids = [...new Set(profiles.items.map((item) => item.company_id))];
        const loaded = await Promise.all(ids.map(getCompanyById));
        if (!active) return;
        setCompanies(loaded);
        setInitialCompanies(loaded);
        setRoles(roleResponse.items);
        setSelectedRoles(Object.fromEntries(profiles.items.map((item) => [item.company_id, item.role])));
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить профили'); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  const handleRoleChange = (companyId: string, newRoleCode: string) => {
    setSelectedRoles((prev) => ({
      ...prev,
      [companyId]: newRoleCode,
    }));
  };

  const handleEnterService = (company: CompanyProfile) => {
    const roleCode = selectedRoles[company.id] || roles[0]?.code || 'ceo';
    const roleObj = roles.find((r) => r.code === roleCode);
    const roleName = roleObj ? roleObj.name : 'Генеральный директор';

    if (onSelectProfile) {
      onSelectProfile(company, roleCode, roleName);
    }
  };

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuery = searchQuery.trim();
    setError(null);

    if (!trimmedQuery) {
      setCompanies(initialCompanies);
      return;
    }

    setIsLoading(true);
    try {
      const foundCompany = await getCompanyById(trimmedQuery);
      setCompanies([foundCompany]);
      setSelectedRoles((prev) => {
        const next = { ...prev };
        if (!next[foundCompany.id]) next[foundCompany.id] = roles[0]?.code || 'ceo';
        return next;
      });
    } catch (reason) {
      setCompanies([]);
      setError(reason instanceof Error ? reason.message : 'Компания не найдена');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetSearch = () => {
    setSearchQuery('');
    setError(null);
    setCompanies(initialCompanies);
  };

  return (
    <div className="launchpad-page">
      <header className="launchpad-header">
        <div className="header-left">
          <span className="alfa-logo" aria-label="Альфа-Бизнес">
            <span className="alfa-logo-letter">А</span>
            <span className="alfa-logo-underline" />
          </span>
          <span className="header-divider" aria-hidden="true" />
          <nav className="header-breadcrumbs" aria-label="Хлебные крошки">
            <span className="breadcrumb-muted">Альфа-Бизнес / </span>
            <span className="breadcrumb-active">Персональная аналитика</span>
          </nav>
        </div>

        <div className="header-right">
          {themeControl}
          <span className="demo-stand-badge">ДЕМО-СТЕНД</span>
        </div>
      </header>

      <main className="launchpad-main">
        <div className="launchpad-container">
          <h1 className="launchpad-title">Выбор профиля для демонстрации</h1>
          <p className="launchpad-subtitle">
            Выберите компанию и роль для просмотра новостной аналитики
          </p>

          {error && (
            <div className="status-banner status-banner--error" role="alert">
              <span>{error}</span>
              <button
                type="button"
                className="status-banner-reset"
                onClick={handleResetSearch}
              >
                Сбросить
              </button>
            </div>
          )}

          {isLoading && (
            <div className="status-banner status-banner--loading">
              Загрузка данных профиля...
            </div>
          )}

          <section className="companies-grid" aria-label="Список компаний">
            {companies.map((company) => {
              const currentRole = selectedRoles[company.id] || roles[0]?.code || 'ceo';

              return (
                <article key={company.id} className="company-card">
                  <div className="company-card-header">
                    <h2 className="company-name">{company.company_name}</h2>
                    <div className="company-id">ID: {company.id}</div>
                  </div>

                  <ul className="company-params-list">
                    <li className="company-param-row">
                      <span className="param-label">
                        <span className="param-bullet" aria-hidden="true">•</span>
                        Отрасль
                      </span>
                      <span className="param-value">{company.industry.name}</span>
                    </li>
                    <li className="company-param-row">
                      <span className="param-label">
                        <span className="param-bullet" aria-hidden="true">•</span>
                        Выручка
                      </span>
                      <span className="param-value">{formatRevenue(company.revenue)}</span>
                    </li>
                    <li className="company-param-row">
                      <span className="param-label">
                        <span className="param-bullet" aria-hidden="true">•</span>
                        Продукты
                      </span>
                      <span className="param-value">{formatCompanyProducts(company)}</span>
                    </li>
                    <li className="company-param-row">
                      <span className="param-label">
                        <span className="param-bullet" aria-hidden="true">•</span>
                        Регион
                      </span>
                      <span className="param-value">{company.region}</span>
                    </li>
                  </ul>

                  <div className="company-card-footer">
                    <label
                      htmlFor={`role-select-${company.id}`}
                      className="role-select-label"
                    >
                      Роль пользователя
                    </label>
                    <div className="role-select-wrapper">
                      <select
                        id={`role-select-${company.id}`}
                        className="role-select"
                        value={currentRole}
                        onChange={(e) => handleRoleChange(company.id, e.target.value)}
                      >
                        {roles.map((role) => (
                          <option key={role.code} value={role.code}>
                            {role.name}
                          </option>
                        ))}
                      </select>
                      <svg
                        className="role-select-chevron"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </div>

                    <button
                      type="button"
                      className="enter-service-btn"
                      onClick={() => handleEnterService(company)}
                      disabled={isLoading}
                    >
                      Открыть Альфа-Бизнес
                    </button>
                  </div>
                </article>
              );
            })}
          </section>

          <form className="search-bar-form" onSubmit={handleSearchSubmit}>
            <div className="search-input-container">
              <svg
                className="search-icon"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="search-input"
                placeholder="Поиск компании по ID из базы данных..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Поиск компании по ID из базы данных"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="search-clear-btn"
                  onClick={handleResetSearch}
                  title="Очистить поиск"
                  aria-label="Очистить поиск"
                >
                  ×
                </button>
              )}
            </div>
            <button type="submit" className="search-submit-btn" disabled={isLoading}>
              Найти
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};
