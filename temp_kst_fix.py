import os
import re

KST_IMPORT = "\nfrom datetime import timezone, timedelta\nKST = timezone(timedelta(hours=9))\n"
NOW_PATTERN = re.compile(r'datetime\.now\(\)')
UTC_PATTERN = re.compile(r'datetime\.utcnow\(\)')

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return False

    original = content
    
    # Check if we need to modify
    if not NOW_PATTERN.search(content) and not UTC_PATTERN.search(content):
        return False

    # Inject KST definition if not present
    if "KST = timezone(timedelta(hours=9))" not in content:
        # Find a good place to inject: after datetime imports
        if "from datetime import" in content:
            content = re.sub(
                r'(from datetime import [^\n]*)',
                r'\1\nfrom datetime import timezone, timedelta\nKST = timezone(timedelta(hours=9))',
                content,
                count=1
            )
        elif "import datetime" in content:
            content = re.sub(
                r'(import datetime[^\n]*)',
                r'\1\nfrom datetime import timezone, timedelta\nKST = timezone(timedelta(hours=9))',
                content,
                count=1
            )
        else:
            # Add to top
            content = "import datetime\nfrom datetime import timezone, timedelta\nKST = timezone(timedelta(hours=9))\n" + content

    # Replace usages
    content = NOW_PATTERN.sub('datetime.now(KST)', content)
    content = UTC_PATTERN.sub('datetime.now(KST)', content)
    
    # Fix explicit 'Z' append which is wrong for +09:00
    content = content.replace('.isoformat() + "Z"', '.isoformat()')

    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")
        return True
    return False

if __name__ == "__main__":
    count = 0
    base_dir = r"e:\AI Study\krx_alertor_modular"
    for root, dirs, files in os.walk(base_dir):
        if any(skip in root for skip in ['.git', '.venv', '__pycache__']):
            continue
        for file in files:
            if file.endswith('.py'):
                if process_file(os.path.join(root, file)):
                    count += 1
    print(f"Total files updated: {count}")
