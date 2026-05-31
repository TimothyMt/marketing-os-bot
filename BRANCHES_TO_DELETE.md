# Branch cần xoá thủ công (2026-05-31)

> ⚠️ Môi trường Claude Code on web KHÔNG xoá được branch remote
> (git push --delete bị chặn 403; GitHub MCP không có tool delete branch).
> Bạn cần xoá thủ công qua **GitHub web UI** (tab Branches → icon thùng rác)
> hoặc `git push origin --delete <branch>` từ máy bạn (có quyền).

Sau khi đã hợp nhất về `master` (= nice-gates + viral analyzer + kpi 14 ngành),
11 branch sau là thừa. SHA tip lưu lại để khôi phục nếu cần
(`git branch <ten> <SHA>`):

| Branch cần xoá | SHA tip | Lý do |
|---|---|---|
| claude/jolly-goodall-X8fnk | b4ccfc3e3bfd6ec1ae254d9072b15e85fc11d53f | subset nice-gates (deletion refactor) |
| claude/nice-bell-KugwP | 7efb94bf67452a5e9bcb479afe27bf1fe0c4b7b5 | subset nice-gates |
| coming-soon | 98af776b698aea4c43b455e5ffcf40a33117b326 | subset nice-gates |
| content-gen-suite | 681637546e8c4fa3ebce260eca97bfad01ada9d5 | subset nice-gates |
| feature/operational-layer | 6a78083ceb92cca675b5c43bb96a870bfe6c2127 | subset nice-gates |
| fix/critical-issues | d1a5ed6704b75899e03c9f594b38dd3ca24acd06 | era base, lỗi thời |
| fix/greeting-intercept | eb904b611e7e1c8b0dc807783cda70d0a6cbd9d0 | subset nice-gates |
| refactor/db-v2-normalize | d355ab8626cdefb47dbe1f08ac188aec7ed0cd30 | subset nice-gates |
| test-prompt-upgrades | 5922b13e8e9fa1c1c3c9cfc2bb918cdf0151cc2f | subset nice-gates (3 commit) |
| claude/nice-gates-KcHRC | 75cd9eae439036c6f8c7d6c38084348db06be551 | đã nằm trong master |
| claude/viral-video-analyzer-skill | b82fbe64a739d049e2c8a922d29d54a6462906b7 | đã merge vào master |

## Branch GIỮ LẠI
- `master` — default, = nội dung hợp nhất
- `integration/consolidated` — branch làm việc (= master)
- `claude/marketing-os-three-tier-RHBLx` — nguồn code three-tier (backup 1 phần ở `_pending_three_tier/`)

## Lệnh xoá nhanh (chạy từ máy có quyền)
```bash
for b in claude/jolly-goodall-X8fnk claude/nice-bell-KugwP coming-soon \
  content-gen-suite feature/operational-layer fix/critical-issues \
  fix/greeting-intercept refactor/db-v2-normalize test-prompt-upgrades \
  claude/nice-gates-KcHRC claude/viral-video-analyzer-skill; do
  git push origin --delete "$b"
done
```
