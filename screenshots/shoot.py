#!/usr/bin/env python3
"""截图所有核心页面用于 README"""
import subprocess, time, os

BASE = "http://localhost:5173"
OUT = "/home/cj/recruitment-agent/.screenshots"
os.makedirs(OUT, exist_ok=True)

pages = [
    ("dashboard.png",      "/dashboard",     "数据看板"),
    ("jds.png",            "/jds",           "岗位管理"),
    ("resumes.png",        "/resumes",       "简历管理"),
    ("candidates.png",     "/candidates",    "候选人库"),
    ("interviews.png",     "/interviews",    "面试流水线"),
    ("offers.png",         "/offers",        "Offer管理"),
    ("onboarding.png",     "/onboarding",    "入职管理"),
]

def shot(name, path, label):
    url = BASE + path
    out = os.path.join(OUT, name)
    print(f"  📸 {label:12s} → {url}")
    r = subprocess.run([
        "firefox", "--headless", "--screenshot", out, url,
        "--window-size=1440,900"
    ], capture_output=True, text=True, timeout=30)
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        kb = os.path.getsize(out) // 1024
        print(f"     ✅ {kb}KB")
    else:
        err = r.stderr.strip() or "no output"
        print(f"     ⚠️  failed: {err[:100]}")

print("=" * 50)
print("  📸 开始截图页面")
print("=" * 50)
for name, path, label in pages:
    shot(name, path, label)
print("=" * 50)
print(f"  截图保存在 {OUT}")
