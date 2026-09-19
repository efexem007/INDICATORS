"""JSONL'den saatlik CSV üretir: takip artık CSV'yi ikinci kez diske yazmıyor.

Kayıt eksilmez — JSONL asıl kaynaktır ve CSV onun skaler alt kümesidir. Bu betik
aynı sütun düzeniyle CSV'yi geri üretir; var olan dosyanın üzerine yazmaz.

    python snapshots_csv_uret.py logs/run_20260918_112149
    python snapshots_csv_uret.py logs/run_20260918_112149 --force
"""
import argparse
import csv
import json
from pathlib import Path
import sys

from tracker_v2 import _csv_cell


def scalar(value):
    return not isinstance(value, (list, dict))


def convert(run_dir, force=False):
    run_dir = Path(run_dir)
    parts = sorted(run_dir.glob('snapshots_*.jsonl'))
    if not parts:
        raise ValueError(f'JSONL parçası yok: {run_dir}')
    fields, rows_by_part = [], {}
    seen = set()
    for part in parts:  # sütun düzeni ilk görülme sırasına göre, tüm parçalar üzerinden
        rows = []
        with part.open(encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                for key, value in row.items():
                    if key not in seen and scalar(value):
                        seen.add(key)
                        fields.append(key)
                rows.append(row)
        rows_by_part[part] = rows
    written = []
    for part, rows in rows_by_part.items():
        target = part.with_suffix('.csv')
        if target.exists() and not force:
            print(f'atlandı (var): {target.name}')
            continue
        with target.open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, lineterminator='\n')
            writer.writerow(fields)
            for row in rows:
                writer.writerow([_csv_cell(row.get(key)) for key in fields])
        written.append((target.name, len(rows)))
    for name, count in written:
        print(f'yazıldı: {name} ({count} satır)')
    return {'parts': len(parts), 'written': len(written), 'fields': len(fields)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir')
    ap.add_argument('--force', action='store_true', help='var olan CSV dosyalarının üzerine yaz')
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass
    print(json.dumps(convert(args.run_dir, args.force), ensure_ascii=False))
