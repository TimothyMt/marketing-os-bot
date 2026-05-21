"""
Output renderers — convert parsed agent output to deliverable formats.

Per-skill primary_deliverable determines which format is sent as main attachment:
  - HTML: all skills support (general purpose, mobile-safe)
  - EXCEL: content_calendar (table grid), performance_audit (data tables)
  - MARKDOWN: ad_copy, video_scripts, briefs (deliverable for downstream tools)

HTML always generated as fallback. Excel/Markdown generated when primary_deliverable matches.
"""
import io
import re
import logging
from datetime import datetime
from typing import Optional

from agents.skills import OutputFormat, PrimaryDeliverable

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Parsers — handle 3 output format variants
# ─────────────────────────────────────────────────────────────────

def parse_strategic_output(text: str) -> dict:
    """Parse STRATEGIC_4_SECTION output into {insight, summary, benchmarks, detail}."""
    from bot.html_report import parse_agent_output
    return parse_agent_output(text)


def parse_operational_deliverable(text: str) -> dict:
    """Parse OPERATIONAL_DELIVERABLE output into {summary, deliverable}."""
    result = {"summary": "", "deliverable": ""}

    # Match "## 🎯 Tóm tắt nhanh" section
    summary_match = re.search(
        r"##\s*🎯[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        text, flags=re.DOTALL
    )
    if summary_match:
        result["summary"] = summary_match.group(1).strip()

    # Match "## 📄 Deliverable" section
    deliverable_match = re.search(
        r"##\s*📄[^\n]*\n+(.*?)(?=\Z)",
        text, flags=re.DOTALL
    )
    if deliverable_match:
        result["deliverable"] = deliverable_match.group(1).strip()

    # Fallback: nếu parse fail, dùng cả text làm deliverable
    if not result["summary"] and not result["deliverable"]:
        result["deliverable"] = text.strip()

    return result


def parse_operational_analysis(text: str) -> dict:
    """Parse OPERATIONAL_ANALYSIS output into {summary, kpi_table, root_cause, actions, forecast}."""
    result = {"summary": "", "kpi_table": "", "root_cause": "", "actions": "", "forecast": "", "raw": text}

    patterns = {
        "summary":    r"##\s*📊\s*Tóm tắt[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "kpi_table":  r"##\s*📈[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "root_cause": r"##\s*🔬[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "actions":    r"##\s*🎯[^\n]*\n+(.*?)(?=\n##\s|\Z)",
        "forecast":   r"##\s*📉[^\n]*\n+(.*?)(?=\Z)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.DOTALL)
        if m:
            result[key] = m.group(1).strip()

    if not any(v for k, v in result.items() if k != "raw"):
        result["summary"] = text.strip()[:2000]

    return result


def parse_by_format(text: str, output_format: OutputFormat) -> dict:
    """Dispatch parser based on output format."""
    if output_format == OutputFormat.STRATEGIC_4_SECTION:
        return parse_strategic_output(text)
    elif output_format == OutputFormat.OPERATIONAL_DELIVERABLE:
        return parse_operational_deliverable(text)
    elif output_format == OutputFormat.OPERATIONAL_ANALYSIS:
        return parse_operational_analysis(text)
    return {"raw": text}


# ─────────────────────────────────────────────────────────────────
# Telegram card formatters
# ─────────────────────────────────────────────────────────────────

def format_telegram_card(
    skill_name: str,
    skill_label: str,
    skill_emoji: str,
    parsed: dict,
    output_format: OutputFormat,
    file_attached_hint: Optional[str] = None,
) -> str:
    """Build Telegram preview card. Long content always goes to HTML/file."""
    header = f"*{skill_emoji} {skill_label.upper()}*"
    separator = "━" * 25
    parts = [header, separator, ""]

    if output_format == OutputFormat.STRATEGIC_4_SECTION:
        if parsed.get("insight"):
            insight = parsed["insight"].strip().strip('"').strip("'")
            parts.append("💡 *Insight quan trọng nhất:*")
            parts.append(f"_{insight}_")
            parts.append("")
        if parsed.get("summary"):
            parts.append("📌 *Tóm tắt:*")
            parts.append(parsed["summary"].strip())
            parts.append("")
        if parsed.get("benchmarks"):
            parts.append("📊 *Benchmarks:*")
            parts.append(parsed["benchmarks"].strip())
            parts.append("")

    elif output_format == OutputFormat.OPERATIONAL_DELIVERABLE:
        if parsed.get("summary"):
            parts.append("🎯 *Tóm tắt nhanh:*")
            parts.append(parsed["summary"].strip())
            parts.append("")

    elif output_format == OutputFormat.OPERATIONAL_ANALYSIS:
        if parsed.get("summary"):
            parts.append("📊 *Tổng quan:*")
            parts.append(parsed["summary"].strip())
            parts.append("")

    # Hint about attached file
    if file_attached_hint:
        parts.append(f"📎 _{file_attached_hint}_")
    else:
        parts.append("📎 _Xem chi tiết trong file đính kèm bên dưới_")

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────
# Markdown deliverable file generator
# ─────────────────────────────────────────────────────────────────

def render_markdown_file(
    skill_name: str,
    skill_label: str,
    parsed: dict,
    output_format: OutputFormat,
    business_name: str = "",
) -> bytes:
    """Render skill output as a .md file for download (designer/dev/creator workflow)."""
    lines = [
        f"# {skill_label} — {business_name or 'Marketing OS'}",
        f"*Generated by Max — AI CMO · {datetime.now().strftime('%d/%m/%Y · %H:%M')}*",
        "",
        "---",
        "",
    ]

    if output_format == OutputFormat.OPERATIONAL_DELIVERABLE:
        if parsed.get("summary"):
            lines += ["## 🎯 Tóm tắt nhanh", "", parsed["summary"].strip(), "", "---", ""]
        if parsed.get("deliverable"):
            lines += [parsed["deliverable"].strip()]
    elif output_format == OutputFormat.STRATEGIC_4_SECTION:
        if parsed.get("insight"):
            lines += [f"> 💡 **Insight:** {parsed['insight'].strip().strip(chr(34)).strip(chr(39))}", ""]
        if parsed.get("summary"):
            lines += ["## 🎯 Tóm tắt", "", parsed["summary"].strip(), ""]
        if parsed.get("benchmarks"):
            lines += ["## 📊 Benchmarks", "", parsed["benchmarks"].strip(), ""]
        if parsed.get("detail"):
            lines += ["## 📄 Phân tích chi tiết", "", parsed["detail"].strip(), ""]
    elif output_format == OutputFormat.OPERATIONAL_ANALYSIS:
        # Dump all sections
        for key in ["summary", "kpi_table", "root_cause", "actions", "forecast"]:
            if parsed.get(key):
                lines += [f"## {key.replace('_', ' ').title()}", "", parsed[key].strip(), "", "---", ""]
    else:
        lines += [parsed.get("raw", "")]

    return "\n".join(lines).encode("utf-8")


# ─────────────────────────────────────────────────────────────────
# Excel renderer — for content_calendar + performance_audit
# ─────────────────────────────────────────────────────────────────

def render_excel_file(
    skill_name: str,
    skill_label: str,
    parsed: dict,
    output_format: OutputFormat,
    business_name: str = "",
) -> Optional[bytes]:
    """Render skill output as .xlsx with markdown tables extracted into sheets.
    Requires openpyxl. Returns None if no tables found or library missing."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        logger.warning("openpyxl not installed — falling back to no Excel export")
        return None

    # Combine all parsed sections for table extraction
    if output_format == OutputFormat.OPERATIONAL_DELIVERABLE:
        full_text = parsed.get("deliverable", "") + "\n\n" + parsed.get("summary", "")
    elif output_format == OutputFormat.OPERATIONAL_ANALYSIS:
        full_text = "\n\n".join(
            parsed.get(k, "") for k in ["summary", "kpi_table", "root_cause", "actions", "forecast"]
        )
    else:
        full_text = parsed.get("detail", "") + "\n\n" + parsed.get("raw", "")

    tables = _extract_markdown_tables(full_text)
    if not tables:
        return None

    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    for idx, (table_title, headers, rows) in enumerate(tables[:10]):  # max 10 sheets
        # Excel sheet name: max 31 chars, cấm các ký tự : \ / ? * [ ]
        raw_name = table_title or f"Sheet {idx+1}"
        sheet_name = re.sub(r"[:\\/?*\[\]]", " ", raw_name)[:30].strip() or f"Sheet {idx+1}"
        ws = wb.create_sheet(title=sheet_name)

        # Title row
        if table_title:
            ws.append([table_title])
            ws["A1"].font = Font(bold=True, size=14)
            ws.append([])  # blank row

        # Headers
        header_row = len(list(ws.rows)) + 1 if list(ws.rows) else 1
        ws.append(headers)
        for col_idx, _ in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align

        # Data rows
        for row in rows:
            ws.append(row)

        # Auto column width
        for col_idx, _ in enumerate(headers, start=1):
            col_letter = ws.cell(row=1, column=col_idx).column_letter
            max_len = max(len(str(headers[col_idx-1] or "")), *[len(str(r[col_idx-1] or "")) for r in rows if col_idx-1 < len(r)])
            ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _extract_markdown_tables(text: str) -> list[tuple[str, list[str], list[list[str]]]]:
    """Extract markdown tables from text. Returns list of (title, headers, rows).
    Title is the nearest preceding heading (###/####)."""
    tables = []
    lines = text.split("\n")

    # State: 'looking_for_table' | 'in_header' | 'in_body'
    current_title = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Track title (last seen heading)
        h_match = re.match(r"^#{1,5}\s+(.+)$", line)
        if h_match:
            current_title = h_match.group(1).strip()

        # Detect table header row: | col | col |
        if re.match(r"^\|.+\|$", line) and i + 1 < len(lines):
            sep_line = lines[i + 1].strip()
            # Separator row: |---|---|
            if re.match(r"^\|[\s:|-]+\|$", sep_line):
                headers = [c.strip() for c in line.strip("|").split("|")]
                rows = []
                j = i + 2
                while j < len(lines) and re.match(r"^\|.+\|$", lines[j].strip()):
                    row_cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    # Pad to match header length
                    while len(row_cells) < len(headers):
                        row_cells.append("")
                    rows.append(row_cells[:len(headers)])
                    j += 1
                if rows:
                    tables.append((current_title, headers, rows))
                i = j
                continue
        i += 1

    return tables
