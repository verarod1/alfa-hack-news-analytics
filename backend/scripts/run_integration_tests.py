"""Временный локальный PostgreSQL без TCP и Docker volumes. Нужны PostgreSQL binaries."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


def main():
    root = Path(tempfile.mkdtemp(prefix="alfa-mvp-isolated-"))
    socket = Path("/tmp") / ("alfapg-" + uuid.uuid4().hex[:8])
    socket.mkdir(mode=0o700)
    database = "alfa_mvp_test_" + uuid.uuid4().hex[:8]
    binary = os.getenv("POSTGRES_TEST_BIN")
    if not binary:
        found = shutil.which("initdb")
        binary = (
            str(Path(found).parent) if found else "/opt/homebrew/opt/postgresql@16/bin"
        )
    pg = Path(binary)
    started = False
    project = Path(__file__).resolve().parents[2]
    try:
        if not (pg / "initdb").is_file():
            print(
                "Задайте POSTGRES_TEST_BIN: каталог initdb/pg_ctl PostgreSQL 16.",
                file=sys.stderr,
            )
            return 1
        print(
            f"Тестовая цель: {database}; каталог {root}; Unix-сокет {socket}; TCP выключен.",
            flush=True,
        )
        subprocess.run(
            [
                str(pg / "initdb"),
                "-D",
                str(root / "data"),
                "--auth-local=trust",
                "--auth-host=reject",
                "--encoding=UTF8",
                "--no-locale",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [
                str(pg / "pg_ctl"),
                "-D",
                str(root / "data"),
                "-l",
                str(root / "server.log"),
                "-o",
                f"-h '' -k {socket} -p 65432 -c max_connections=20 -c shared_buffers=16MB",
                "-w",
                "start",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        started = True
        with psycopg.connect(
            host=str(socket), port=65432, dbname="postgres", autocommit=True
        ) as conn:
            assert (
                Path(conn.execute("SHOW data_directory").fetchone()[0]) == root / "data"
            )
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        dsn = make_conninfo(host=str(socket), port=65432, dbname=database)
        with psycopg.connect(dsn) as conn:
            assert (
                conn.execute("SELECT current_database()").fetchone()[0] == database
                and database != "alfa_news"
            )
            for path in ["backend/db/schema.sql", "backend/db/mvp.sql"]:
                conn.execute((project / path).read_text())
        env = dict(
            os.environ,
            INTEGRATION_DATABASE_URL=dsn,
            ALFA_TEST_CLUSTER_ROOT=str(root),
            PYTHONDONTWRITEBYTECODE="1",
        )
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "unittest",
                "discover",
                "-s",
                "backend/tests",
                "-p",
                "test_postgres_integration.py",
                "-v",
            ],
            cwd=project,
            env=env,
        ).returncode
    finally:
        if started:
            subprocess.run(
                [
                    str(pg / "pg_ctl"),
                    "-D",
                    str(root / "data"),
                    "-m",
                    "fast",
                    "-w",
                    "stop",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        # Удаляются только созданные этим запуском временные ресурсы.
        shutil.rmtree(root)
        shutil.rmtree(socket)


if __name__ == "__main__":
    sys.exit(main())
