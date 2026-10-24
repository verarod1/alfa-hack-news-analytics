export type Theme = 'light' | 'dark';

interface Props {
  theme: Theme;
  onToggle: () => void;
}

export function ThemeToggle({ theme, onToggle }: Props) {
  const nextTheme = theme === 'light' ? 'тёмную' : 'светлую';

  return <button
    type="button"
    className="theme-toggle"
    onClick={onToggle}
    aria-label={`Включить ${nextTheme} тему`}
    title={`Включить ${nextTheme} тему`}
  >
    <span aria-hidden="true">{theme === 'light' ? '☾' : '☀'}</span>
    <span>{theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}</span>
  </button>;
}
