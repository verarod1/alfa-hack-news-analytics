"""Пять проверок на временных CSV, без подключения к PostgreSQL."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "import_csv", Path(__file__).resolve().parents[1] / "scripts/import_csv.py"
)
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)


class ImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        files = {
            'df_Uid_data_hack.csv': 'SYNTHETIC_U;NOTE\n c1 ;  text  \n',
            'df_Uid_payment_hack.csv': 'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\nc1;c2;12.50;3\n',
            'df_Fid_Uid_link_hack.csv': 'SYNTHETIC_F;SYNTHETIC_U\nf1;c1\n',
        }
        for name, text in files.items():
            (self.directory / name).write_text(text, encoding='utf-8')

        data_directory = patch.object(imp, 'DATA_DIR', self.directory)
        data_directory.start()
        self.addCleanup(data_directory.stop)
        # Если тест случайно попробует подключиться к БД, он сразу упадёт.
        real_connection = patch.object(imp.psycopg, 'connect', side_effect=AssertionError('Real DB forbidden'))
        real_connection.start()
        self.addCleanup(real_connection.stop)

        # Mock только записывает вызовы; PostgreSQL здесь не эмулируется.
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        # Первый ответ: блокировка получена. Второй: таблицы пусты.
        self.cursor.fetchone.side_effect = [(True,), (False,)]
        self.transaction = self.connection.transaction.return_value
        self.transaction.__exit__.return_value = False  # Не подавлять ошибки.

    def test_small_csv_is_processed_successfully(self):
        self.assertEqual(imp.import_companies(self.connection), 1)
        writer = self.cursor.copy.return_value.__enter__.return_value
        company_id, raw_json = writer.write_row.call_args.args[0]
        self.assertEqual(company_id, 'c1')
        self.assertEqual(json.loads(raw_json), {'SYNTHETIC_U': ' c1 ', 'NOTE': '  text  '})

    def test_invalid_csv_is_rejected_before_connection(self):
        path = self.directory / 'df_Uid_payment_hack.csv'
        invalid_files = [
            b'',                                      # Пустой файл.
            b'OTHER\nx\n',                             # Нет обязательных колонок.
            b'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\n',      # Нет строк данных.
            b'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\na;b\n', # Не хватает полей.
            b'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\n ;b;1;1\n',
            b'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\na;b;NaN;1\n',
            b'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\na;b;1;1.5\n',
            b'PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\na;b;1;9223372036854775808\n',
            b'\xff',                                  # Некорректная кодировка.
            None,                                     # Файл отсутствует.
        ]
        for content in invalid_files:
            with self.subTest(content=content):
                if content is None:
                    path.unlink()
                else:
                    path.write_bytes(content)
                with patch.object(imp, 'get_connection') as connect, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(imp.main(['--replace']), 1)
                connect.assert_not_called()

    def test_existing_data_or_running_import_prevents_changes(self):
        cases = [
            ([(True,), (True,)], 'содержат данные'),  # Повторный импорт.
            ([(False,)], 'Другой импорт'),           # Импорт уже выполняется.
        ]
        for answers, message in cases:
            with self.subTest(message=message):
                self.cursor.reset_mock()
                self.cursor.fetchone.side_effect = answers
                with self.assertRaisesRegex(imp.ImportError, message):
                    imp.run_import(self.connection)
                self.cursor.copy.assert_not_called()
                queries = [call.args[0] for call in self.cursor.execute.call_args_list]
                self.assertFalse(any('TRUNCATE' in query for query in queries))

    def test_error_reaches_transaction_for_rollback(self):
        # Ошибка в последнем файле должна выйти из общей транзакции,
        # даже если в режиме replace перед этим уже выполнялся TRUNCATE.
        error = imp.ImportError('Ошибка в последнем CSV')
        for replace in (False, True):
            with self.subTest(replace=replace):
                self.cursor.fetchone.side_effect = [(True,), (False,)]
                self.transaction.reset_mock()
                with patch.object(imp, 'import_person_links', side_effect=error):
                    with self.assertRaises(imp.ImportError):
                        imp.run_import(self.connection, replace=replace)
                self.transaction.__exit__.assert_called_once()
                error_type, received_error, _ = self.transaction.__exit__.call_args.args
                self.assertIs(error_type, imp.ImportError)
                self.assertIs(received_error, error)
                self.connection.commit.assert_not_called()

    def test_replace_warns_and_clears_only_source_tables(self):
        output, warning = io.StringIO(), io.StringIO()
        with patch.object(imp, 'get_connection', return_value=self.connection):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(warning):
                self.assertEqual(imp.main(['--replace']), 0)
        self.assertIn('ВНИМАНИЕ', warning.getvalue())
        queries = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertEqual(queries, [
            'SELECT pg_try_advisory_xact_lock(%s)',
            'TRUNCATE TABLE raw_companies, raw_payments, raw_person_links RESTART IDENTITY',
        ])
        self.assertEqual(self.cursor.copy.call_count, 3)
        self.transaction.__exit__.assert_called_once_with(None, None, None)

    def test_import_timeout_is_transaction_local(self):
        with patch.dict(imp.os.environ, {'IMPORT_STATEMENT_TIMEOUT_MS': '600000'}):
            imp.run_import(self.connection)
        self.connection.execute.assert_called_once_with(
            "SELECT set_config('statement_timeout', %s, true)", ('600000',))


if __name__ == '__main__':
    unittest.main()
