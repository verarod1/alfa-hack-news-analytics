"""Импорт небольшого проверенного JSON через существующий news_service, без сети/ML."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.parsers.article_extractor import substantive
from app.parsers.sources import SOURCES
from app.schemas.news import NewsInput
from app.services.news_service import save_news

DEFAULT_FILE = Path(__file__).resolve().parents[1] / 'fixtures' / 'official_news.json'


def load_fixtures(path):
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError('JSON слишком большой')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list) or not 1 <= len(data) <= 20:
        raise ValueError('Ожидается 1–20 записей')
    values = [NewsInput.model_validate(item) for item in data]
    for value in values:
        if value.source_id not in {'minfin', 'fns'} or value.is_synthetic or value.published_at is None:
            raise ValueError('Требуется проверенная официальная публикация с датой')
        source = SOURCES[value.source_id]
        if value.id != source.news_id(value.source_url) or value.source_name != source.name:
            raise ValueError('ID или источник не совпадают с реестром')
        if not substantive(value.text or '', 120):
            raise ValueError('Нет содержательного текста')
    if len({item.id for item in values}) != len(values):
        raise ValueError('Повтор ID внутри файла')
    return values


def import_fixtures(path=DEFAULT_FILE, *, dry_run=False):
    values = load_fixtures(path)  # Проверяем весь файл до первой записи.
    result = {'dry_run': dry_run, 'stored_or_existing': [], 'failed': []}
    for value in values:
        if dry_run:
            continue
        try:
            result['stored_or_existing'].append(save_news(value).id)
        except Exception:
            result['failed'].append(value.id)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=DEFAULT_FILE)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        result = import_fixtures(args.file, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(bool(result['failed']))
    except (OSError, ValueError, TypeError):
        print('Некорректный JSON или неподтверждённые поля публикации.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
