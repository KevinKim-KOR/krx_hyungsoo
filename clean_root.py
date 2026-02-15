import shutil, glob, os
dest = "_archive/cleanup_20260215"
os.makedirs(dest, exist_ok=True)
patterns = [
    "verify_*.*", "run_*.py", "*_output.txt", "*_check.txt", "*_result.txt", 
    "p95_*.txt", "diff_check.txt", "repro_*.*", "temp_*.json"
]
print(f"Cleaning up files to {dest}...")
count = 0
for p in patterns:
    for f in glob.glob(p):
        try:
            shutil.move(f, dest)
            print(f"Moved: {f}")
            count += 1
        except Exception as e:
            print(f"Error moving {f}: {e}")
print(f"Moved {count} files.")
