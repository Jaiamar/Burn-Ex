import re
from collections import defaultdict

with open("backend/api.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

route_lines = defaultdict(list)
for i, line in enumerate(lines, 1):
    m = re.search(r'@app\.(get|post|put|delete|patch|options)\(["\']([^"\']+)["\']', line)
    if m:
        method = m.group(1).upper()
        path = m.group(2)
        route_lines[(method, path)].append(i)

for (method, path), line_nums in route_lines.items():
    if len(line_nums) > 1:
        print(f"Duplicate route {method} {path} at lines: {line_nums}")
