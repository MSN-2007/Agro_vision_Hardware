#!/usr/bin/env python3
"""Fix mediaSource bug in server.js observations handler."""
import os

path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'SIH_26_01', 'server', 'server.js')
path = os.path.abspath(path)

print(f"Fixing: {path}")

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
changes = 0
for i, line in enumerate(lines):
    if "mediaSource === 'raspberry_pi'" in line and ('13.2985' in line or '77.5350' in line):
        new_line = line.replace("mediaSource === 'raspberry_pi'", "obsSource === 'raspberry_pi'")
        fixed_lines.append(new_line)
        changes += 1
        print(f"  Fixed line {i+1}")
    else:
        fixed_lines.append(line)

if changes > 0:
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    print(f"SUCCESS: Fixed {changes} line(s) — mediaSource -> obsSource in observations handler")
else:
    print("No fix needed (already fixed or pattern not found)")
    for i, line in enumerate(lines, 1):
        if 'mediaSource' in line:
            print(f"  Line {i}: {line.strip()[:100]}")
