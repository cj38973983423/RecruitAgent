"""联网搜索服务 — 搜狗搜索（国内可用）"""
import json
import logging
import re
import httpx

logger = logging.getLogger(__name__)

SOGOU_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def sogou_search(query: str, num_results: int = 5) -> list[dict]:
    """搜狗搜索（国内网络环境可用）"""
    try:
        url = "https://www.sogou.com/web"
        params = {"query": query, "num": num_results}
        with httpx.Client(verify=False, timeout=15.0) as client:
            resp = client.get(url, params=params, headers=SOGOU_HEADERS, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"[WebSearch] 搜狗搜索请求失败: {e}")
        return []

    # 解析结果
    results = []
    # 提取所有结果块
    blocks = re.findall(
        r'<div\s+class="(?:vrwrap|vr5|vr_result)[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL
    )
    if not blocks:
        # 兜底：直接找 h3 标题 + 附近文本
        blocks = re.findall(
            r'<h3[^>]*class="vr-title"[^>]*>(.*?)</h3>',
            html, re.DOTALL
        )

    # CSS/脚本正则，用于过滤非正文片段
    _css_or_js = re.compile(r'^\s*(color|margin|padding|font|\.struct|#\w+\s*\{|@media|function\s*\()', re.IGNORECASE)

    def _clean_text(t: str) -> str:
        t = re.sub(r'<[^>]+>', '', t)          # 去 HTML 标签
        t = re.sub(r'\s+', ' ', t).strip()     # 合并空白
        t = re.sub(r'&[a-z]+;', ' ', t)         # 去 HTML 实体
        t = re.sub(r'&\#\d+;', ' ', t)          # 去数字实体
        t = re.sub(r'[\ue000-\uf8ff]', '', t)   # 去私用区字符（乱码）
        t = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""''（）【】《》\-+,\.;:!?()\[\]{}@/ ]', ' ', t)
        t = re.sub(r'\s{2,}', ' ', t).strip()
        return t

    def _is_useful_text(t: str) -> bool:
        t = t.strip()
        return (len(t) > 15
                and not _css_or_js.match(t)
                and not t.startswith(('.', '#', '@media', 'function')))

    for block in blocks[:num_results]:
        title_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
        title = _clean_text(title_match.group(1)) if title_match else ""

        # 找摘要
        snippet = ""
        # 优先找 <p class="str_text_info">
        snippet_match = re.search(r'<p\s+class="str_text_info"[^>]*>(.*?)</p>', block, re.DOTALL)
        if snippet_match:
            snippet = _clean_text(snippet_match.group(1))
        else:
            # 在块内找有用文本
            texts = re.findall(r'>([^<]{20,500})<', block)
            for t in texts:
                t = _clean_text(t)
                if _is_useful_text(t) and t != title:
                    snippet = t
                    break

        if title or snippet:
            results.append({
                "title": title[:120],
                "snippet": snippet[:400],
                "url": "",
            })

    # 兜底：从全文提取有用文本
    if not results:
        texts = re.findall(r'>([^<]{30,400})<', html)
        seen = set()
        for t in texts:
            t = _clean_text(t)
            if _is_useful_text(t) and t not in seen:
                seen.add(t)
                skip_kw = ["搜索", "广告", "下一页", "相关搜索", "导航", "设置首页", "加入收藏"]
                if any(kw in t for kw in skip_kw):
                    continue
                results.append({
                    "title": t[:60],
                    "snippet": t[:400],
                    "url": "",
                })

    logger.info(f"[WebSearch] 搜狗搜索「{query}」→ {len(results)} 条结果")
    return results[:num_results]


if __name__ == "__main__":
    results = sogou_search("AI算法工程师 岗位职责", 5)
    print(f"结果: {len(results)} 条")
    for r in results:
        print(f"  标题: {r['title']}")
        print(f"  摘要: {r['snippet'][:80]}")
        print()
