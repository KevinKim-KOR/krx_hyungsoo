#!/usr/bin/env python3
"""
간단한 인코딩 변환 스크립트
- 저장소 루트에서 실행을 가정 (tools 폴더에 있으므로 상대경로로 docs에 접근)
- `docs/` 아래 모든 파일을 순회해 텍스트로 판단되는 파일만 처리
- UTF-8로 디코딩 가능하면 그대로 둠, 아니면 여러 인코딩으로 시도해 성공하면 UTF-8로 덮어씀
- 작업 후 이 파일은 자동으로 삭제할 예정(사용자 요청)

주의: 원본 백업을 만들지 않습니다(요청에 따라 덮어쓰기). 필요하면 알려주세요.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOCS = os.path.join(ROOT, 'docs')

if not os.path.isdir(DOCS):
    print('docs/ 디렉터리를 찾을 수 없습니다:', DOCS)
    sys.exit(1)

TEXT_EXT_LIKELY = {'.md', '.txt', '.rst', '.mdx', '.html', '.htm', '.csv', '.yml', '.yaml', '.json', '.py'}
BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.bmp', '.pdf', '.zip', '.tar', '.gz', '.bz2', '.7z', '.dll', '.exe', '.class', '.pyc', '.woff', '.woff2', '.ttf', '.otf', '.mp3', '.mp4'}
TRY_ENCODINGS = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'cp1252', 'latin-1', 'iso-8859-1']

converted = []
skipped = []
errors = []

def is_maybe_binary(data: bytes) -> bool:
    if b'\x00' in data:
        return True
    # heuristic: if many non-text bytes, consider binary
    if not data:
        return False
    text_chars = bytearray(range(32, 127)) + b"\n\r\t\f\b"
    nontext = sum(1 for b in data if b not in text_chars)
    return (nontext / len(data)) > 0.30

for root, dirs, files in os.walk(DOCS):
    for fn in files:
        path = os.path.join(root, fn)
        rel = os.path.relpath(path, ROOT)
        ext = os.path.splitext(fn)[1].lower()
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except Exception as e:
            errors.append((rel, f'read-error: {e}'))
            continue

        if ext in BINARY_EXTS or (ext and ext not in TEXT_EXT_LIKELY and is_maybe_binary(data)):
            skipped.append((rel, 'binary-or-skip'))
            continue

        if len(data) == 0:
            skipped.append((rel, 'empty'))
            continue

        # Try utf-8 first
        try:
            data.decode('utf-8')
            # already utf-8
            skipped.append((rel, 'utf-8-ok'))
            continue
        except Exception:
            pass

        detected = None
        for enc in TRY_ENCODINGS:
            try:
                text = data.decode(enc)
                detected = enc
                break
            except Exception:
                continue

        if detected is None:
            errors.append((rel, 'encoding-unknown'))
            continue

        # write back as utf-8
        try:
            with open(path, 'w', encoding='utf-8', newline='\n') as outf:
                outf.write(text)
            converted.append((rel, detected))
        except Exception as e:
            errors.append((rel, f'write-error: {e}'))

# Print summary
print('--- Encoding conversion summary ---')
print('Target:', DOCS)
print()
print('Converted:', len(converted))
for r, enc in converted:
    print('CONVERTED:', r, '<-', enc)

print('\nSkipped:', len(skipped))
for r, reason in skipped[:200]:
    print('SKIPPED:', r, '(', reason, ')')

print('\nErrors:', len(errors))
for r, reason in errors[:200]:
    print('ERROR:', r, '(', reason, ')')

if errors:
    print('\n완료(일부 오류 발생).')
    sys.exit(2)

print('\n완료. 모든 처리된 파일은 UTF-8로 덮어씌워졌습니다.')
sys.exit(0)
