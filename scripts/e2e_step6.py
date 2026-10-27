"""Paid manual end-to-end check. Run only after approving the estimated cost."""
import sys

from repro.cli import app

ISSUE = 'https://github.com/mahmoud/boltons/issues/337'

if __name__ == '__main__':
    print('Estimated model cost: roughly $0.15–$0.50 for a typical run; '
          'actual usage varies. The per-run guard is $1.00.', flush=True)
    app(args=[sys.argv[1] if len(sys.argv) > 1 else ISSUE])
