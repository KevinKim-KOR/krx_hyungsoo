import argparse
import hashlib
import os
import sys
from typing import List

def sha256_of(path: str, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description='Compare SHA256 hashes of multiple files')
    p.add_argument('files', nargs='+', help='Files to compare')
    args = p.parse_args(argv)

    missing = [f for f in args.files if not os.path.exists(f)]
    if missing:
        print(f"[ERROR] Missing files: {missing}")
        return 2

    hashes = [(f, sha256_of(f)) for f in args.files]
    base_hash = hashes[0][1]
    all_match = all(h == base_hash for _, h in hashes)

    for f, h in hashes:
        print(f"{h}  {f}")

    if all_match:
        print("[OK] ALL MATCH")
        return 0
    else:
        print("[DIFF] Hash mismatch detected")
        return 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
