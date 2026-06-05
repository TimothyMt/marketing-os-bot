"""
Regression tests cho việc chỉnh menu persona:
- Bỏ Mai khỏi main menu, bỏ performance_audit khỏi Khoa
- Nam mode "viết bài mới" → post_write với 4 field (topic/channel/post_goal/tone_angle), KHÔNG có TikTok
- Khoa skills có field channel_focus (prefill từ nút chooser)
- Các keyboard mới tồn tại + callback_data đúng

Chạy offline, không gọi API.
"""
from bot import keyboards as kb
from agents.task_registry import get_task
from agents.manager_personas import get_persona


def _all_callbacks(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


# ── Main menu ─────────────────────────────────────────────────────
def test_main_menu_no_mai():
    cbs = _all_callbacks(kb.MAIN_MENU_KEYBOARD)
    assert "persona_menu_crm" not in cbs, "Mai (CRM) vẫn còn trong main menu"
    # Các persona còn lại vẫn có
    for expected in ("persona_menu_cmo", "persona_menu_brand",
                     "persona_menu_content", "persona_menu_tiktok",
                     "persona_menu_growth"):
        assert expected in cbs, f"Thiếu {expected} trong main menu"


# ── Khoa (growth) ─────────────────────────────────────────────────
def test_growth_drops_performance_audit():
    skills = get_persona("growth").owns_skills
    assert "performance_audit" not in skills
    assert skills == ["retention_strategy", "winback_campaign"]


def test_growth_skills_have_channel_focus():
    for name in ("retention_strategy", "winback_campaign"):
        keys = [f["key"] for f in get_task(name).intake_fields]
        assert "channel_focus" in keys, f"{name} thiếu channel_focus"


def test_growth_channel_keyboard():
    cbs = _all_callbacks(kb.GROWTH_CHANNEL_KEYBOARD)
    assert set(cbs) == {"growth_ch_all", "growth_ch_zalo",
                        "growth_ch_email", "growth_ch_sms"}


# ── Nam (content) ─────────────────────────────────────────────────
def test_post_write_fresh_fields_no_tiktok():
    pw = get_task("post_write")
    keys = [f["key"] for f in pw.intake_fields]
    assert keys == ["topic", "channel", "post_goal", "tone_angle"]
    # Channel example không được gợi ý TikTok (đó là domain của Trang)
    channel_field = next(f for f in pw.intake_fields if f["key"] == "channel")
    assert "TikTok" not in channel_field["example"]
    assert "tone_angle" == pw.intake_fields[-1]["key"]
    assert pw.intake_fields[-1]["required"] is False  # tone optional


def test_nam_mode_keyboard():
    cbs = _all_callbacks(kb.NAM_MODE_KEYBOARD)
    assert "nam_mode_calendar" in cbs
    assert "nam_mode_fresh" in cbs


# ── Trang (tiktok) ────────────────────────────────────────────────
def test_trang_mode_keyboard():
    cbs = _all_callbacks(kb.TRANG_MODE_KEYBOARD)
    assert "trang_mode_calendar" in cbs
    assert "trang_mode_fresh" in cbs


# ── Linh (brand voice) ────────────────────────────────────────────
def test_linh_keyboards():
    exists = _all_callbacks(kb.LINH_BV_EXISTS_KEYBOARD)
    assert "bv_edit_chat" in exists
    assert "bv_view" in exists
    new = _all_callbacks(kb.LINH_BV_NEW_KEYBOARD)
    assert "bv_create" in new
