# Ads Scheduler & FB Posting — Hướng Dẫn Setup

Báo cáo ads tự động qua Telegram: digest 8:00 sáng (so hôm qua), weekly thứ Hai
(so 7 ngày trước), alert real-time mỗi 4 tiếng. Ngoài ra hỗ trợ đăng bài lên
Facebook Page qua `/post_fb`.

Mỗi user kết nối Facebook bằng **Manual Token** — tự tạo FB App của riêng mình
+ lấy Access Token qua Graph API Explorer, paste vào bot. Không cần OAuth, không
cần chờ App Review.

---

## Tổng quan kiến trúc

```
User /connect_ads → hướng dẫn tạo FB App + lấy token → user paste token
                                      │
                          fetch_token_info() validate
                          + lấy ad accounts + pages
                                      │
                  lưu encrypted (user token + page tokens) per-user
                                      │
        ┌─────────────────────────────┴──────────────────────────┐
        ▼                                                          ▼
  Scheduler (asyncio loop)                              /ads_settings · /post_fb
  ├─ 8:00   Daily digest (T2 = Weekly)                  /switch_account · /switch_page
  ├─ /4h    Alert monitor (Freq/ROAS/CPM)
  ├─ 2:00   Token validity check
  └─ CN 3:00 Cleanup snapshot >90 ngày
```

---

## Bước 1 — Chạy Database Migration

Mở **Supabase → SQL Editor**, paste lần lượt nội dung các file:

```
storage/migrations/010_fb_connections.sql
storage/migrations/011_fb_available_accounts.sql
storage/migrations/012_fb_manual_token.sql
```

Tạo/cập nhật các bảng:
- `user_fb_connections` — token (encrypted), ad account, pages (encrypted page tokens), settings per-user
- `ads_snapshots` — data ngày (giữ 90 ngày, để tính delta)
- `ads_alert_cooldowns` — chống spam alert (24h/alert)

**Verify:** chạy `SELECT * FROM user_fb_connections LIMIT 1;` — không lỗi là OK.

---

## Bước 2 — Tạo ENCRYPTION_KEY

Token FB **không lưu plain text**. Cần 1 Fernet key để mã hóa.

Tạo key (chạy local hoặc bất kỳ máy nào có Python):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Output dạng: `kJ8xR2..._q9zB4=` (44 ký tự, base64)

→ Set vào env var `ENCRYPTION_KEY` trên Railway.

> ⚠️ **Giữ key này cẩn thận.** Đổi key = mất toàn bộ token đã lưu (user phải `/connect_ads` lại).

---

## Bước 3 — User tự kết nối (không cần admin setup FB App)

Mỗi user gõ `/connect_ads` trong bot, bot hướng dẫn:

1. Tạo FB App của riêng họ tại https://developers.facebook.com/apps (type **Business**)
2. Vào **Graph API Explorer**, chọn app vừa tạo, chọn **User Token**
3. Tick permissions: `ads_read`, `ads_management`, `read_insights`,
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
4. **Generate Access Token** → copy chuỗi `EAA...`
5. Paste token vào chat với bot

Bot validate token qua `/me`, lấy danh sách Ad Account (`/me/adaccounts`) và
Page (`/me/accounts`, kèm Page Access Token riêng), lưu encrypted.

> Vì mỗi user là chủ app + admin Page của chính họ, **không cần App Review** —
> token hoạt động ngay với chính tài khoản FB của họ.

---

## Bước 4 — Deploy & Verify

### 4.1 Cài dependencies

`requirements.txt` đã có: `cryptography`, `uvicorn`, `starlette`, `httpx`.
Railway tự `pip install` khi deploy.

### 4.2 Checklist sau deploy

1. **Bot khởi động:** log thấy `PTB webhook registered` + `Background tasks started (... + ads scheduler)`
2. **Telegram webhook còn chạy:** gửi `/start` → bot phản hồi
3. **Connect flow:** gửi `/connect_ads` → làm theo hướng dẫn → paste token →
   bot xác nhận Ad Account + Page đã kết nối
4. **Settings:** `/ads_settings` → hiện keyboard chọn metric + toggle
5. **Posting:** `/post_fb` → gửi text hoặc ảnh kèm caption → bot đăng lên Page

### 4.3 Test scheduler nhanh (không đợi 8:00)

Tạm sửa giờ trong `services/ads_scheduler.py` `_tick()` để fire ngay (ví dụ
đổi `hour == 8` thành giờ hiện tại), deploy, chờ ≤30s, kiểm tra Telegram nhận
digest. **Nhớ revert** sau khi test.

---

## Các lệnh người dùng

| Lệnh | Chức năng |
|---|---|
| `/connect_ads` | Kết nối Facebook bằng Manual Token (Ad Account + Page) |
| `/switch_account` | Đổi Ad Account active (báo cáo/tối ưu ads) |
| `/switch_page` | Đổi Page active (đăng bài) |
| `/post_fb` | Đăng bài (text hoặc ảnh+caption) lên Page active |
| `/ads_settings` | Chọn chỉ số theo dõi + đặt ngưỡng alert + bật/tắt |
| `/disconnect_ads` | Ngắt kết nối, xóa toàn bộ token |

### Đặt ngưỡng alert (trong /ads_settings → "Đặt ngưỡng alert")

Gửi text format (bỏ trống dòng nào = Max tự dùng benchmark ngành):
```
frequency: 5.0
roas_drop: 20
cpm_spike: 30
```

---

## Chỉ số hỗ trợ

**FB trả thẳng:** spend, impressions, reach, clicks, ctr, cpc, cpm, frequency,
actions (leads/purchases), video views.

**Bot tự tính:** ROAS (= purchase_value/spend), CPL (= spend/leads),
VTR 3s (= video_3s/impressions), delta % so kỳ trước.

**Recommended (mặc định):** Spend · ROAS · CPL · Frequency

---

## Benchmark mặc định (khi user không set ngưỡng)

| Ngưỡng | Default | Ý nghĩa |
|---|---|---|
| Frequency max | 5.0 | > 5.0 = saturation → push alert |
| ROAS drop | 20% | giảm > 20% trong 24h → alert |
| CPM spike | 30% | tăng > 30% trong 24h → alert |

---

## Troubleshooting

| Triệu chứng | Nguyên nhân | Fix |
|---|---|---|
| `/connect_ads` báo "ENCRYPTION_KEY chưa set" | thiếu key | bước 2 |
| `/connect_ads` báo "Token không hợp lệ" | token sai/hết hạn/thiếu quyền | tạo lại token ở Graph API Explorer, đủ permissions |
| Sau connect không thấy Ad Account | token thiếu `ads_read`/`ads_management` | tạo lại token đủ quyền |
| Sau connect không thấy Page | token thiếu `pages_show_list` hoặc user không phải admin Page nào | thêm quyền/admin rồi connect lại |
| `/post_fb` báo lỗi đăng bài | token thiếu `pages_manage_posts` | tạo lại token đủ quyền, `/connect_ads` lại |
| Không nhận digest sáng | scheduler chưa chạy / token revoked | check log; user `/connect_ads` lại |
| Bot báo "Kết nối đã ngắt" | token hết hạn/revoke | user `/connect_ads` lại (settings giữ nguyên) |

---

## Token Lifecycle

User Access Token tạo qua Graph API Explorer thường hết hạn sau ~1-2h
(short-lived) trừ khi user tự extend trong app của họ. Vì token thuộc app
riêng của từng user, bot **không tự refresh được** (cần app secret của họ).

```
Scheduler 2:00 sáng → ping /me bằng token đã lưu
  còn dùng được → giữ nguyên
  hết hạn/revoke → tắt notify + nhắn user /connect_ads lại (lấy token mới)
```

Snapshot giữ **90 ngày**, tự xóa Chủ Nhật 3:00 sáng.
