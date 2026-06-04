"""
HTML report generator for Marketing OS analysis output.
Bundles structured agent outputs into 1 styled HTML document.
"""
import re
from datetime import datetime

try:
    import markdown as _md
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


STAGE_META = {
    # Strategic skills — by stage_key (used in full pipeline + ops result rendering)
    "market_research":    {"title": "Nghiên cứu Thị trường",       "icon": "📊", "color": "market"},
    "competitor":         {"title": "Phân tích Đối thủ",            "icon": "🕵️", "color": "competitor"},
    "customer_insight":   {"title": "Customer Insight & ICP",      "icon": "👥", "color": "customer"},
    "psychology_pricing": {"title": "Marketing Psychology & Pricing", "icon": "💡", "color": "pricing"},
    "social_listening":   {"title": "Social Listening System",     "icon": "📡", "color": "market"},
    "usp_definition":     {"title": "USP Definition",                "icon": "🎯", "color": "strategy"},
    "retention_strategy": {"title": "Retention Strategy",            "icon": "🔄", "color": "customer"},
    "winback_campaign":   {"title": "Winback Vision",                "icon": "🔁", "color": "customer"},
    "synthesis":          {"title": "Marketing Strategy",          "icon": "🚀", "color": "strategy"},
    # Strategic single-shot task aliases (Phase 3 — task names used in handler dispatch)
    "market":             {"title": "Nghiên cứu Thị trường",       "icon": "📊", "color": "market"},
    "customer":           {"title": "Customer Insight & ICP",      "icon": "👥", "color": "customer"},
    "pricing":            {"title": "Marketing Psychology & Pricing", "icon": "💡", "color": "pricing"},
    "strategy":           {"title": "Marketing Strategy",          "icon": "🎯", "color": "strategy"},
    # Operational skills
    "campaign_brief":      {"title": "Viết Brief Campaign",         "icon": "📋", "color": "strategy"},
    "content_calendar":    {"title": "Lịch Nội Dung",               "icon": "📅", "color": "market"},
    "content_generator":   {"title": "Sản Xuất Nội Dung",           "icon": "✍️", "color": "customer"},
    "ads_copy":            {"title": "Sản Xuất Nội Dung Ads",       "icon": "📢", "color": "pricing"},
    "ads_generator":       {"title": "Sản Xuất Nội Dung Ads",       "icon": "📢", "color": "pricing"},
    "video_scripts":       {"title": "Viết Kịch Bản Video",         "icon": "🎬", "color": "customer"},
    "landing_page":        {"title": "Thiết Kế Website",            "icon": "🌐", "color": "competitor"},
    "sales_inbox_script":  {"title": "Kịch Bản Sales",              "icon": "💬", "color": "customer"},
    "email_zalo_sequence": {"title": "Chăm Sóc Khách Hàng",         "icon": "📧", "color": "pricing"},
    "competitor_spy":      {"title": "Theo Dõi Đối Thủ",            "icon": "🔍", "color": "competitor"},
    "competitor_comparison": {"title": "So Sánh Với Đối Thủ",         "icon": "🆚", "color": "competitor"},
    "performance_audit":   {"title": "Báo Cáo Ads",                 "icon": "📊", "color": "strategy"},
    "campaign_plan":       {"title": "Kế Hoạch Triển Khai Campaign", "icon": "🗺️", "color": "strategy"},
}


CSS = """
:root {
  --primary: #2563eb; --accent: #f59e0b; --bg: #fafafa; --card: #ffffff;
  --text: #1e293b; --muted: #64748b; --border: #e2e8f0;
  --success: #10b981;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.65; padding: 24px 16px;
}
.container { max-width: 880px; margin: 0 auto; }

.header {
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: white; padding: 32px 28px; border-radius: 16px; margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(37,99,235,0.15);
}
.header h1 { font-size: 26px; font-weight: 700; margin-bottom: 6px; }
.header .meta { font-size: 14px; opacity: 0.9; }
.header .powered { margin-top: 14px; font-size: 11px; opacity: 0.7; }

/* CSS-only tabs (radio buttons + :checked, no JS) */
.tab-state { display: none !important; }  /* hide radio inputs */

.tabs {
  display: flex; gap: 4px; background: white;
  padding: 6px; border-radius: 12px; margin-bottom: 20px;
  overflow-x: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  scrollbar-width: thin;
}
.tab-btn {
  padding: 10px 16px; background: transparent;
  cursor: pointer; font-size: 13px; font-weight: 500; color: var(--muted);
  white-space: nowrap; border-radius: 8px; transition: all 0.15s;
  display: inline-flex; align-items: center; gap: 6px;
}
.tab-btn:hover { background: #f1f5f9; color: var(--text); }

/* Sections start hidden, shown when matching radio is checked */
.section {
  display: none;
  background: var(--card); border-radius: 12px; padding: 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-left: 4px solid var(--primary);
}
.section.market    { border-color: #2563eb; }
.section.competitor{ border-color: #f59e0b; }
.section.customer  { border-color: #10b981; }
.section.pricing   { border-color: #ec4899; }
.section.strategy  { border-color: #8b5cf6; }

.section-header {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
}
.section-header .icon { font-size: 28px; }
.section-header h2 { font-size: 22px; font-weight: 600; }

.insight {
  background: #fef3c7; border-left: 4px solid var(--accent);
  padding: 16px 20px; border-radius: 6px; margin: 16px 0;
  font-style: italic; color: #78350f; font-size: 15px; line-height: 1.6;
}
.insight::before { content: "💡 "; font-style: normal; font-weight: 600; }

.summary, .benchmarks {
  background: #f0f9ff; border-left: 3px solid var(--primary);
  padding: 16px 20px; border-radius: 8px; margin: 14px 0;
}
.summary-label, .benchmarks-label {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  color: var(--primary); letter-spacing: 0.5px; margin-bottom: 10px;
}
.summary ul, .benchmarks ul { margin-left: 20px; }
.summary p, .benchmarks p { margin-bottom: 6px; }

.content { margin-top: 16px; line-height: 1.7; }

/* Reset shared rule — mỗi level tự định nghĩa riêng */
.content h1, .content h2, .content h3, .content h4 {
  font-weight: 700; color: var(--text); line-height: 1.3;
}

/* h1 — title cấp section (hiếm dùng trong content) */
.content h1 {
  font-size: 22px; margin: 36px 0 14px;
  padding-bottom: 8px; border-bottom: 2px solid var(--primary);
}

/* h2 — đề mục lớn trong tab */
.content h2 {
  font-size: 19px; margin: 32px 0 12px; color: var(--text);
  padding-bottom: 6px; border-bottom: 1px solid var(--border);
}

/* h3 — phần chính (TAM, Tier 1, ICP...) — phải nổi bật nhất trong content */
.content h3 {
  font-size: 15px; font-weight: 700;
  margin: 30px 0 10px;
  padding: 9px 14px;
  background: #eff6ff;
  border-left: 4px solid var(--primary);
  border-radius: 0 6px 6px 0;
  color: #1e3a8a;
  text-transform: none;
}

/* h4 — sub-section label nổi bật (Messaging Gap, Channel Gap, Tier 1...) */
.content h4 {
  font-size: 13px; font-weight: 700;
  margin: 24px 0 10px;
  display: inline-block;
  padding: 3px 10px 3px 0;
  color: var(--text);
  text-transform: uppercase; letter-spacing: 0.6px;
  border-bottom: 2px solid var(--accent);
}

.content p { margin-bottom: 14px; font-size: 15px; }
.content ul, .content ol { margin: 6px 0 14px 26px; }
.content li { margin-bottom: 8px; font-size: 15px; line-height: 1.65; }
.content strong { font-weight: 700; color: var(--text); }
.content em { color: var(--muted); }
.content .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 20px 0; }
.content table {
  width: 100%; border-collapse: collapse; font-size: 14px;
  background: white; border-radius: 8px; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04); min-width: 480px;
}
.content th, .content td {
  padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.content td { white-space: normal; min-width: 80px; }
.content th {
  background: #f1f5f9; font-weight: 700; font-size: 12px;
  text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px;
  white-space: nowrap;
}
.content tr:last-child td { border-bottom: none; }
.content tr:hover { background: #f8fafc; }
.content blockquote {
  border-left: 4px solid var(--accent); padding: 14px 18px; margin: 18px 0;
  background: #fffbeb; color: #78350f; font-style: italic; border-radius: 4px;
  font-size: 15px;
}
.content a {
  color: var(--primary); text-decoration: none;
  border-bottom: 1px solid #bfdbfe; padding-bottom: 1px;
}
.content a:hover { border-bottom-color: var(--primary); }
.content pre {
  background: #f8fafc; border: 1px solid var(--border); border-radius: 8px;
  padding: 16px; margin: 18px 0; overflow-x: auto;
  font-size: 12.5px; line-height: 1.5; color: #334155;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
.content pre code { background: none; padding: 0; font-size: inherit; }

.footer {
  text-align: center; color: var(--muted); font-size: 12px;
  padding: 24px 16px; margin-top: 16px; line-height: 1.7;
}

/* === Positioning Map Visual === */
.pos-map-wrap { margin: 24px 0; font-family: inherit; }
.pos-map-title { font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 8px; }
.pos-y-lbl { text-align: center; font-size: 12px; font-weight: 600; color: var(--muted); padding: 4px 0; }
.pos-quads {
  display: grid; grid-template-columns: 1fr 1fr;
  border: 2px solid var(--border); border-radius: 10px; overflow: hidden;
}
.pos-q { padding: 14px; min-height: 100px; }
.pq2 { background: #eff6ff; border-right: 2px solid #bfdbfe; border-bottom: 2px solid #bfdbfe; }
.pq1 { background: #f0fdf4; border-bottom: 2px solid #bbf7d0; }
.pq3 { background: #fefce8; border-right: 2px solid #fde68a; }
.pq4 { background: #fdf4ff; }
.pos-q-lbl { font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; letter-spacing: 0.5px; }
.pos-q-desc { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 8px; line-height: 1.4; }
.pos-q-items { display: flex; flex-wrap: wrap; gap: 5px; }
.pos-item { font-size: 12px; padding: 3px 9px; border-radius: 12px; background: rgba(255,255,255,0.8); border: 1px solid rgba(0,0,0,0.1); color: var(--text); }
.pos-item-self { background: var(--primary) !important; color: white !important; border-color: var(--primary) !important; font-weight: 600; }
.pos-x-axis { display: flex; align-items: center; gap: 10px; margin-top: 8px; font-size: 12px; font-weight: 600; color: var(--muted); }
.pos-x-l, .pos-x-r { flex-shrink: 0; }
.pos-x-line { flex: 1; height: 2px; background: var(--border); }

/* Mobile */
@media (max-width: 640px) {
  body { padding: 12px 8px; }
  .header { padding: 24px 20px; border-radius: 12px; }
  .header h1 { font-size: 22px; }
  .section { padding: 20px 16px; }
  .tab-btn { padding: 8px 12px; font-size: 12px; }
  .content h3 { font-size: 14px; padding: 7px 12px; }
  .content table { font-size: 13px; }
  .content th, .content td { padding: 8px 10px; }
  .pos-q { padding: 10px; min-height: 80px; }
  .pos-q-desc { font-size: 11px; }
}
"""


POS_MAP_SCRIPT = """<script>
(function() {
  function isMap(t) {
    return t.indexOf('^') >= 0 && /GÓC/i.test(t);
  }
  function roman(n) { return ['I','II','III','IV'][n-1] || String(n); }
  function fromRoman(s) {
    return {'I':1,'II':2,'III':3,'IV':4}[(s||'').toUpperCase().trim()] || 0;
  }
  function parseMap(text) {
    var lines = text.split('\\n'), n = lines.length;
    var hIdx = -1;
    for (var i = 0; i < n; i++) {
      if (/[-─]{4,}/.test(lines[i])) { hIdx = i; break; }
    }
    if (hIdx < 0) return null;
    var cols = {}, vCol = 0, mx = 0;
    lines.forEach(function(l) {
      for (var j = 0; j < l.length; j++) if (l[j] === '|') cols[j] = (cols[j]||0) + 1;
    });
    Object.keys(cols).forEach(function(j) { if (cols[j] > mx) { mx = cols[j]; vCol = +j; } });
    if (!mx) vCol = Math.floor((lines[hIdx]||'').length / 2);
    var yTop = '', yBottom = '', xRight = '', xLeft = '';
    for (var i = 0; i < hIdx; i++) {
      if (lines[i].indexOf('^') >= 0) {
        var t = lines[i].replace(/\^/g,'').replace(/\|/g,'').trim();
        yTop = t || (i > 0 ? lines[i-1].replace(/\|/g,'').trim() : '');
        break;
      }
    }
    for (var i = hIdx + 1; i < n; i++) {
      if (/^\\s*v\\s*$/.test(lines[i]) || lines[i].trim() === 'v') {
        yBottom = (i+1 < n ? lines[i+1] : '').replace(/\\|/g,'').trim();
        break;
      }
    }
    var axL = lines[hIdx] || '';
    var ar = axL.match(/[-─>]+\\s*(.+)$/); if (ar) xRight = ar[1].trim();
    var lr = axL.match(/^([^─\\-|+]+)[-─]/); if (lr) xLeft = lr[1].trim();
    var qdesc = {1:'',2:'',3:'',4:''};
    var gr = /GÓC\\s*(IV|III|II|I)\\s*[:\\-—\\(]?\\s*([^\\n|\\)]{0,60})/gi, gm;
    while ((gm = gr.exec(text)) !== null) {
      var num = fromRoman(gm[1]);
      if (num >= 1 && num <= 4) qdesc[num] = gm[2].replace(/[\\)\\]]/g,'').trim();
    }
    var items = {1:[],2:[],3:[],4:[]}, seen = {1:[],2:[],3:[],4:[]};
    for (var row = 0; row < n; row++) {
      if (row === hIdx) continue;
      var line = lines[row], isTop = row < hIdx;
      var ir = /(?:[•·●♦★→]|\\[)([^\\]•·●♦★→\\n|]{2,35})(?:\\])?/g, im;
      while ((im = ir.exec(line)) !== null) {
        var item = im[1].trim().replace(/[\\[\\]\\(\\)]/g,'');
        if (!item || /GÓC|TRỐNG/i.test(item)) continue;
        var q = isTop ? (im.index >= vCol ? 1 : 2) : (im.index >= vCol ? 4 : 3);
        if (seen[q].indexOf(item) < 0) { seen[q].push(item); items[q].push(item); }
      }
    }
    return {yTop:yTop, yBottom:yBottom, xRight:xRight, xLeft:xLeft, qdesc:qdesc, items:items};
  }
  function mk(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function buildEl(map) {
    var w = mk('div','pos-map-wrap');
    w.appendChild(mk('div','pos-map-title','📍 Bản đồ Định vị Cạnh tranh'));
    if (map.yTop) w.appendChild(mk('div','pos-y-lbl top','↑ ' + map.yTop));
    var qg = mk('div','pos-quads');
    [[2,'pq2'],[1,'pq1'],[3,'pq3'],[4,'pq4']].forEach(function(p) {
      var qn = p[0], q = mk('div','pos-q ' + p[1]);
      q.appendChild(mk('div','pos-q-lbl','GÓC ' + roman(qn)));
      if (map.qdesc[qn]) q.appendChild(mk('div','pos-q-desc', map.qdesc[qn]));
      var qi = mk('div','pos-q-items');
      map.items[qn].forEach(function(it) {
        var isSelf = /SếP|sếp|★|self/.test(it);
        qi.appendChild(mk('span','pos-item' + (isSelf ? ' pos-item-self' : ''), it));
      });
      q.appendChild(qi);
      qg.appendChild(q);
    });
    w.appendChild(qg);
    if (map.yBottom) w.appendChild(mk('div','pos-y-lbl bot','↓ ' + map.yBottom));
    if (map.xLeft || map.xRight) {
      var xa = mk('div','pos-x-axis');
      if (map.xLeft) xa.appendChild(mk('span','pos-x-l','← ' + map.xLeft));
      xa.appendChild(mk('div','pos-x-line'));
      if (map.xRight) xa.appendChild(mk('span','pos-x-r', map.xRight + ' →'));
      w.appendChild(xa);
    }
    return w;
  }
  document.querySelectorAll('pre').forEach(function(pre) {
    var text = (pre.querySelector('code') || pre).textContent || '';
    if (!isMap(text)) return;
    var map = parseMap(text);
    if (!map) return;
    pre.parentNode.replaceChild(buildEl(map), pre);
  });
})();
</script>"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{report_title} — {business_name}</title>
<style>{css}
{tab_rules}</style>
</head>
<body>
<div class="container">

  {radio_inputs}

  <div class="header">
    <h1>{report_title}</h1>
    <div class="meta">
      🏢 <strong>{business_name}</strong> · {industry} · Stage: {stage}<br>
      📅 {date}
    </div>
    <div class="powered">Powered by Max — AI CMO · Marketing OS</div>
  </div>

  <div class="tabs">
    {tabs_html}
  </div>

  {sections_html}

  <div class="footer">
    Generated by <strong>Max — AI CMO</strong> · Marketing OS<br>
    Phân tích dựa trên thông tin business + framework KPI / SAVE / SMART<br>
    Không phải lời khuyên đầu tư — cross-check thực tế trước khi quyết định lớn
  </div>

</div>
{pos_map_script}
</body>
</html>"""


def _ensure_blank_line_before_tables(text: str) -> str:
    """Python-Markdown chỉ render bảng khi có DÒNG TRỐNG ngay trước bảng.
    LLM thường viết 'Tuần 1 ...\\n| Ngày | Kênh |' (không có dòng trống) → bảng
    bị render thành text thô với dấu '|'. Chèn 1 dòng trống trước mỗi block bảng."""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        is_table_row = line.lstrip().startswith("|")
        if is_table_row and out:
            prev = out[-1]
            prev_is_table = prev.lstrip().startswith("|")
            # Dòng trước là text thường (không trống, không phải row bảng) → chèn blank
            if prev.strip() and not prev_is_table:
                out.append("")
        out.append(line)
    return "\n".join(out)


def _md_to_html(text: str) -> str:
    """Convert markdown → HTML. Falls back to <pre> if no markdown lib available."""
    if not text:
        return ""
    if HAS_MARKDOWN:
        text = _ensure_blank_line_before_tables(text)
        html = _md.markdown(text, extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
        # Wrap <table> in scroll container so wide tables (e.g. 11-col calendar) scroll on mobile
        html = re.sub(r"<table>", '<div class="table-wrap"><table>', html)
        html = re.sub(r"</table>", "</table></div>", html)
        return html
    # Fallback: basic conversion
    out = text
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    out = out.replace("\n\n", "</p><p>")
    out = out.replace("\n", "<br>")
    return f"<p>{out}</p>"


def parse_agent_output(text: str) -> dict:
    """Extract structured sections from agent output.
    Returns {insight, summary, benchmarks, detail} — all strings (markdown).
    Matches by emoji OR keyword (lenient — LLM có thể dùng emoji khác)."""
    result = {"insight": "", "summary": "", "benchmarks": "", "detail": ""}

    # Lenient patterns: match emoji OR keyword
    patterns = {
        "insight":    r"##\s*(?:💡|🔑|⭐|✨)?\s*Insight[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "summary":    r"##\s*(?:🎯|📌|📝)?\s*(?:Tóm tắt|Tom tat|Summary)[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "benchmarks": r"##\s*(?:📊|📈|📉)?\s*(?:Benchmarks?|KPIs?|Số liệu)[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "detail":     r"##\s*(?:📄|📋|📑|🔍|🧠)?\s*(?:Phân tích chi tiết|Phan tich|Detail|Chi tiết|Full analysis)[^\n]*\n+(.*?)(?=\n##\s|\Z)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            result[key] = m.group(1).strip()

    # Heuristic: nếu chỉ có 3 sections nhưng output dài hơn nhiều → còn nội dung không có header
    if not result["detail"] and (result["insight"] or result["summary"] or result["benchmarks"]):
        # Lấy phần text NGOÀI 3 sections đã extract — coi như detail
        used_text = " ".join([result["insight"], result["summary"], result["benchmarks"]])
        # Tìm tất cả ## headers, lấy content sau header cuối cùng
        all_headers = list(re.finditer(r"##\s+[^\n]+", text))
        if all_headers:
            # Lấy phần sau header cuối — nếu phần đó dài >300 chars và chưa match section khác
            last = all_headers[-1]
            tail = text[last.end():].strip()
            if len(tail) > 300 and tail[:200] not in used_text:
                result["detail"] = tail

    # Fallback: nếu vẫn không có gì parsed → toàn bộ text là detail
    if not any(result.values()):
        result["detail"] = text.strip()

    return result


def render_stage_html(stage_key: str, parsed: dict, idx: int) -> str:
    """Render one stage as a CSS-only tabbed section with data-idx attribute."""
    meta = STAGE_META.get(stage_key, {"title": stage_key, "icon": "📄", "color": ""})

    # Order: Insight (hook) → Detail (full) → Summary (recap) → Benchmarks (bottom)
    parts = []
    if parsed.get("insight"):
        insight = parsed["insight"].strip().strip('"').strip("'")
        parts.append(f'<div class="insight">{_md_to_html(insight)}</div>')
    if parsed.get("detail"):
        parts.append(f'<div class="content">{_md_to_html(parsed["detail"])}</div>')
    if parsed.get("summary"):
        parts.append('<div class="summary"><div class="summary-label">📌 Tóm tắt</div>'
                     f'{_md_to_html(parsed["summary"])}</div>')
    if parsed.get("benchmarks"):
        parts.append('<div class="benchmarks"><div class="benchmarks-label">📊 Benchmarks</div>'
                     f'{_md_to_html(parsed["benchmarks"])}</div>')

    body = "\n".join(parts)
    return f"""
<div class="section {meta['color']}" data-idx="{idx}">
  <div class="section-header">
    <span class="icon">{meta['icon']}</span>
    <h2>{meta['title']}</h2>
  </div>
  {body}
</div>"""


def _generate_tab_css(n: int) -> str:
    """Generate per-tab CSS rules: when radio i is checked, show section i + highlight button i."""
    rules = []
    for i in range(n):
        rules.append(
            f"#tab-{i}:checked ~ .section[data-idx='{i}'] {{ display: block; }}"
        )
        rules.append(
            f"#tab-{i}:checked ~ .tabs label[for='tab-{i}'] "
            f"{{ background: var(--primary); color: white; font-weight: 600; }}"
        )
    return "\n".join(rules)


def build_single_skill_report(
    skill_key: str,
    parsed: dict,
    output_format,  # OutputFormat enum
    business_name: str = "",
    industry: str = "",
    stage: str = "",
) -> str:
    """Render HTML for a standalone skill output (operational skills).
    Single tab, single section — no aggregate report."""
    from agents.skills import OutputFormat

    meta = STAGE_META.get(skill_key, {"title": skill_key, "icon": "📄", "color": ""})

    # Compose section body based on output format
    parts = []
    if output_format == OutputFormat.OPERATIONAL_DELIVERABLE:
        if parsed.get("summary"):
            parts.append('<div class="summary"><div class="summary-label">🎯 Tóm tắt nhanh</div>'
                         f'{_md_to_html(parsed["summary"])}</div>')
        if parsed.get("deliverable"):
            parts.append(f'<div class="content">{_md_to_html(parsed["deliverable"])}</div>')
    elif output_format == OutputFormat.OPERATIONAL_ANALYSIS:
        # Order: Summary → KPI table → Root cause → Actions → Forecast
        if parsed.get("summary"):
            parts.append(f'<div class="insight">{_md_to_html(parsed["summary"])}</div>')
        if parsed.get("kpi_table"):
            parts.append('<div class="content"><h2>📈 Kết quả vs KPI</h2>'
                         f'{_md_to_html(parsed["kpi_table"])}</div>')
        if parsed.get("root_cause"):
            parts.append('<div class="content"><h2>🔬 Phân tích nguyên nhân</h2>'
                         f'{_md_to_html(parsed["root_cause"])}</div>')
        if parsed.get("actions"):
            parts.append('<div class="content"><h2>🎯 Next Actions</h2>'
                         f'{_md_to_html(parsed["actions"])}</div>')
        if parsed.get("forecast"):
            parts.append('<div class="content"><h2>📉 Dự báo</h2>'
                         f'{_md_to_html(parsed["forecast"])}</div>')
    else:
        # Strategic 4-section fallback
        if parsed.get("insight"):
            insight = parsed["insight"].strip().strip('"').strip("'")
            parts.append(f'<div class="insight">{_md_to_html(insight)}</div>')
        if parsed.get("detail"):
            parts.append(f'<div class="content">{_md_to_html(parsed["detail"])}</div>')
        if parsed.get("summary"):
            parts.append('<div class="summary"><div class="summary-label">📌 Tóm tắt</div>'
                         f'{_md_to_html(parsed["summary"])}</div>')
        if parsed.get("benchmarks"):
            parts.append('<div class="benchmarks"><div class="benchmarks-label">📊 Benchmarks</div>'
                         f'{_md_to_html(parsed["benchmarks"])}</div>')

    body = "\n".join(parts)
    section_html = f"""
<div class="section {meta['color']} active" data-idx="0">
  <div class="section-header">
    <span class="icon">{meta['icon']}</span>
    <h2>{meta['title']}</h2>
  </div>
  {body}
</div>"""

    # Single tab with skill name
    radio = f'<input type="radio" name="tab" id="tab-0" class="tab-state" checked>'
    tab_label = (
        f'<label for="tab-0" class="tab-btn">'
        f'<span>{meta["icon"]}</span> {meta["title"]}'
        f'</label>'
    )

    return HTML_TEMPLATE.format(
        report_title=f"{meta['icon']} {meta['title']}",
        business_name=business_name or "Business",
        industry=industry or "—",
        stage=stage or "—",
        date=datetime.now().strftime("%d/%m/%Y · %H:%M"),
        radio_inputs=radio,
        tabs_html=tab_label,
        sections_html=section_html,
        css=CSS,
        tab_rules=_generate_tab_css(1),
        pos_map_script=POS_MAP_SCRIPT,
    )


def build_report(
    business_name: str,
    industry: str,
    stage: str,
    parsed_stages: list[tuple[str, dict]],
) -> str:
    """Render full HTML report with CSS-only tab navigation (radio buttons, no JS)."""
    n = len(parsed_stages)

    # Radio inputs at top — first one checked
    radio_inputs = "\n  ".join(
        f'<input type="radio" name="tab" id="tab-{i}" class="tab-state"'
        + (' checked' if i == 0 else '')
        + '>'
        for i in range(n)
    )

    # Tab labels (act as clickable buttons via <label for="...">)
    tab_labels = []
    for i, (k, _) in enumerate(parsed_stages):
        meta = STAGE_META.get(k, {"title": k, "icon": "📄"})
        tab_labels.append(
            f'<label for="tab-{i}" class="tab-btn">'
            f'<span>{meta["icon"]}</span> {meta["title"]}'
            f'</label>'
        )
    tabs_html = "\n    ".join(tab_labels)

    # Section blocks
    sections_html = "\n".join(
        render_stage_html(k, p, i) for i, (k, p) in enumerate(parsed_stages)
    )

    # Dynamic title: nhiều skill = full report; 1 skill = tên skill cụ thể
    if n == 1:
        single_meta = STAGE_META.get(parsed_stages[0][0], {"title": parsed_stages[0][0], "icon": "📄"})
        report_title = f"{single_meta['icon']} {single_meta['title']}"
    elif n >= 5:  # full A→Z pipeline (5+ stages)
        report_title = "📊 Marketing Strategy Report"
    else:
        # 2-4 skills → liệt kê
        titles = []
        for k, _ in parsed_stages[:3]:
            m = STAGE_META.get(k, {"title": k})
            titles.append(m["title"])
        report_title = "📊 " + " · ".join(titles) + (f" + {n-3}" if n > 3 else "")

    return HTML_TEMPLATE.format(
        report_title=report_title,
        business_name=business_name or "Business",
        industry=industry or "—",
        stage=stage or "—",
        date=datetime.now().strftime("%d/%m/%Y · %H:%M"),
        radio_inputs=radio_inputs,
        tabs_html=tabs_html,
        sections_html=sections_html,
        css=CSS,
        tab_rules=_generate_tab_css(n),
        pos_map_script=POS_MAP_SCRIPT,
    )
