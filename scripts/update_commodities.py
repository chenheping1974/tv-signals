#!/usr/bin/env python3
"""每天拉取大宗商品OHLCV（新浪全球期货） → push到GitHub"""
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests as req

BASE = Path(__file__).resolve().parent.parent
OHLCV_FILE = BASE / "data/commodities_ohlcv.csv.gz"

# 新浪代码 → Yahoo符号（供Space识别）
COMMODITIES = {
    "GC":  "GC=F",   # COMEX黄金
    "SI":  "SI=F",   # COMEX白银
    "CL":  "CL=F",   # NYMEX原油
    "HG":  "HG=F",   # COMEX铜
    "AHD": "AH=F",   # LME铝
    "SM":  "ZM=F",   # CBOT豆粕
}

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_sina_futures(symbol_sina: str) -> list[dict]:
    """拉取单个品种全部日线，返回标准化行列表"""
    today = f"{datetime.today().year}_{datetime.today().month}_{datetime.today().day}"
    url = (
        f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php"
        f"/var%20_S{today}=/GlobalFuturesService.getGlobalFuturesDailyKLine"
    )
    r = req.get(url, params={"symbol": symbol_sina, "_": today, "source": "web"},
               headers=HEADERS, timeout=30)
    # JSONP去壳
    text = r.text
    start = text.index("[")
    end = text.rindex("]") + 1
    rows = json.loads(text[start:end])
    if not rows or not isinstance(rows, list):
        return []

    df = pd.DataFrame(rows)
    df = df.rename(columns={"day": "date"})
    df["symbol"] = COMMODITIES[symbol_sina]
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["date", "symbol", "open", "high", "low", "close"]].dropna().to_dict("records")


def main():
    t0 = time.time()
    print(f"📥 大宗商品OHLCV更新 {datetime.now():%Y-%m-%d %H:%M:%S}")

    # 加载已有数据
    existing = []
    if OHLCV_FILE.exists():
        df = pd.read_csv(OHLCV_FILE)
        df["date"] = pd.to_datetime(df["date"], format='ISO8601')
        existing = df.to_dict("records")
        print(f"   已有: {df['symbol'].nunique()}品种, {len(df)}行, 截止{df['date'].max().date()}")

    # 拉取6品种全量（API不支持增量参数，6个×~2500行,很小）
    all_rows = {}
    for sina_sym, yahoo_sym in COMMODITIES.items():
        try:
            rows = fetch_sina_futures(sina_sym)
            print(f"   {sina_sym} → {yahoo_sym}: {len(rows)}行")
            all_rows[yahoo_sym] = rows
        except Exception as e:
            print(f"   ❌ {sina_sym}: {e}")

    # 去重合并：以 (date, symbol) 为主键
    combined = {}
    for row in existing:
        combined[(row["date"].date() if hasattr(row["date"], "date") else row["date"],
                  row["symbol"])] = row
    for sym, rows in all_rows.items():
        for row in rows:
            combined[(row["date"].date(), row["symbol"])] = row

    new_df = pd.DataFrame(list(combined.values()))
    new_df = new_df.sort_values(["symbol", "date"])
    OHLCV_FILE.parent.mkdir(exist_ok=True)
    new_df.to_csv(OHLCV_FILE, index=False, compression="gzip")
    print(f"✅ 总计: {new_df['symbol'].nunique()}品种, {len(new_df)}行, "
          f"截止{new_df['date'].max().date()}, "
          f"{(time.time()-t0):.0f}s")


if __name__ == "__main__":
    main()
