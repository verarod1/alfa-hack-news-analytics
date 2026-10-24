"""Внутренний однократный процесс. Вызывается только ml_gateway."""

import asyncio
import contextlib
import importlib
import inspect
import json
import sys
import os
import signal


def main():
    try:
        # Собственный deadline действует и при аварии родительского API/worker.
        def stop_group(signum, frame):
            if os.getpgrp() == os.getpid():
                os.killpg(os.getpgrp(), signal.SIGKILL)
            os._exit(124)

        signal.signal(signal.SIGALRM, stop_group)
        signal.alarm(int(os.environ.get("ML_PROCESS_TIMEOUT", "62")))
        context = json.load(sys.stdin)
        # Логи адаптера не становятся JSON-ответом и не возвращаются клиенту.
        with contextlib.redirect_stdout(sys.stderr):
            adapter = importlib.import_module(sys.argv[1])
            value = getattr(adapter, sys.argv[2])(context)
            if inspect.isawaitable(value):
                value = asyncio.run(value)
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json")
        print(json.dumps({"ok": True, "value": value}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({"ok": False}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
