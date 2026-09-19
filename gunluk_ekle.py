"""Çalışma günlüğüne tarihli kayıt ekler ve indeksi günceller.

Bu klasörün kaydı bu klasörde durur. Kayıt biçimi sabittir: SORUN → ÇÖZÜM →
DOĞRULAMA + değiştirilen dosyalar. Var olan bir kaydın üzerine yazılmaz.

    python gunluk_ekle.py "Kısa başlık" --sorun "..." --cozum "..." --dogrulama "..." \
        --dosya "research_ledger.py: tur revizyonu" --dosya "tracker_v2.py: saatlik CSV kapandı"
    python gunluk_ekle.py --liste
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).parent
DIARY = ROOT / 'GÜNLÜK'
INDEX = DIARY / '00_INDEKS.md'
INDEX_HEADER = """# Çalışma günlüğü indeksi

Bu klasörde yapılan her iş buraya bir satır bırakır. Ayrıntılı araştırma raporları
`ARASTIRMA/` altındadır; günlük yalnız ne yapıldığını ve nerede durduğunu söyler.
Kayıtlar yeniden eskiye sıralıdır.

"""


def slug(title):
    text = title.lower()
    for a, b in (('ı', 'i'), ('ğ', 'g'), ('ü', 'u'), ('ş', 's'), ('ö', 'o'), ('ç', 'c'), ('â', 'a')):
        text = text.replace(a, b)
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', text)).strip('-')[:60]


def entries():
    return sorted((p for p in DIARY.glob('20*.md') if p.name != INDEX.name), reverse=True)


def write_index():
    lines = [INDEX_HEADER]
    for path in entries():
        first = ''
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('# '):
                first = line[2:].strip()
                break
        lines.append(f'- [{path.name}]({path.name}) — {first}')
    INDEX.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return len(entries())


def add(title, sorun='', cozum='', dogrulama='', dosyalar=(), when=None, body=''):
    DIARY.mkdir(exist_ok=True)
    day = (when or date.today()).isoformat()
    path = DIARY / f'{day}_{slug(title)}.md'
    if path.exists():
        raise ValueError(f'Bu kayıt zaten var: {path.name} (üzerine yazılmaz)')
    rows = '\n'.join(f'| `{item.split(":", 1)[0].strip()}` | {item.split(":", 1)[-1].strip()} |'
                     for item in dosyalar) or '| — | — |'
    text = f"""# {day} — {title}

## SORUN

{sorun or '(yazılacak)'}

## ÇÖZÜM

{cozum or '(yazılacak)'}

## DOĞRULAMA

{dogrulama or '(yazılacak)'}

## Değiştirilen dosyalar

| Dosya | Değişiklik |
|---|---|
{rows}
"""
    if body:
        text += '\n' + body.rstrip() + '\n'
    path.write_text(text, encoding='utf-8')
    total = write_index()
    return {'kayit': path.name, 'toplam_kayit': total}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('baslik', nargs='?')
    ap.add_argument('--sorun', default='')
    ap.add_argument('--cozum', default='')
    ap.add_argument('--dogrulama', default='')
    ap.add_argument('--dosya', action='append', default=[], metavar='ad: değişiklik')
    ap.add_argument('--liste', action='store_true')
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass
    if args.liste:
        print(json.dumps({'kayitlar': [p.name for p in entries()]}, ensure_ascii=False, indent=2))
    elif args.baslik:
        print(json.dumps(add(args.baslik, args.sorun, args.cozum, args.dogrulama, args.dosya),
                         ensure_ascii=False, indent=2))
    else:
        ap.error('başlık ya da --liste gerekli')
