#!/usr/bin/env python3
"""
tv-signals — 大宗商品 & A股 AI情报系统
每日从RSSHub采集 → DeepSeek分析 → 生成精选RSS → GitHub Pages发布
"""

import feedparser, json, hashlib, os, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# ── 配置 ────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
FEEDS_DIR = ROOT / "feeds"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
PROCESSED_FILE = DATA_DIR / "processed_urls.json"
SIGNAL_LOG = DATA_DIR / "signal_log.json"

# 信源配置 — 直接API，不经过RSSHub
SOURCES = [
    {
        "type": "wallstreetcn",
        "name": "华尔街见闻",
        "cat": "both",
        "url": "https://api-prod.wallstreetcn.com/apiv1/content/lives/pc?limit=50",
    },
]

# 关键词过滤
KEYWORDS = re.compile(
    r"黄金|白银|gold|silver|XAU|XAG|"
    r"原油|crude|WTI|Brent|OPEC|EIA|石油|"
    r"铜|copper|COMEX|LME|铜矿|罢工|"
    r"铝|aluminum|电解铝|产能|"
    r"豆粕|soybean|meal|USDA|大豆|"
    r"降准|降息|政治局|证监会|央行|PBOC|Fed|美联储|"
    r"概念|涨停|跌停|板块|沪深|上证|深证|创业板|科创板|北交|"
    r"业绩|公告|重组|增持|减持|分红|券商|研报|调研|"
    r"北向|净流入|ETF|题材|热点|龙头|个股|主力|游资|"
    r"基金|仓位|回购|定增|IPO|注册制",
    re.IGNORECASE
)

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
MAX_ITEMS_PER_FEED = 30  # 每个RSS保留最近30条

# ── 工具函数 ────────────────────────────────────────
def load_processed():
    if PROCESSED_FILE.exists():
        return json.loads(PROCESSED_FILE.read_text())
    return []

def save_processed(items):
    PROCESSED_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2))

def url_hash(url):
    return hashlib.sha1(url.encode()).hexdigest()[:16]

def load_signal_log():
    if SIGNAL_LOG.exists():
        return json.loads(SIGNAL_LOG.read_text())
    return []

def save_signal_log(log):
    SIGNAL_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2))

# ── 核心流程 ────────────────────────────────────────
def fetch_all_feeds():
    """拉取所有信源的文章"""
    all_items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    for src in SOURCES:
        try:
            print(f"📡 正在拉取 {src['name']}: {src['url']}")
            resp = requests.get(src["url"], timeout=30, headers=headers)
            print(f"   状态码: {resp.status_code}, 大小: {len(resp.text)} bytes")

            if src["type"] == "jin10":
                items = parse_jin10(resp.text, src)
            elif src["type"] == "wallstreetcn":
                items = parse_wallstreetcn(resp.json(), src)
            else:
                items = []

            print(f"   解析到 {len(items)} 条目")
            all_items.extend(items)

        except Exception as e:
            print(f"❌ 拉取 {src['name']} 失败: {e}")

    return all_items


def parse_jin10(text, src):
    """解析金十数据 API"""
    items = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return items

    flashes = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(flashes, list):
        flashes = [flashes]

    for f in flashes[:80]:
        if not isinstance(f, dict):
            continue
        content = f.get("content", "") or f.get("data", {}).get("content", "")
        if not content or len(content) < 5:
            continue
        fid = f.get("id", "")
        link = f"https://www.jin10.com/flash/{fid}" if fid else ""
        items.append({
            "title": content[:80],
            "content": content[:1000],
            "link": link,
            "source": src["name"],
            "cat": src["cat"],
            "pub_date": f.get("time", ""),
            "hash": url_hash(content[:60] + link),
        })
    return items


def parse_wallstreetcn(data, src):
    """解析华尔街见闻 API — 按频道提取"""
    items = []
    inner = data.get("data", {})
    if not isinstance(inner, dict):
        return items

    # 关注的频道: commodity(商品), global(宏观), a_stock(A股), forex(外汇)
    channels = ["commodity", "global", "a_stock", "forex"]

    for channel in channels:
        ch_data = inner.get(channel, {})
        if not isinstance(ch_data, dict):
            continue
        ch_items = ch_data.get("items", [])
        if not isinstance(ch_items, list):
            continue
        print(f"   {channel}: {len(ch_items)} 条")

        for item in ch_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content_text", "") or item.get("content", "")
            title = item.get("title", "") or content[:80]
            item_id = item.get("id", "")
            link = f"https://wallstreetcn.com/livenews/{item_id}" if item_id else ""
            if not content or len(content) < 5:
                continue
            ts = item.get("display_time", 0)
            pub_date = ""
            if ts and ts > 1000000000:
                pub_date = datetime.fromtimestamp(ts).strftime("%a, %d %b %Y %H:%M:%S +0800")
            # 按频道分配类别
            cat = src["cat"]
            if channel in ("commodity", "forex"):
                cat = "commodities"
            elif channel in ("a_stock", "global"):
                cat = "both"
            items.append({
                "title": title,
                "content": content[:1000],
                "link": link,
                "source": f"{src['name']}({channel})",
                "cat": cat,
                "pub_date": pub_date,
                "hash": url_hash(content[:60] + link),
            })

    print(f"   解析到 {len(items)} 条")
    return items

def filter_by_keyword(items):
    """关键词过滤"""
    return [it for it in items if KEYWORDS.search(it["title"] + it["content"])]

def dedup(items, processed):
    """去重"""
    new = []
    hashes = {p["hash"] for p in processed}
    for it in items:
        if it["hash"] not in hashes:
            new.append(it)
            hashes.add(it["hash"])
    return new

def call_deepseek(articles):
    """调DeepSeek API批量分析"""
    if not articles:
        return []

    # 构建文章摘要给AI
    article_texts = []
    for i, a in enumerate(articles):
        article_texts.append(
            f"[{i}] 标题:{a['title']} | 来源:{a['source']} | 内容:{a['content'][:500]}"
        )
    combined = "\n---\n".join(article_texts)

    prompt = f"""分析以下财经新闻，每篇返回一个JSON对象。最终返回JSON数组。

每篇格式:
{{
  "idx": 序号,
  "title_cn": "中文标题",
  "summary": "50字以内中文摘要,提取影响价格的核心信息",
  "sentiment": -1到1的小数(负=利空,正=利好,0=中性),
  "impact": 1-5整数(1=噪音,3=值得关注,5=可能驱动大幅波动),
  "commodities": ["GC=F/CL=F/HG=F/AH=F/ZM=F中选,不相关为空"],
  "a_stocks": ["A股代码或板块名称,不涉及为空"],
  "tags": ["库存变化/供应中断/政策变动/地缘政治/财报/天气/行业轮动/资金面中选"],
  "credibility": 1-5整数(1=传闻,5=官方数据),
  "urgency": "即时/当日/本周"
}}

只返回JSON数组,不要其他文字。

文章列表:
{combined}"""

    try:
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是大宗商品和A股情报分析师。分析新闻并返回结构化JSON。区分事实和观点,官方数据可信度高,传闻可信度低。"},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            timeout=60,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        # 提取JSON数组
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except Exception as e:
        print(f"❌ DeepSeek调用失败: {e}")
        return []

def build_rss_xml(channel_title, channel_desc, link_suffix, items):
    """生成RSS 2.0 XML"""
    bj_tz = timezone(timedelta(hours=8))
    now = datetime.now(bj_tz).strftime("%a, %d %b %Y %H:%M:%S +0800")

    # 不带用户名（GitHub Actions环境变量或手动设置）
    gh_user = os.environ.get("GH_USER", "chenheping1974")
    base_url = f"https://{gh_user}.github.io/tv-signals/feeds/{link_suffix}"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{channel_title}</title>
    <link>{base_url}</link>
    <description>{channel_desc}</description>
    <language>zh-CN</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{base_url}" rel="self" type="application/rss+xml"/>
"""

    for item in items[:MAX_ITEMS_PER_FEED]:
        xml += f"""    <item>
      <title>{item['rss_title']}</title>
      <link>{item['link']}</link>
      <description>{item['rss_desc']}</description>
      <pubDate>{item.get('pub_date', now)}</pubDate>
      <guid isPermaLink="false">{item['hash']}</guid>
      <category>{','.join(item.get('tags', []))}</category>
    </item>
"""

    xml += """  </channel>
</rss>"""
    return xml

def generate_rss_items(articles, analysis_results):
    """将分析结果转为RSS条目"""
    rss_items = []
    # 按顺序配对：结果数可能少于文章数（DeepSeek截断），只取能配对的
    if len(analysis_results) < len(articles):
        print(f"   ⚠️ 分析结果({len(analysis_results)})少于文章({len(articles)})，仅配对前{len(analysis_results)}篇")

    for i in range(min(len(articles), len(analysis_results))):
        art = articles[i]
        ai = analysis_results[i]
        ai = analysis_map.get(i, {})
        min_impact = 1 if art["cat"] in ("both", "a-stocks") else 2
        if ai.get("impact", 0) < min_impact:
            continue  # 商品>=2★，A股>=1★

    impacts = [r.get("impact", 0) for r in analysis_results]
    print(f"   AI评分: 0★={impacts.count(0)} 1★={impacts.count(1)} 2★={impacts.count(2)} 3★={impacts.count(3)} 4★={impacts.count(4)} 5★={impacts.count(5)}")
    a_passed = sum(1 for i in range(min(len(articles), len(analysis_results)))
                   if articles[i]["cat"] in ("both", "a-stocks")
                   and analysis_results[i].get("impact", 0) >= 1)
    c_passed = sum(1 for i in range(min(len(articles), len(analysis_results)))
                   if articles[i]["cat"] == "commodities"
                   and analysis_results[i].get("impact", 0) >= 2)
    print(f"   通过: A股>={a_passed} 商品>={c_passed}")

    for i in range(min(len(articles), len(analysis_results))):
        art = articles[i]
        ai = analysis_results[i]
        min_impact = 1 if art["cat"] in ("both", "a-stocks") else 2
        if ai.get("impact", 0) < min_impact:
            continue  # 商品>=2★，A股>=1★

        sentiment_emoji = "🔴" if (ai.get("sentiment", 0) < -0.3) else ("🟢" if ai.get("sentiment", 0) > 0.3 else "🟡")
        impact_stars = "★" * ai.get("impact", 2)
        rss_title = f"[{impact_stars}{sentiment_emoji}] {ai.get('title_cn', art['title'])}"

        commodities = ", ".join(ai.get("commodities", [])) or "无"
        a_stocks = ", ".join(ai.get("a_stocks", [])) or "无"
        tags = ", ".join(ai.get("tags", [])) or "无"
        rss_desc = (
            f"<p><strong>摘要</strong>：{ai.get('summary', '暂无')}</p>"
            f"<p><strong>情绪</strong>：{sentiment_emoji} {ai.get('sentiment', 0)}</p>"
            f"<p><strong>关联商品</strong>：{commodities}</p>"
            f"<p><strong>关联A股</strong>：{a_stocks}</p>"
            f"<p><strong>分类</strong>：{tags}</p>"
            f"<p><strong>可信度</strong>：{'★' * ai.get('credibility', 3)} | 来源: {art['source']} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>"
        )

        rss_items.append({
            "rss_title": rss_title,
            "rss_desc": rss_desc,
            "link": art["link"],
            "pub_date": art.get("pub_date", ""),
            "hash": art["hash"],
            "tags": ai.get("tags", []),
            "cat": art["cat"],
        })

    return rss_items

def write_feeds(new_items):
    """写入RSS XML文件，与已有条目合并"""
    # 加载旧条目（从现有XML文件中解析）
    all_commodities = load_existing_items(FEEDS_DIR / "commodities.xml")
    all_astocks = load_existing_items(FEEDS_DIR / "a-stocks.xml")

    for item in new_items:
        if item["cat"] in ("commodities", "both"):
            all_commodities.insert(0, item)
        if item["cat"] in ("a-stocks", "both"):
            all_astocks.insert(0, item)

    # 去重 + 限制数量
    all_commodities = dedup_items(all_commodities)[:MAX_ITEMS_PER_FEED]
    all_astocks = dedup_items(all_astocks)[:MAX_ITEMS_PER_FEED]

    # 写文件
    commodities_xml = build_rss_xml(
        "大宗商品精选情报",
        "AI精选大宗商品情报 — 黄金·白银·原油·美铜·伦铝·豆粕 | DeepSeek分析 + 影响力评级",
        "commodities.xml",
        all_commodities
    )
    astocks_xml = build_rss_xml(
        "A股精选情报",
        "AI精选A股情报 — 宏观政策·行业板块·个股信号 | DeepSeek分析 + 影响力评级",
        "a-stocks.xml",
        all_astocks
    )

    (FEEDS_DIR / "commodities.xml").write_text(commodities_xml)
    (FEEDS_DIR / "a-stocks.xml").write_text(astocks_xml)
    print(f"✅ 商品Feed: {len(all_commodities)}条, A股Feed: {len(all_astocks)}条")


def load_existing_items(filepath):
    """从现有RSS XML中解析条目"""
    if not filepath.exists():
        return []
    text = filepath.read_text()
    items = []
    # 简单解析item块
    for match in re.finditer(r"<item>(.*?)</item>", text, re.DOTALL):
        block = match.group(1)
        title_m = re.search(r"<title>(.*?)</title>", block)
        link_m = re.search(r"<link>(.*?)</link>", block)
        desc_m = re.search(r"<description>(.*?)</description>", block, re.DOTALL)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", block)
        guid_m = re.search(r"<guid[^>]*>(.*?)</guid>", block)
        items.append({
            "rss_title": title_m.group(1) if title_m else "",
            "rss_desc": desc_m.group(1) if desc_m else "",
            "link": link_m.group(1) if link_m else "",
            "pub_date": pub_m.group(1) if pub_m else "",
            "hash": guid_m.group(1) if guid_m else url_hash(link_m.group(1) if link_m else ""),
            "tags": [],
            "cat": "commodities",  # 从文件名判断，简化处理
        })
    return items

def dedup_items(items):
    """按hash去重"""
    seen = set()
    result = []
    for it in items:
        h = it.get("hash", "")
        if h and h not in seen:
            seen.add(h)
            result.append(it)
    return result


# ── 主函数 ──────────────────────────────────────────
def main():
    print(f"🚀 tv-signals 开始运行 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 拉取
    all_items = fetch_all_feeds()
    print(f"📥 拉取到 {len(all_items)} 篇文章")

    # 2. 过滤
    filtered = filter_by_keyword(all_items)
    # 统计各频道/信源分布
    from collections import Counter
    src_count = Counter(f["source"] for f in filtered)
    print(f"🔍 关键词过滤后: {len(filtered)} 篇")
    for k, v in src_count.most_common():
        print(f"   {k}: {v} 篇")
    cat_count = Counter(f["cat"] for f in filtered)
    print(f"   分类: {dict(cat_count)}")

    # 3. 去重
    processed = load_processed()
    new_items = dedup(filtered, processed)
    print(f"🆕 新文章: {len(new_items)} 篇")

    if not new_items:
        print("✨ 无新文章, 跳过")
        return

    # 4. AI分析 (分批, 每批10篇)
    all_analysis = []
    batch_size = 5
    for i in range(0, len(new_items), batch_size):
        batch = new_items[i : i + batch_size]
        print(f"🤖 DeepSeek分析: {i+1}-{min(i+batch_size, len(new_items))}/{len(new_items)}")
        results = call_deepseek(batch)
        all_analysis.extend(results)
        if i + batch_size < len(new_items):
            time.sleep(2)  # 避免限流

    print(f"📊 分析完成: {len(all_analysis)} 条结果")

    # 5. 生成RSS条目
    rss_items = generate_rss_items(new_items, all_analysis)
    print(f"📝 生成RSS条目: {len(rss_items)} 条 (>=2★)")

    # 6. 写入Feed文件
    write_feeds(rss_items)

    # 7. 更新去重记录
    for it in new_items:
        processed.append({"hash": it["hash"], "url": it["link"], "date": datetime.now().isoformat()})
    # 只保留最近5000条
    processed = processed[-5000:]
    save_processed(processed)

    # 8. 写信号日志
    log = load_signal_log()
    for item in rss_items:
        log.append({"title": item["rss_title"], "date": datetime.now().isoformat()})
    save_signal_log(log[-500:])

    print("✅ 完成!")

if __name__ == "__main__":
    main()
