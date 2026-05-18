# Bug Analysis: Brand Detection Feature
**Branch**: `feature/web-search` (Commit: `d961012`)  
**Date**: 2025-05-18

---

## 🎯 Summary

Brand detection logic **ĐÃ ĐƯỢC IMPLEMENT** trên branch `feature/web-search`, nhưng có **5 issues** cần fix trước merge:

| Issue | Severity | Impact | Fix Time |
|-------|----------|--------|----------|
| No timeout on Tavily search | HIGH | Bot hangs 5-30s+ | 1h |
| Race condition on brand selection | HIGH | Session corruption | 2h |
| Missing error handling | HIGH | Crashes on API fail | 1h |
| Brand name matching too aggressive | MEDIUM | False positives | 1h |
| No error recovery flow | MEDIUM | User confusion | 1h |

---

## 🔴 Issue #1: No timeout on Tavily search (HIGH)

**Location**: `tools/search.py`, line 22-42

**Problem**:
```python
response = await client.search(
    query=query,
    max_results=max_results,
    search_depth="basic",
)  # ❌ NO TIMEOUT — can hang forever
```

**Impact**: 
- User sends brand name → Tavily slow → bot hangs
- Railway timeout (30s) → process killed → session lost

**Fix** (add timeout wrapper):
```python
import asyncio

async def web_search(query: str, max_results: int = 5) -> str:
    try:
        client = get_client()
        response = await asyncio.wait_for(
            client.search(query=query, max_results=max_results, search_depth="basic"),
            timeout=15  # 15s max
        )
        # ... parse results
    except asyncio.TimeoutError:
        return f"⏳ Tìm kiếm lâu quá. Bạn mô tả thêm được không?"
    except Exception as e:
        logger.error(f"Tavily error: {e}")
        return f"Lỗi tìm kiếm: {str(e)[:100]}"
```

---

## 🔴 Issue #2: Race condition on brand selection (HIGH)

**Location**: `bot/handlers.py` callback handler

**Problem**:
1. User clicks "Brand A" button → callback queued
2. User sends message simultaneously → message handler queued
3. Both handlers try to update `session.brand_candidates`
4. State becomes inconsistent

**Impact**: 
- Double intake triggered
- Session corruption
- Bot asks same questions twice

**Fix**: Add state machine
```python
class BrandSearchState(Enum):
    NONE = "none"
    SEARCHING = "searching"
    RESULTS_SHOWN = "results_shown"
    SELECTED = "selected"

# In callback handler
if data.startswith("brand_select_"):
    if session.brand_search_state != BrandSearchState.RESULTS_SHOWN:
        await query.answer("⏳ Already selected", show_alert=True)
        return
    
    session.brand_search_state = BrandSearchState.SELECTED
    await save_session(session)
    # ... process selection
```

---

## 🔴 Issue #3: Missing error handling (HIGH)

**Location**: `bot/handlers.py`, `_handle_brand_search()` line 202-250

**Problem**:
```python
candidates = await search_brand_candidates(brand_name)
# ❌ No try-catch — if Tavily fails, bot crashes
```

**Impact**: 
- Any Tavily error → UnhandledException
- Message sent ("🔍 Searching...") stays stuck
- User confused

**Fix**:
```python
async def _handle_brand_search(update, context, session, brand_name: str):
    await update.message.reply_text(f"🔍 Searching *{brand_name}*...", parse_mode=ParseMode.MARKDOWN)
    
    try:
        candidates = await asyncio.wait_for(
            search_brand_candidates(brand_name),
            timeout=20
        )
    except asyncio.TimeoutError:
        await update.message.reply_text("⏳ Tìm kiếm lâu. Hãy mô tả thêm!")
        # Fallback to normal intake
        session.add_to_history("user", brand_name)
        session.add_to_history("assistant", "Bạn mô tả chi tiết được không?")
        await save_session(session)
        return
    except Exception as e:
        logger.error(f"Brand search error: {e}")
        await update.message.reply_text("❌ Lỗi tìm kiếm. Bạn mô tả thêm được không?")
        # Fallback to normal intake...
        return
    
    # If no candidates found
    if not candidates:
        # Fallback to normal intake
```

---

## 🟡 Issue #4: Brand matching too aggressive (MEDIUM)

**Location**: `bot/handlers.py`, `_is_likely_brand_name()` line 186-200

**Problem**:
```python
# Current logic
if not (1 <= len(words) <= 4) or len(text) > 45:
    return False
# This matches ANY 1-4 word sentence without descriptive words
```

**False Positives**:
- "Luna" → brand search triggered (but user meant "luxury brand")
- "Spa" → brand search triggered
- "Tech startup" → brand search triggered

**Fix** (stricter matching):
```python
def _is_likely_brand_name(text: str, session) -> bool:
    if len(session.intake_history) > 0:
        return False
    
    words = text.strip().split()
    if not (1 <= len(words) <= 3) or len(text) > 30:  # Tighter
        return False
    
    # Must NOT contain: numbers, emojis, special chars
    if not all(c.isalnum() or c in " -'" for c in text.lower()):
        return False
    
    # Check against descriptive words
    descriptive = {
        "tôi", "bạn", "mình", "đang", "là",
        "bán", "dịch", "vụ", "sản", "phẩm",
        "app", "web", "shop", "muốn", "cần"
    }
    if any(w.lower() in descriptive for w in words):
        return False
    
    return True
```

---

## 🟡 Issue #5: No error recovery (MEDIUM)

**Location**: Multiple places — brand search flow

**Problem**: 
When brand search fails, bot sends error but doesn't guide next step. User confused.

**Fix**: Always fallback to normal intake with helpful message
```python
# After ANY error:
session.brand_candidates = []
session.add_to_history("user", brand_name)
session.add_to_history("assistant", 
    f"Tôi không tìm được info về {brand_name}.\n\n"
    f"Không sao, bạn hãy mô tả:\n"
    f"• Sản phẩm/dịch vụ là gì?\n"
    f"• Khách hàng mục tiêu là ai?\n"
    f"• Đã hoạt động bao lâu?\n\n"
    f"Tôi sẽ giúp phân tích dựa trên đó."
)
await save_session(session)
```

---

## ✅ Merge Checklist

Before merging `feature/web-search` → `master`:

- [ ] Add timeout to `search_brand_candidates()` + `web_search()`
- [ ] Add `BrandSearchState` enum to prevent race conditions
- [ ] Add try-catch in `_handle_brand_search()` + error recovery
- [ ] Improve `_is_likely_brand_name()` matching logic
- [ ] Test 10 brand names (Nike, Starbucks, local brands)
- [ ] Test 10 descriptions (should NOT trigger brand search)
- [ ] Verify Tavily quota (1000 req/month free tier)
- [ ] Check for timeouts in logs during testing
- [ ] Code review by 2+ people
- [ ] Deploy to staging first

---

## 🧪 Testing Plan

### Manual Tests (2h)
```
Test 1: Nike
- User sends "Nike" → Should trigger brand search
- Wait 15s → Results shown with 1-4 options
- Click "✅ Correct" → Continue to confirmation

Test 2: Starbucks Coffee
- User sends "Starbucks Coffee" → Should trigger brand search
- Results shown → Click option
- Verify profile extracted correctly

Test 3: "I run a coffee shop"
- User sends full description → Should NOT trigger brand search
- Should go straight to normal intake
- Bot asks follow-up questions

Test 4: Timeout Test
- Mock Tavily to delay 20s → Should timeout gracefully
- Bot shows "⏳ Search taking too long..."
- Fallback to normal intake

Test 5: Error Recovery
- Mock Tavily to error → Bot shows error + guidance
- Fallback to normal intake with helpful message
```

### Automated Tests (1h)
```python
# tests/test_brand_detection.py
import pytest
from bot.handlers import _is_likely_brand_name
from storage.models import Session

def test_brand_detection():
    # Should detect
    assert _is_likely_brand_name("Nike", Session(user_id=1))
    assert _is_likely_brand_name("Starbucks", Session(user_id=1))
    assert _is_likely_brand_name("Luna Spa", Session(user_id=1))
    
    # Should NOT detect
    assert not _is_likely_brand_name("I run a spa", Session(user_id=1))
    assert not _is_likely_brand_name("tôi bán hàng", Session(user_id=1))
    assert not _is_likely_brand_name("app quản lý", Session(user_id=1))
```

---

## 📈 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Race condition | Medium | High | Add state machine |
| Timeout hang | High | High | Add timeouts |
| False positives | Medium | Medium | Improve matching |
| Tavily quota exceeded | Low | High | Monitor quota |
| Silent failures | High | High | Add error handling |

**Overall Risk**: **MEDIUM** — Logic sound, but needs hardening before production

---

## 🚀 Timeline

- **Day 1 (5/19)**: Fix all 5 issues (4-5h)
- **Day 2 (5/20)**: Test thoroughly (2-3h)
- **Day 3 (5/21)**: Code review + staging deploy
- **Day 4 (5/22)**: Production deploy if all green

**Target**: Ready to merge by 5/23

