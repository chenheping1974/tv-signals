#!/usr/bin/env python3
"""每周股票池重筛——本地运行，推 GitHub"""
import json, requests, time, re
import akshare as ak
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent

print("📊 拉全量股票...")
df = ak.stock_info_a_code_name()
df.columns = ["code", "name"]

print("🔍 四条件筛选（腾讯财经）...")
pool = []
for i in range(0, len(df), 80):
    batch = df.iloc[i : i + 80]
    codes = ",".join(
        f"{'sh' if str(r['code']).zfill(6).startswith('6') else 'sz'}{str(r['code']).zfill(6)}"
        for _, r in batch.iterrows()
    )
    try:
        r = requests.get(f"http://qt.gtimg.cn/q={codes}", timeout=20)
        r.encoding = "gbk"
        for _, row in batch.iterrows():
            code = str(row["code"]).zfill(6)
            name = str(row["name"])
            if "ST" in name or "退" in name:
                continue
            if code.startswith(("688", "8")):
                continue
            sym = f"sh{code}" if code.startswith("6") else f"sz{code}"
            m = re.search(rf'{sym}="([^"]*)"', r.text)
            if not m:
                continue
            parts = m.group(1).split("~")
            if len(parts) < 45:
                continue
            mcap = float(parts[44]) if parts[44] else 0
            turnover = float(parts[37]) if parts[37] else 0
            if mcap > 80 and turnover > 10000:
                pool.append({"code": code, "name": name})
    except Exception as e:
        print(f"   ⚠️ 批次失败: {e}")
    time.sleep(0.1)
    if i % 400 == 0:
        print(f"   [{i}/{len(df)}] {len(pool)} 只")

pool.sort(key=lambda x: x.get("turnover", 0), reverse=True)
data = {"last_screened": datetime.now().strftime("%Y-%m-%d"), "stocks": pool}
with open(BASE / "data/stock_pool.json", "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"✅ {len(pool)} 只，git push 即可")
