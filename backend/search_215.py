import os
for root, dirs, files in os.walk('.'):
    if '.git' in root or '__pycache__' in root or '.system_generated' in root:
        continue
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                c = fh.read()
                if '215.00' in c or '215' in c:
                    for idx, line in enumerate(c.splitlines()):
                        if '215' in line:
                            print(f"{fp}:{idx+1}: {line.strip()[:100]}")
        except Exception:
            pass
