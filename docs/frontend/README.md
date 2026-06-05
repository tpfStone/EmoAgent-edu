# 前端文档入口

本目录保存前端设计、接口契约、实施计划、UX 图和部署说明。当前代码实现位于仓库根目录 `frontend/`，不是历史计划中的外部分支或单独 worktree。

## 当前实现

- `frontend/student/`：学生端，优先使用 `/chat/stream`，只渲染用户需要看到的简洁回复、基础风险状态和会话连续性信息。
- `frontend/console/`：研究分析台，可展示完整 `/chat` trace、候选、分数、偏好对和批量证据；它服务研究和调试，不代表学生端体验。
- `frontend/shared/`：共享 API 类型、mock 样例和 fetch wrapper，包含 SSE 事件解析。
- `frontend/scripts/build-pages.mjs`：生成 GitHub Pages mock 静态产物。

## 当前交互口径

学生端应以“短、清楚、低负担”为原则呈现输出。后端已经把 `/chat/stream` 事件拆为：

| 事件 | 用途 |
| --- | --- |
| `stage` | 请求已接收等轻量阶段信息 |
| `metadata` | 不含 `reply_text` 的状态信息 |
| `delta` | 流式文本增量 |
| `done` | 完整 `ChatResponse` |
| `error` | 流式错误 |

学生端不要展示 F1/F2/F3/F4 内部术语、critic 分数、CASEL/EPITOME 细节或候选对比。研究分析台可以展示这些信息，但需要明确它是调试视图。

当前后端生产链路是首次对话 `F1 -> F2 -> F3 -> 流式返回 -> 后台 F4`，后续对话走轻量 CBT 支持。前端不需要等待后台 F4，也不需要感知 F4 是否完成；下一轮如果后端已经拿到 guidance，会由生成器内部使用。

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
