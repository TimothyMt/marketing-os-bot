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
    "market_research":    {"title": "Nghiên cứu Thị trường",       "icon": "📊", "color": "market"},
    "competitor":         {"title": "Phân tích Đối thủ",            "icon": "🕵️", "color": "competitor"},
    "customer_insight":   {"title": "Customer Insight & ICP",      "icon": "👥", "color": "customer"},
    "psychology_pricing": {"title": "Marketing Psychology & Pricing", "icon": "💡", "color": "pricing"},
    "social_listening":   {"title": "Social Listening System",     "icon": "📡", "color": "market"},
    "synthesis":          {"title": "Marketing Strategy",          "icon": "🚀", "color": "strategy"},
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

/* Tabs navigation */
.tabs {
  display: flex; gap: 4px; background: white;
  padding: 6px; border-radius: 12px; margin-bottom: 20px;
  overflow-x: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  scrollbar-width: thin;
}
.tab-btn {
  padding: 10px 16px; border: none; background: transparent;
  cursor: pointer; font-size: 13px; font-weight: 500; color: var(--muted);
  white-space: nowrap; border-radius: 8px; transition: all 0.15s;
  font-family: inherit;
}
.tab-btn:hover { background: #f1f5f9; color: var(--text); }
.tab-btn.active {
  background: var(--primary); color: white; font-weight: 600;
}

/* Section visibility */
.section {
  display: none;
  background: var(--card); border-radius: 12px; padding: 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-left: 4px solid var(--primary);
  animation: fadeIn 0.25s ease;
}
.section.active { display: block; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
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

.content { margin-top: 16px; }
.content h1, .content h2, .content h3, .content h4 {
  margin: 20px 0 10px; font-weight: 600; color: var(--text);
}
.content h1 { font-size: 22px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.content h2 { font-size: 18px; }
.content h3 { font-size: 16px; color: var(--primary); }
.content h4 { font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.content p { margin-bottom: 12px; }
.content ul, .content ol { margin: 8px 0 12px 24px; }
.content li { margin-bottom: 6px; }
.content strong { font-weight: 700; color: var(--text); }
.content em { color: var(--muted); }
.content table {
  width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;
  background: white; border-radius: 8px; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.content th, .content td {
  padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border);
}
.content th {
  background: #f1f5f9; font-weight: 600; font-size: 12px;
  text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px;
}
.content tr:last-child td { border-bottom: none; }
.content tr:hover { background: #f8fafc; }
.content blockquote {
  border-left: 4px solid var(--accent); padding: 14px 18px; margin: 14px 0;
  background: #fffbeb; color: #78350f; font-style: italic; border-radius: 4px;
}

.footer {
  text-align: center; color: var(--muted); font-size: 12px;
  padding: 24px 16px; margin-top: 16px; line-height: 1.7;
}

/* Mobile */
@media (max-width: 640px) {
  body { padding: 12px 8px; }
  .header { padding: 24px 20px; border-radius: 12px; }
  .header h1 { font-size: 22px; }
  .section { padding: 20px 16px; }
  .tab-btn { padding: 8px 12px; font-size: 12px; }
  .content table { font-size: 13px; }
  .content th, .content td { padding: 8px 10px; }
}
"""


JS = """
function showSection(id, btn) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Marketing Report — {business_name}</title>
<style>{css}</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>📊 Marketing Strategy Report</h1>
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
<script>{js}</script>
</body>
</html>"""


def _md_to_html(text: str) -> str:
    """Convert markdown → HTML. Falls back to <pre> if no markdown lib available."""
    if not text:
        return ""
    if HAS_MARKDOWN:
        return _md.markdown(text, extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
    # Fallback: basic conversion
    out = text
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    out = out.replace("\n\n", "</p><p>")
    out = out.replace("\n", "<br>")
    return f"<p>{out}</p>"


def parse_agent_output(text: str) -> dict:
    """Extract structured sections from agent output.
    Returns {insight, summary, benchmarks, detail} — all strings (markdown)."""
    result = {"insight": "", "summary": "", "benchmarks": "", "detail": ""}

    patterns = {
        "insight":    r"##\s*💡[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "summary":    r"##\s*🎯[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "benchmarks": r"##\s*📊[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "detail":     r"##\s*📄[^\n]*\n+(.*?)(?=\n##\s|\Z)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.DOTALL)
        if m:
            result[key] = m.group(1).strip()

    # Fallback: if nothing parsed, treat all as detail
    if not any(result.values()):
        result["detail"] = text.strip()

    return result


def render_stage_html(stage_key: str, parsed: dict, idx: int) -> str:
    """Render one stage as a tabbed section. idx is the tab index (0-based)."""
    meta = STAGE_META.get(stage_key, {"title": stage_key, "icon": "📄", "color": ""})
    section_id = f"section-{stage_key}"
    active_cls = " active" if idx == 0 else ""

    # Order: Insight (hook) → Detail (full) → Summary (recap) → Benchmarks (data ref at bottom)
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
<div id="{section_id}" class="section {meta['color']}{active_cls}">
  <div class="section-header">
    <span class="icon">{meta['icon']}</span>
    <h2>{meta['title']}</h2>
  </div>
  {body}
</div>"""


def render_tab_button(stage_key: str, idx: int) -> str:
    """Render a single tab button."""
    meta = STAGE_META.get(stage_key, {"title": stage_key, "icon": "📄"})
    section_id = f"section-{stage_key}"
    active_cls = " active" if idx == 0 else ""
    label = f"{meta['icon']} {meta['title']}"
    return f'<button class="tab-btn{active_cls}" onclick="showSection(\'{section_id}\', this)">{label}</button>'


def build_report(
    business_name: str,
    industry: str,
    stage: str,
    parsed_stages: list[tuple[str, dict]],
) -> str:
    """Render full HTML report with tabbed navigation.
    parsed_stages: list of (stage_key, parsed_dict) in pipeline order."""
    tabs_html = "\n    ".join(
        render_tab_button(k, i) for i, (k, _) in enumerate(parsed_stages)
    )
    sections_html = "\n".join(
        render_stage_html(k, p, i) for i, (k, p) in enumerate(parsed_stages)
    )
    return HTML_TEMPLATE.format(
        business_name=business_name or "Business",
        industry=industry or "—",
        stage=stage or "—",
        date=datetime.now().strftime("%d/%m/%Y · %H:%M"),
        tabs_html=tabs_html,
        sections_html=sections_html,
        css=CSS,
        js=JS,
    )
