import sys
import re
from pathlib import Path

def scan_files():
    base_dir = Path("e:/AI Study/krx_alertor_modular/pc_cockpit")
    output_path = Path("e:/AI Study/krx_alertor_modular/docs/UI_grep_inventory.log")
    
    files_to_scan = [
        base_dir / "cockpit.py",
        base_dir / "cockpit_new.py",
        base_dir / "cockpit_fixed.py"
    ]
    
    # regex matches exactly what user requested
    pattern = re.compile(r'(st\.button|st\.text_input|st\.selectbox|st\.radio|st\.checkbox|requests\.get|requests\.post|subprocess|os\.system|"/api/")')
    
    lines_found = []
    
    for f in files_to_scan:
        if not f.exists():
            continue
            
        lines_found.append(f"=== {f.name} ===")
        with open(f, 'r', encoding='utf-8') as file:
            for i, line in enumerate(file, 1):
                if pattern.search(line):
                    lines_found.append(f"{f.name}:{i}:{line.rstrip()}")
                    
        lines_found.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as out:
        out.write("\n".join(lines_found))
        
    print(f"Wrote {len(lines_found)} lines to {output_path}")

if __name__ == "__main__":
    scan_files()
