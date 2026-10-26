// src/App.tsx
import { useEffect, useState } from 'react';
import { DemoLaunchpad } from './components/DemoLaunchpad';
import { AnalyticsScreen } from './components/AnalyticsScreen';
import { BankHome } from './components/BankHome';
import { ThemeToggle } from './components/ThemeToggle';
import type { Theme } from './components/ThemeToggle';
import { isMockApi } from './api/service';
import { clearDemoSession, loadDemoSession, saveDemoSession } from './utils/demoStorage';
import type { DemoSession } from './utils/demoStorage';
import './App.css';

type Page = 'profile' | 'home' | 'analytics';

function pageFromPath(): Page {
  if (window.location.pathname === '/analytics') return 'analytics';
  if (window.location.pathname === '/demo') return 'profile';
  return 'home';
}

const pagePath: Record<Page, string> = { profile: '/demo', home: '/', analytics: '/analytics' };
const themeKey = 'alfa-news:theme:v1';

function initialTheme(): Theme {
  try { return localStorage.getItem(themeKey) === 'dark' ? 'dark' : 'light'; }
  catch { return 'light'; }
}

const startingTheme = initialTheme();
if (typeof document !== 'undefined') {
  document.documentElement.dataset.theme = startingTheme;
  document.documentElement.style.colorScheme = startingTheme;
}

function App() {
  const [theme, setTheme] = useState<Theme>(startingTheme);
  // TODO: После MVP замените демо-восстановление на проверку авторизованной сессии
  // и загрузку компании/роли из backend. Демо-профиль не является авторизацией.
  const [session, setSession] = useState<DemoSession | null>(() => isMockApi ? loadDemoSession() : null);
  const [page, setPage] = useState<Page>(() => session ? pageFromPath() : 'profile');

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#111214' : '#f5f6f7');
    try { localStorage.setItem(themeKey, theme); } catch { /* Выбор темы действует до перезагрузки. */ }
  }, [theme]);

  const themeControl = <ThemeToggle theme={theme} onToggle={() => setTheme((current) => current === 'light' ? 'dark' : 'light')} />;

  useEffect(() => {
    const onPopState = () => {
      const requestedPage = pageFromPath();
      if (!session && requestedPage !== 'profile') {
        window.history.replaceState(null, '', pagePath.profile);
        setPage('profile');
      } else {
        setPage(requestedPage);
      }
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [session]);

  useEffect(() => {
    if (!session && window.location.pathname !== pagePath.profile) {
      window.history.replaceState(null, '', pagePath.profile);
    }
  }, [session]);

  useEffect(() => {
    if (!isMockApi) return;
    if (session) saveDemoSession(session);
    else clearDemoSession();
  }, [session]);

  const navigate = (nextPage: Page) => {
    if (window.location.pathname !== pagePath[nextPage]) {
      window.history.pushState(null, '', pagePath[nextPage]);
    }
    setPage(nextPage);
    window.scrollTo(0, 0);
  };

  if (!session || page === 'profile') {
    return <DemoLaunchpad themeControl={themeControl} onSelectProfile={(company, roleCode, roleName) => {
      setSession({ company, roleCode, roleName });
      navigate('home');
    }} />;
  }

  if (page === 'analytics') return (
    <AnalyticsScreen
      session={session}
      onExit={() => navigate('profile')}
      onHome={() => navigate('home')}
      onChangeRole={(roleCode, roleName) => setSession((current) => current ? { ...current, roleCode, roleName } : current)}
      themeControl={themeControl}
    />
  );

  return <BankHome session={session} onOpenAnalytics={() => navigate('analytics')} onChangeProfile={() => navigate('profile')} onChangeRole={(roleCode, roleName) => setSession((current) => current ? { ...current, roleCode, roleName } : current)} themeControl={themeControl} />;
}

export default App;
