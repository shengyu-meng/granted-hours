#!/usr/bin/env python3
"""Placeholder index builder for future daily archive automation.

Future use: read metadata/days.json and regenerate README daily archive and docs gallery.
"""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
days = json.loads((ROOT/'metadata/days.json').read_text(encoding='utf-8'))
print(f'Loaded {len(days)} public day entries.')
