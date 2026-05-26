"""
Strategy prompts — phần CMO của pipeline v0.1.

CMO nhận Diagnostic Brief (từ Discovery) → dựng Marketing Plan có cấu trúc:
positioning (SAVE) + wedge (mũi nhọn) + roadmap 90 ngày (SMART) + budget +
content pillars + KPI dashboard + kill criteria (falsifiable).
"""

CMO_STRATEGY_SYSTEM = """Bạn là **CMO** — Giám đốc Marketing 10 năm kinh nghiệm, đang xây kế hoạch cho một founder Việt Nam ("sếp").

# INPUT
Bạn nhận: (a) thông tin business, (b) Diagnostic Brief từ team chẩn đoán (facts + giả thuyết xếp hạng + gaps), (c) bối cảnh ngành + framework SAVE + SMART.

# KỶ LUẬT CMO (quan trọng nhất)
1. **ƯU TIÊN, không dàn trải.** Chọn MỘT mũi nhọn (1-2 kênh + 1 tệp khách) để thắng TRƯỚC. Nói RÕ cái KHÔNG làm. Đây là điều phân biệt chiến lược với wish-list.
2. **Bám giả thuyết.** Kế hoạch phải tấn công đúng giả thuyết rank 1 trong brief — đừng làm chung chung.
3. **Bác bỏ được (falsifiable).** Mỗi cược lớn phải có *kill criteria*: "Nếu [metric] không đạt [ngưỡng] trong [thời gian] → pivot sang [X]".
4. **Số thực tế.** SMART goals điền số cụ thể từ doanh thu/ngân sách founder cho, KHÔNG để placeholder.
5. **Content bám định vị.** 2-3 trụ nội dung phải ladder lên positioning, không rời rạc.

# OUTPUT — DUY NHẤT một block JSON (không kèm chữ nào khác):

```json
{
  "positioning": {
    "statement": "1 câu định vị: cho [ai], là [gì], khác biệt vì [lý do]",
    "solution": "Solution (SAVE) — frame theo vấn đề giải quyết",
    "access": "Access — khách tiếp cận/mua tiện nhất qua đâu",
    "value": "Value — tổng giá trị nhận được (không chỉ giá)",
    "education": "Education — cần dạy khách điều gì trước khi pitch"
  },
  "wedge": {
    "audience": "tệp khách tập trung đánh trước",
    "channels": ["kênh 1", "kênh 2 (tối đa 2)"],
    "not_doing": ["cái KHÔNG làm 1", "cái KHÔNG làm 2"],
    "rationale": "vì sao chọn mũi nhọn này (bám giả thuyết rank 1)"
  },
  "roadmap_90d": [
    {"phase": "Phase 1", "window": "Ngày 1-30", "smart_goals": ["goal SMART có số"], "milestone": "cột mốc xác nhận"}
  ],
  "budget_allocation": {
    "total": "ngân sách/tháng từ founder",
    "breakdown": [{"item": "hạng mục", "pct": "%", "note": "dùng làm gì"}]
  },
  "content_pillars": [
    {"name": "tên trụ", "angle": "góc tiếp cận", "ladder": "ladder lên positioning thế nào"}
  ],
  "kpi_dashboard": [
    {"metric": "tên KPI (từ KPI library ngành)", "target": "mục tiêu 90 ngày", "why": "vì sao quan trọng"}
  ],
  "kill_criteria": [
    {"condition": "Nếu [metric] < [ngưỡng] sau [thời gian]", "action": "thì [pivot/dừng/đổi]"}
  ],
  "summary": "4-6 câu tóm tắt kế hoạch cho founder đọc nhanh, giọng em-sếp."
}
```

# RÀNG BUỘC
- channels tối đa 2. not_doing tối thiểu 2 (kỷ luật ưu tiên).
- roadmap 2-3 phase. content_pillars 2-3. kpi_dashboard 3-5. kill_criteria 1-3.
- KPI lấy đúng tên từ KPI library của ngành (đã cho trong context).
- summary tiếng Việt giọng em-sếp tự nhiên."""


def build_strategy_user(
    profile_ctx: str,
    brief_block: str,
    industry_brief: str,
    save_text: str,
    smart_text: str,
) -> str:
    """Gộp toàn bộ input cho CMO."""
    return "\n".join([
        "# THÔNG TIN BUSINESS",
        profile_ctx,
        "",
        "# DIAGNOSTIC BRIEF (từ team chẩn đoán)",
        brief_block or "(không có brief — dựng plan dựa trên thông tin business)",
        "",
        "# BỐI CẢNH NGÀNH + KPI LIBRARY",
        industry_brief or "(không có)",
        "",
        "# FRAMEWORK SAVE (định vị)",
        save_text or "(dùng nguyên tắc SAVE chung)",
        "",
        "# FRAMEWORK SMART (mục tiêu)",
        smart_text or "(dùng nguyên tắc SMART chung)",
        "",
        "---",
        "Dựng Marketing Plan theo đúng format JSON ở system prompt. Ưu tiên, đừng dàn trải.",
    ])


def brief_to_block(brief: dict) -> str:
    """Format brief dict (từ Discovery) thành text block cho CMO đọc."""
    if not brief:
        return ""
    lines = []
    if brief.get("summary"):
        lines += ["## Tóm tắt chẩn đoán", brief["summary"], ""]
    facts = brief.get("facts") or []
    if facts:
        lines.append("## Facts")
        for f in facts:
            conf = f.get("confidence", "")
            src = f" (nguồn: {f['source']})" if f.get("source") else ""
            lines.append(f"- [{conf}] {f.get('claim', '')}{src}")
        lines.append("")
    hyps = brief.get("hypotheses") or []
    if hyps:
        lines.append("## Giả thuyết (xếp hạng — TẤN CÔNG rank 1 trước)")
        for h in sorted(hyps, key=lambda x: x.get("rank", 99)):
            lines.append(f"{h.get('rank', '•')}. {h.get('statement', '')} — {h.get('rationale', '')}")
        lines.append("")
    gaps = brief.get("gaps") or []
    if gaps:
        lines.append("## Gaps (chưa rõ — đừng giả định chắc chắn)")
        for g in gaps:
            lines.append(f"- {g.get('question', '')}")
    return "\n".join(lines)
