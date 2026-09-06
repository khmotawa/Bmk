#!/usr/bin/env python3
"""
fetch_clips.py — يبحث في Pexels عن مقاطع فيديو ستوك مناسبة لإعلانات BMK Grand
العقارية، وينزّلها محلياً داخل هذا الـrunner (بيئة GitHub Actions، إنترنت طبيعي
غير مقيّد)، ثم يبني index.json يوصف كل مقطع (يُقرأ لاحقاً عبر raw.githubusercontent.com
من الحاوية السحابية لـ Claude، اللي ما تقدر تنزّل من Pexels مباشرة).

يشتغل هذا السكربت فقط داخل GitHub Actions (أو أي جهاز عنده إنترنت طبيعي) —
مو مصمم للتشغيل داخل بيئة Claude السحابية أو داخل device_bash.
"""

import os
import json
import time
import pathlib
import requests

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
HEADERS = {"Authorization": PEXELS_API_KEY}
OUT_DIR = pathlib.Path("clips")
OUT_DIR.mkdir(exist_ok=True)

# فئات البي-رول المناسبة لإعلانات عقارية/استثمارية — نوسّع هذي القائمة بمرور الوقت
CATEGORIES = {
    "modern_building":   ["modern building exterior", "city skyline real estate"],
    "office_work":       ["office laptop typing", "business meeting office"],
    "handshake":         ["business handshake deal", "partnership agreement"],
    "money_counting":    ["counting cash money", "stacking coins finance"],
    "keys_handover":     ["house keys handover", "holding house key"],
    "contract_signing":  ["signing contract document", "pen signature paper"],
    "investment_chart":  ["stock chart growth graph", "financial data screen"],
    "construction":      ["building construction site", "construction crane"],
    "luxury_interior":   ["luxury apartment interior", "modern living room"],
    "family_home":       ["family walking new home", "family front door house"],
    "vault_safe":        ["bank vault door", "safe deposit box"],
    "digital_tech":      ["digital network hologram", "AI technology abstract"],
}

PER_CATEGORY = 2       # عدد المقاطع المطلوب تنزيلها لكل فئة
PER_PAGE_SEARCH = 5    # عدد النتائج المطلوب استعراضها بكل بحث لاختيار الأنسب
MIN_WIDTH = 720        # نتجاهل مقاطع بدقة أقل من كذا

index = {}

for category, queries in CATEGORIES.items():
    picked = []
    for query in queries:
        if len(picked) >= PER_CATEGORY:
            break
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=HEADERS,
            params={"query": query, "per_page": PER_PAGE_SEARCH, "size": "medium"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[!] فشل البحث '{query}': {resp.status_code} {resp.text[:200]}")
            continue
        data = resp.json()
        for video in data.get("videos", []):
            if len(picked) >= PER_CATEGORY:
                break
            # اختر أفضل ملف فيديو متاح (نفضّل عمودي/portrait إن وجد، وإلا landscape)
            files = sorted(
                [f for f in video["video_files"] if f.get("width", 0) >= MIN_WIDTH],
                key=lambda f: (f["height"] > f["width"], f.get("width", 0)),
                reverse=True,
            )
            if not files:
                continue
            best = files[0]
            vid_id = video["id"]
            fname = f"{category}_{vid_id}.mp4"
            fpath = OUT_DIR / fname
            if fpath.exists():
                picked.append(fname)
                continue
            print(f"[+] تنزيل {fname} من الفئة {category} ({query})")
            r = requests.get(best["link"], timeout=60)
            r.raise_for_status()
            fpath.write_bytes(r.content)
            picked.append(fname)
            index.setdefault(category, []).append({
                "filename": fname,
                "pexels_id": vid_id,
                "pexels_url": video["url"],
                "width": best.get("width"),
                "height": best.get("height"),
                "query": query,
            })
            time.sleep(1)  # احترام حدود Pexels API (200 طلب/ساعة على الخطة المجانية)

with open("index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print(f"\nتم. إجمالي المقاطع المنزّلة: {sum(len(v) for v in index.values())}")
