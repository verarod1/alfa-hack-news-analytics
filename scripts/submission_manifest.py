"""Print the exact committed submission version; refuse an uncommitted checkout."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def main():
    if git('status', '--porcelain', '--untracked-files=all'):
        print('Refusing to identify uncommitted files as a submitted commit. Commit the intended files first.', file=sys.stderr)
        return 1
    print(json.dumps({
        'repository': git('remote', 'get-url', 'origin'),
        'commit': git('rev-parse', 'HEAD'),
        'commit_time': git('show', '-s', '--format=%cI', 'HEAD'),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'jury_account': 'alfa-hack-2026',
        'jury_access': 'must be verified on GitHub',
        'deadline': 'must be supplied by the team; commit time alone does not prove deadline compliance',
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
