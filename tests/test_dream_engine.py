"""
Smoke test cho Dream Engine — KHÔNG cần API key / DB thật.

Phủ:
1. _parse_dreams_json — parse robust (plain JSON, có ```json fence, lẫn text).
2. make_signature — chuẩn hoá tiếng Việt để dedupe.
3. generate_dreams — dedupe theo recent_signatures (mock llm_router + storage).
4. build_digest_text / build_digest_keyboard — format đúng.

Chạy:
    python -m tests.test_dream_engine
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import patch

from agents.dreamer import _parse_dreams_json, generate_dreams
from storage.dreams import make_signature
from workers.dream_engine import build_digest_text, build_digest_keyboard


def test_parse_plain_json():
    raw = '{"dreams": [{"title": "A", "angle": "x", "impact": "high"}]}'
    out = _parse_dreams_json(raw)
    assert len(out) == 1
    assert out[0]["title"] == "A"
    assert out[0]["impact"] == "high"
    print("✅ test_parse_plain_json")


def test_parse_fenced_and_noisy():
    raw = (
        "Đây là ý tưởng của em:\n```json\n"
        '{"dreams": [{"title": "B", "angle": "y"}, {"title": "C"}]}'
        "\n```\nMong sếp thích!"
    )
    out = _parse_dreams_json(raw)
    assert [d["title"] for d in out] == ["B", "C"]
    # default impact/inspired_by được điền
    assert out[1]["impact"] == "medium"
    assert out[1]["inspired_by"] == "mix"
    print("✅ test_parse_fenced_and_noisy")


def test_parse_garbage_returns_empty():
    assert _parse_dreams_json("không phải json") == []
    assert _parse_dreams_json("") == []
    assert _parse_dreams_json('{"dreams": "not a list"}') == []
    print("✅ test_parse_garbage_returns_empty")


def test_make_signature_vietnamese():
    assert make_signature("Chiến dịch Tết Đỏ!") == "chien dich tet do"
    # Cùng ý tưởng khác dấu câu/hoa thường → cùng signature
    assert make_signature("CHIẾN DỊCH TẾT ĐỎ") == make_signature("chiến dịch tết đỏ")
    print("✅ test_make_signature_vietnamese")


def test_generate_dreams_dedupes():
    """generate_dreams loại ý tưởng trùng signature đã mơ trước đó."""
    fake_output = {
        "output": (
            '{"dreams": ['
            '{"title": "Chiến dịch Tết Đỏ", "angle": "a"},'
            '{"title": "Flash sale cuối tuần", "angle": "b"},'
            '{"title": "Flash Sale Cuối Tuần", "angle": "dup"}'  # trùng #2 sau chuẩn hoá
            ']}'
        )
    }

    async def fake_call(**kwargs):
        return fake_output

    async def fake_recent(user_id, limit=40):
        # "chien dich tet do" đã mơ rồi → phải bị loại
        return ["chien dich tet do"]

    async def run():
        with patch("agents.dreamer.call", fake_call), \
             patch("agents.dreamer.recent_signatures", fake_recent):
            return await generate_dreams(123, "memory block")

    out = asyncio.run(run())
    titles = [d["title"] for d in out]
    # Loại "Chiến dịch Tết Đỏ" (trùng history) + "Flash Sale Cuối Tuần" (trùng trong batch)
    assert titles == ["Flash sale cuối tuần"], titles
    print("✅ test_generate_dreams_dedupes")


def test_digest_format():
    rows = [
        {"id": "id1", "title": "Idea 1", "angle": "góc 1",
         "why_now": "vì đối thủ", "first_step": "làm X", "impact": "high"},
        {"id": "id2", "title": "Idea 2", "angle": "góc 2",
         "why_now": "vì mùa lễ", "first_step": "làm Y", "impact": "medium"},
    ]
    text = build_digest_text(rows)
    assert "2 ý tưởng" in text
    assert "Idea 1" in text and "Idea 2" in text
    assert "🔥" in text and "💡" in text  # high vs medium emoji

    kb = build_digest_keyboard(rows)
    # 2 dream → 2 hàng, mỗi hàng 2 nút (Phát triển + Bỏ qua)
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].callback_data == "dreamdev_id1"
    assert kb.inline_keyboard[0][1].callback_data == "dreamx_id1"
    print("✅ test_digest_format")


def main():
    tests = [
        test_parse_plain_json,
        test_parse_fenced_and_noisy,
        test_parse_garbage_returns_empty,
        test_make_signature_vietnamese,
        test_generate_dreams_dedupes,
        test_digest_format,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"❌ {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"💥 {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{'ALL PASS ✅' if failed == 0 else f'{failed} FAILED ❌'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
