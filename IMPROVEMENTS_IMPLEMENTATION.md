# Improvement Implementation — Code Examples
**Timeline**: Priority 1 (this week) + Priority 2 (next week)

---

## 🎯 Priority 1: Critical Fixes (This Week)

### Fix #1: Add timeout decorator (1.5h)

**File**: `agents/pipeline.py`

```python
import asyncio
from functools import wraps

def timeout_wrapper(timeout_secs):
    """Decorator to add timeout to async functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_secs
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {timeout_secs}s")
                raise TimeoutError(f"Operation timed out after {timeout_secs}s")
        return wrapper
    return decorator

# Apply to agent calls
@timeout_wrapper(AGENT_TIMEOUT)
async def _run_agent(system_prompt: str, user_message: str, context: str, max_tokens: int = 2048) -> str:
    response = await client.messages.create(...)
    return response.content[0].text

@timeout_wrapper(120)
async def run_intake(session: Session, user_message: str) -> tuple[str, bool]:
    # ... existing code
```

---

### Fix #2: Error handling in intake (1.5h)

**File**: `bot/handlers.py`

```python
async def _handle_intake(update, context, session, text):
    """Handle intake with error recovery."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    try:
        response, is_complete = await run_intake(session, text)
        await save_session(session)
    except asyncio.TimeoutError:
        logger.error(f"Intake timeout for user {update.effective_user.id}")
        await update.message.reply_text(
            "⏳ Tôi mất kết nối tạm thời. Bạn gõ lại được không?"
        )
        return
    except Exception as e:
        logger.error(f"Intake error: {type(e).__name__}: {e}")
        await update.message.reply_text(
            "❌ Lỗi kỹ thuật. Bạn thử `/reset` để bắt đầu lại nhé.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if is_complete:
        # ... existing confirmation logic
```

---

### Fix #3: Enum validation (0.5h)

**File**: `bot/handlers.py`

```python
if data.startswith("task_"):
    task_type = data[5:]
    
    # Validate against TaskType enum
    valid_tasks = {t.value for t in TaskType}
    if task_type not in valid_tasks:
        logger.warning(f"Invalid task_type: {task_type} from user {user_id}")
        await query.answer("❌ Invalid task selected", show_alert=True)
        return
    
    session.selected_task = task_type
    session.stage = PipelineStage.INTAKE
    await save_session(session)
```

---

### Fix #4: Add input validation (1h)

**File**: `bot/handlers.py`

```python
def validate_user_input(text: str, max_len: int = 2000) -> tuple[str, bool]:
    """Validate + sanitize user input."""
    if not text or not isinstance(text, str):
        return "", False
    
    text = text.strip()
    
    # Check length
    if len(text) == 0 or len(text) > max_len:
        return "", False
    
    # Check for spam (only 1-2 unique chars)
    if len(set(text)) < 3:
        return "", False
    
    # Limit consecutive newlines
    if "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    
    return text, True

# Use in handle_message
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text, is_valid = validate_user_input(update.message.text)
    
    if not is_valid:
        await update.message.reply_text(
            "❌ Tin nhắn không hợp lệ. Bạn thử lại được không?"
        )
        return
```

---

## 🔧 Priority 2: Features (Next Week)

### Feature #1: Structured logging (2h)

**File**: New file `logging_config.py`

```python
import json
import logging
import sys
from datetime import datetime

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_data)

def setup_logging():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    
    # Suppress verbose libraries
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# bot/main.py
from logging_config import setup_logging
async def main():
    setup_logging()
    # ... rest
```

---

### Feature #2: Session cleanup (2h)

**File**: New file `storage/cleanup.py`

```python
import asyncio
import logging
from datetime import datetime, timedelta
from storage import _client, TABLE

logger = logging.getLogger(__name__)

async def cleanup_old_sessions(days_old: int = 30):
    """Delete sessions older than N days."""
    if not _client:
        logger.warning("Supabase client not initialized")
        return
    
    cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
    
    try:
        result = await _client.table(TABLE).delete().lt(
            "updated_at", cutoff_date
        ).execute()
        deleted_count = len(result.data) if result.data else 0
        logger.info(f"Cleanup: deleted {deleted_count} old sessions")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

async def schedule_cleanup():
    """Run cleanup daily at 2 AM UTC."""
    while True:
        now = datetime.utcnow()
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target < now:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await cleanup_old_sessions(days_old=30)

# bot/main.py
async def main():
    # ... existing startup
    asyncio.create_task(schedule_cleanup())  # Start cleanup task
```

---

### Feature #3: PDF export (4h)

**File**: New file `exporters/pdf_exporter.py`

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak
from reportlab.lib import colors
from datetime import datetime
from storage.models import Session

class MarketingReportExporter:
    def __init__(self, session: Session):
        self.session = session
        self.styles = getSampleStyleSheet()
    
    def generate(self, output_path: str):
        """Generate PDF report."""
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = []
        
        # Title
        story.append(Paragraph(
            f"🎯 Marketing Strategy Report",
            self.styles['Heading1']
        ))
        story.append(Paragraph(
            f"Business: <b>{self.session.profile.business_name}</b>",
            self.styles['BodyText']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
            self.styles['BodyText']
        ))
        story.append(Spacer(1, 0.3*inch))
        
        # Market Research
        if "market_research" in self.session.results:
            story.append(Paragraph("Market Research", self.styles['Heading2']))
            story.append(Paragraph(
                self.session.results["market_research"][:1000],
                self.styles['BodyText']
            ))
        
        # ... More sections
        
        doc.build(story)
        return output_path

# In bot/handlers.py
async def handle_export_pdf(update, context, session):
    try:
        from exporters.pdf_exporter import MarketingReportExporter
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            exporter = MarketingReportExporter(session)
            pdf_path = exporter.generate(tmp.name)
            
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename=f"{session.profile.business_name}.pdf"
                )
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        await update.message.reply_text("❌ Lỗi tạo PDF")
```

---

## 📋 Implementation Checklist

### Week 1 (5/19-5/23) — Priority 1
- [ ] Add timeouts to _run_agent() + run_intake() — **1.5h**
- [ ] Add error handling in _handle_intake() — **1.5h**
- [ ] Validate selected_task enum — **0.5h**
- [ ] Add input validation — **1h**
- [ ] Fix brand detection (feature/web-search) — **3h**
- [ ] Test all 7 task flows — **2h**
- **Total: ~9h**

### Week 2 (5/26-5/30) — Priority 2
- [ ] Structured JSON logging — **2h**
- [ ] Session cleanup job — **2h**
- [ ] PDF export feature — **4h**
- [ ] Rate limiting (optional) — **1h**
- **Total: ~9h**

---

## 🧪 Testing Checklist

### Unit Tests
```bash
# tests/test_validation.py
pytest tests/test_validation.py -v
```

### Integration Tests
```bash
# Test all task flows
python simulate.py
# Verify: intake 30-60s, pipeline 3-5min
```

### Staging Deployment
```bash
# Deploy to Railway staging
git checkout feature/web-search
# ... apply all fixes ...
git push origin feature/web-search
# Wait for Railway auto-deploy
# Monitor logs: check for timeouts, errors
```

---

## 📊 Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Intake latency | 30-60s | TBD | TBD |
| Pipeline latency | 3-5m | TBD | TBD |
| Error rate | < 1% | TBD | TBD |
| Timeout errors | 0 | TBD | TBD |
| Silent failures | 0 | TBD | TBD |

---

## 🚀 Go-Live Plan

**Friday 5/23**: Deploy to production
1. Merge `feature/web-search` (with all fixes) → `master`
2. Railway auto-deploys from master
3. Monitor logs for 24h
4. Check error metrics (target: < 1% error rate)
5. Verify Tavily quota usage (target: < 100 req/day)

**Rollback plan**: 
- If error rate > 2%, revert to previous master
- Railway → Deployments → Select previous commit → deploy

---

## 📞 Support

- **Questions on setup?** → IMPROVEMENTS_IMPLEMENTATION.md (this file)
- **Bug details?** → BUG_ANALYSIS_BRAND_DETECTION.md
- **Architecture review?** → AUDIT_REPORT_20250518.md

