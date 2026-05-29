# 前端文档入口

本目录保存前端设计、接口契约、实施计划、UX 图和部署说明。当前代码实现位于仓库根目录 `frontend/`，不是历史计划中的外部分支或单独 worktree。

## 当前实现

- `frontend/student/`：学生端，只应渲染 `session_id`、`reply_text`、`risk_level`。
- `frontend/console/`：研究分析台，可展示完整 `/chat` trace、候选、分数、偏好对和批量证据。
- `frontend/shared/`：共享 API 类型、mock 样例和 fetch wrapper。
- `frontend/scripts/build-pages.mjs`：生成 GitHub Pages mock 静态产物。

## 推荐阅读

1. `emoagent-frontend-design-baseline.md`：视觉与产品安全边界。
2. `frontend-cc-spec.md`：接口契约、模块边界、mock/live 切换。
3. `github-pages-mock-local-live.md`：GitHub Pages mock 和本机 live 演示。
4. `2026-05-26-frontend-rebuild-plan.md`：重建实施计划和历史自审记录。

## 验证命令

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

学生端安全边界检查：

```powershell
rg "FullChatResponse|fetchChat\(|scores|candidates|weighted_total|failure_reason|preference_pair" frontend\student\src
rg "scrollIntoView" frontend
```

预期：学生端源码不直接使用分析字段或 console 全量 API；前端不使用 `scrollIntoView`。
