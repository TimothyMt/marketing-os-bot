from .session import get_session, save_session, reset_session, init_pool, init_db
from .models import Session, BusinessProfile, PipelineStage, BrandVoice
from .brand_voice import (
    get_brand_voice,
    save_brand_voice,
    has_brand_voice,
    deactivate_brand_voice,
)
from .campaign_history import (
    save_campaign_history,
    search_similar_campaigns,
    list_campaigns,
    get_latest_campaign,
    get_history_user_ids,
)
from .dreams import (
    save_dreams,
    list_dreams,
    get_dream,
    update_status as update_dream_status,
    recent_signatures,
    mark_surfaced,
)
from .embeddings import embed_text
