"""Run from a checkout without installing any Python dependencies."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pg_remnants.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
