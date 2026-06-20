#!/usr/bin/env python3
"""
A股横截面选股 — 粗筛1000只 + Kronos-small预测30天涨跌幅 → ranking.json
每天16:30由GitHub Actions触发，结果存到data/ranking.json
"""

import os, sys, json, time, warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import requests

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── 配置 ────────────────────────────────────────────
OUTPUT_FILE = DATA_DIR / "ranking.json"
PROGRESS_FILE = DATA_DIR / "ranking_progress.json"  # 断点续跑
BATCH_SIZE = 10    # 每10只存一次进度
MAX_STOCKS = 1000  # 目标粗筛数量
PRED_DAYS = 30     # 预测未来天数

# ── 股票池（预生成的沪深主板+创业板清单）────────────────
# 避免依赖 akshare（GitHub Actions US 机房连不上）
# 使用 yfinance 拉单只数据，再用基本面 API 补充筛选
STOCK_POOL_URL = "https://raw.githubusercontent.com/chenheping1974/tv-signals/main/data/stock_pool.json"


def build_stock_pool():
    """如果本地没有 stock_pool.json，从远程读取或生成默认池"""
    pool_file = DATA_DIR / "stock_pool.json"
    if pool_file.exists():
        return json.loads(pool_file.read_text())

    print("📥 下载预生成股票池...")
    try:
        r = requests.get(STOCK_POOL_URL, timeout=30)
        stocks = r.json()
        pool_file.write_text(json.dumps(stocks, ensure_ascii=False))
        return stocks
    except:
        pass

    # fallback: 使用内置清单（沪深300 + 中证500 核心成分）
    print("⚠️ 无法下载，使用内置核心池")
    return FALLBACK_POOL

# 内置备选：沪深300+中证500去重（代码+名称）
FALLBACK_POOL = [
    {"code": "600519", "name": "贵州茅台"}, {"code": "000858", "name": "五粮液"},
    {"code": "601318", "name": "中国平安"}, {"code": "600036", "name": "招商银行"},
    {"code": "000333", "name": "美的集团"},   {"code": "002415", "name": "海康威视"},
    {"code": "600276", "name": "恒瑞医药"},   {"code": "000651", "name": "格力电器"},
    {"code": "601012", "name": "隆基绿能"},   {"code": "002714", "name": "牧原股份"},
    {"code": "600887", "name": "伊利股份"},   {"code": "000002", "name": "万科A"},
    {"code": "601899", "name": "紫金矿业"},   {"code": "600547", "name": "山东黄金"},
    {"code": "600362", "name": "江西铜业"},   {"code": "000807", "name": "云铝股份"},
    {"code": "601600", "name": "中国铝业"},   {"code": "601857", "name": "中国石油"},
    {"code": "600028", "name": "中国石化"},   {"code": "603993", "name": "洛阳钼业"},
    {"code": "600111", "name": "北方稀土"},   {"code": "002460", "name": "赣锋锂业"},
    {"code": "000876", "name": "新希望"},     {"code": "002311", "name": "海大集团"},
    {"code": "601088", "name": "中国神华"},   {"code": "600585", "name": "海螺水泥"},
    {"code": "000725", "name": "京东方A"},    {"code": "002475", "name": "立讯精密"},
    {"code": "300750", "name": "宁德时代"},   {"code": "300059", "name": "东方财富"},
    {"code": "300124", "name": "汇川技术"},   {"code": "300274", "name": "阳光电源"},
    # ... 后续可扩展
]


def fetch_all_stocks():
    """直接取预生成股票池的前 MAX_STOCKS 只（已被 akshare 验证过，无需 yfinance 二次筛选）"""
    pool = build_stock_pool()
    print(f"📊 预生成股票池: {len(pool)} 只")

    valid = []
    for s in pool:
        code = s["code"] if isinstance(s, dict) else s
        if code.startswith("688") or code.startswith("8"):
            continue
        valid.append({"code": code, "name": s.get("name", "") if isinstance(s, dict) else ""})

    # 直接取前 N 只（池子已按有效股票排序）
    result = valid[:MAX_STOCKS]
    print(f"✅ 取前 {len(result)} 只送 Kronos")
    return pd.DataFrame(result).rename(columns={"code": "代码", "name": "名称"})


# ── Kronos 预测 ─────────────────────────────────────
def load_kronos():
    """懒加载 Kronos 模型"""
    import importlib.util
    if importlib.util.find_spec("model") is None:
        # 如果没有安装kronos包，直接从HF克隆
        kronos_path = Path("/tmp/kronos_repo")
        if not (kronos_path / "model.py").exists():
            print("📦 克隆 Kronos 仓库...")
            os.system(f"rm -rf {kronos_path} && git clone --depth 1 https://github.com/shiyu-coder/Kronos {kronos_path} 2>&1 | tail -1")
        sys.path.insert(0, str(kronos_path))

    from model import Kronos, KronosTokenizer, KronosPredictor

    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
    return predictor


# 批量缓存的 OHLCV 数据
_OHLCV_CACHE = {}

def fetch_batch_ohlcv(codes):
    """用 yfinance 批量下载 OHLCV（一次请求多只，避免限流）"""
    import yfinance as yf
    symbols = []
    for c in codes:
        suffix = ".SS" if c.startswith("6") else ".SZ"
        symbols.append(f"{c}{suffix}")
    try:
        data = yf.download(symbols, period="1y", progress=False, threads=True, group_by="ticker")
        for i, sym in enumerate(symbols):
            if sym in data.columns:
                df = data[sym].dropna()
                if len(df) >= 100:
                    df = df.reset_index()
                    df.columns = [c.lower() for c in df.columns]
                    df = df.rename(columns={"date": "date", "open": "open",
                                             "high": "high", "low": "low", "close": "close"})
                    df["date"] = pd.to_datetime(df["date"])
                    if hasattr(df["date"], "dt"):
                        df["date"] = df["date"].dt.tz_localize(None)
                    for col in ["open", "high", "low", "close"]:
                        if col in df.columns:
                            key = codes[i]
                            _OHLCV_CACHE[key] = df[["date", "open", "high", "low", "close"]].tail(512)
    except Exception as e:
        print(f"   ⚠️ 批量下载失败: {e}")


def fetch_stock_ohlcv(code):
    """从缓存取单只股票OHLCV"""
    return _OHLCV_CACHE.get(code, None)


def predict_single(predictor, code, name):
    """预测单只股票30天涨跌幅"""
    df = fetch_stock_ohlcv(code)
    if df is None or len(df) < 100:
        return None

    try:
        result = predictor.predict(
            df=df[["open", "high", "low", "close"]],
            x_timestamp=pd.to_datetime(df["date"]),
            y_timestamp=None,
            pred_len=PRED_DAYS,
            T=1.0,
            top_p=0.9,
            sample_count=1,
        )
        if result is None or len(result) == 0:
            return None
        last_close = df["close"].iloc[-1]
        pred_close = result["close"].iloc[-1] if "close" in result.columns else result.iloc[-1, 0]
        pct_change = (pred_close - last_close) / last_close * 100
        return {
            "code": code,
            "name": name,
            "last_close": round(float(last_close), 2),
            "pred_close": round(float(pred_close), 2),
            "pct_change": round(float(pct_change), 2),
        }
    except Exception as e:
        print(f"   ⚠️ {code} {name} 预测失败: {e}")
        return None


# ── 主函数 ──────────────────────────────────────────
def main():
    print(f"🚀 A股横截面选股开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    t0 = time.time()

    # 1. 粗筛
    stocks = fetch_all_stocks()
    if stocks.empty:
        print("❌ 粗筛结果为空")
        return

    # 2. 加载断点
    if PROGRESS_FILE.exists():
        progress = json.loads(PROGRESS_FILE.read_text())
        results = progress.get("results", [])
        start_idx = progress.get("next_idx", 0)
        print(f"📎 断点续跑: 已处理 {len(results)} 只，从第 {start_idx} 只继续")
    else:
        results = []
        start_idx = 0

    # 3. 加载 Kronos
    print("🤖 加载 Kronos-small 模型...")
    predictor = load_kronos()

    # 4. 逐批下载 + 预测
    total = len(stocks)
    ohclv_batch = 10  # 每批下载10只OHLCV
    print(f"🔮 开始预测 {total} 只股票（剩余 {total - start_idx} 只）...")
    for i in range(start_idx, total):
        # 批量预下载 OHLCV
        if i % ohclv_batch == 0:
            batch_end = min(i + ohclv_batch, total)
            batch_codes = [stocks.iloc[j]["代码"] for j in range(i, batch_end)]
            print(f"📥 批量下载 OHLCV [{i+1}-{batch_end}]...")
            fetch_batch_ohlcv(batch_codes)
            time.sleep(2)  # 避免限流

        row = stocks.iloc[i]
        code, name = row["代码"], row["名称"]
        print(f"   [{i+1}/{total}] {code} {name}...", end=" ", flush=True)

        result = predict_single(predictor, code, name)
        if result:
            results.append(result)
            pct = result["pct_change"]
            emoji = "🟢" if pct > 0 else "🔴"
            print(f"{emoji} {pct:+.2f}%")
        else:
            print("⏭️ 跳过")

        if (i + 1) % BATCH_SIZE == 0:
            progress = {"results": results, "next_idx": i + 1, "total": total,
                        "updated": datetime.now().isoformat()}
            PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2))
            elapsed = time.time() - t0
            rate = (i + 1 - start_idx) / elapsed * 60 if elapsed > 0 else 0
            print(f"   💾 已存断点 [{i+1}/{total}] 速度: {rate:.1f} 只/分钟")

    # 5. 排序保存
    results.sort(key=lambda x: x["pct_change"], reverse=True)
    output = {
        "updated": datetime.now().isoformat(),
        "total_stocks": len(results),
        "ranking": results,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    # 清理断点
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    elapsed = (time.time() - t0) / 60
    print(f"\n✅ 完成! {len(results)} 只排序完成，耗时 {elapsed:.0f} 分钟")
    top = results[:5]
    for r in top:
        print(f"   {r['code']} {r['name']}: {r['pct_change']:+.2f}%")

if __name__ == "__main__":
    main()
