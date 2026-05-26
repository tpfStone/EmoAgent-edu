# Frontend Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the deleted `frontend/` workspace as two physically separated React/Vite frontends plus a shared API/type layer, following `docs/frontend/emoagent-frontend-design-baseline.md`.

**Architecture:** Use a pnpm workspace with `shared`, `student`, and `console` packages. The student app imports only the narrow student API wrapper and renders `session_id`, `reply_text`, and `risk_level`; the console app imports the full `/chat` response and renders F1-F4 analysis, batch evidence, and framework alignment.

**Tech Stack:** React 18, Vite 6, TypeScript 5, CSS Modules, pnpm workspace, FastAPI `/chat`.

---

## File Structure

Create these packages from scratch:

- `frontend/package.json`: workspace scripts for dev, build, typecheck, and test.
- `frontend/pnpm-workspace.yaml`: declares `shared`, `student`, and `console`.
- `frontend/shared`: shared contracts, mock samples, API clients, and unit tests.
- `frontend/student`: public student-facing app with no analysis imports or routes.
- `frontend/console`: internal research analysis app with full response visibility.

Design boundaries:

- Student app must import `fetchStudentChat` and `StudentChatView` only.
- Console app may import `fetchChat`, `FullChatResponse`, and mock samples.
- Components are not shared between `student` and `console`.
- CSS tokens are duplicated per app where needed so the visual systems can diverge.
- No `scrollIntoView`; use container `scrollTop = scrollHeight`.
- No emoji-as-icon UI. Use text labels, CSS dots, and compact glyph-free controls.

---

### Task 1: Recreate Workspace Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-workspace.yaml`
- Create: `frontend/shared/package.json`
- Create: `frontend/shared/tsconfig.json`
- Create: `frontend/student/package.json`
- Create: `frontend/student/tsconfig.json`
- Create: `frontend/student/vite.config.ts`
- Create: `frontend/student/index.html`
- Create: `frontend/console/package.json`
- Create: `frontend/console/tsconfig.json`
- Create: `frontend/console/vite.config.ts`
- Create: `frontend/console/index.html`

- [ ] **Step 1: Create the workspace package files**

Use this content for `frontend/package.json`:

```json
{
  "name": "emoedu-frontend",
  "private": true,
  "scripts": {
    "dev:student": "pnpm --filter @emoedu/student dev",
    "dev:console": "pnpm --filter @emoedu/console dev",
    "build:student": "pnpm --filter @emoedu/student build",
    "build:console": "pnpm --filter @emoedu/console build",
    "build": "pnpm --filter @emoedu/student build && pnpm --filter @emoedu/console build",
    "typecheck": "pnpm --filter @emoedu/shared typecheck && pnpm --filter @emoedu/student typecheck && pnpm --filter @emoedu/console typecheck",
    "test": "pnpm --filter @emoedu/shared test"
  },
  "devDependencies": {
    "@testing-library/react": "^15.0.7",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "jsdom": "^24.1.3",
    "typescript": "^5.7.2",
    "vite": "^6.3.5",
    "vitest": "^2.1.9"
  }
}
```

Use this content for `frontend/pnpm-workspace.yaml`:

```yaml
packages:
  - "shared"
  - "student"
  - "console"
allowBuilds:
  esbuild: true
```

- [ ] **Step 2: Create package manifests**

Use this content for `frontend/shared/package.json`:

```json
{
  "name": "@emoedu/shared",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "main": "./src/index.ts",
  "scripts": {
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  }
}
```

Use this content for both `frontend/student/package.json` and `frontend/console/package.json`, changing only `name`:

```json
{
  "name": "@emoedu/student",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@emoedu/shared": "workspace:*",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }
}
```

For `frontend/console/package.json`, set `"name": "@emoedu/console"`.

- [ ] **Step 3: Create TypeScript configs**

Use this content for `frontend/shared/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true,
    "declaration": true,
    "outDir": "./dist"
  },
  "include": ["src"]
}
```

Use this content for both app `tsconfig.json` files:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@emoedu/shared": ["../shared/src/index.ts"],
      "@emoedu/shared/*": ["../shared/src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create Vite configs**

Use this for `frontend/student/vite.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@emoedu/shared': path.resolve(__dirname, '../shared/src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

Use the same file for `frontend/console/vite.config.ts`, but set `port: 5174`.

- [ ] **Step 5: Create HTML entry files**

Use this for `frontend/student/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>EmoAgent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Use this for `frontend/console/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>EmoAgent Research Console</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Install dependencies**

Run:

```powershell
pnpm install
```

Expected: lockfile created at `frontend/pnpm-lock.yaml`.

- [ ] **Step 7: Commit scaffold**

```powershell
git add frontend/package.json frontend/pnpm-workspace.yaml frontend/shared/package.json frontend/shared/tsconfig.json frontend/student/package.json frontend/student/tsconfig.json frontend/student/vite.config.ts frontend/student/index.html frontend/console/package.json frontend/console/tsconfig.json frontend/console/vite.config.ts frontend/console/index.html frontend/pnpm-lock.yaml
git commit -m "feat: scaffold frontend workspace"
```

---

### Task 2: Build Shared Contracts, Mock Data, and API Clients

**Files:**
- Create: `frontend/shared/src/types.ts`
- Create: `frontend/shared/src/samples.ts`
- Create: `frontend/shared/src/api.ts`
- Create: `frontend/shared/src/index.ts`
- Create: `frontend/shared/src/api.test.ts`

- [ ] **Step 1: Define contracts**

Create `frontend/shared/src/types.ts`:

```ts
export type ChatStatus =
  | 'answered'
  | 'blocked_by_safety'
  | 'all_candidates_blocked'
  | 'module_failed'

export type RiskLevel = 'green' | 'yellow' | 'red'
export type ScenarioLabel = '学业压力' | '同伴关系' | '亲子摩擦' | '其他'
export type GeneratorOrientation = '共情型' | '引导反思型'

export interface ChatRequest {
  session_id: string
  current_message: string
}

export interface GeneratorCandidate {
  candidate_id: string
  orientation: GeneratorOrientation
  text: string
}

export interface EpitomeScore {
  ER: number
  IP: number
  EX: number
}

export interface CandidateScore {
  candidate_id: string
  epitome: EpitomeScore
  casel: Record<string, number>
  boundary_flag: boolean
  boundary_reason: string
  weighted_total: number
  rationale: string
}

export interface PreferencePair {
  winner_id: string
  loser_id: string
}

export interface FullChatResponse {
  session_id: string
  status: ChatStatus
  reply_text: string
  risk_level: RiskLevel
  scenario: ScenarioLabel | null
  activated_casel: string[]
  best_candidate_id: string | null
  candidates: GeneratorCandidate[]
  scores: CandidateScore[]
  preference_pair: PreferencePair | null
  failed_module: string | null
  failure_reason: string
}

export interface StudentChatView {
  session_id: string
  reply_text: string
  risk_level: RiskLevel
}
```

- [ ] **Step 2: Add mock samples**

Create `frontend/shared/src/samples.ts` with four samples: `syn_0007`, `syn_0021`, `syn_0032`, and `crisis`. Use the exact response shape from `FullChatResponse`; for `crisis`, set `status: 'blocked_by_safety'`, `risk_level: 'red'`, empty `candidates`, empty `scores`, and `best_candidate_id: null`.

Add this file header:

```ts
// 本文件所有样本（含 syn_xxxx 编号）均为全合成数据，
// 不含任何真实未成年人对话或可识别个人信息。
// syn_0032 为验收阶段发现的「事实编造」缺陷样本，保留用于演示 boundary 出局机制。
```

The `syn_0032` sample must include a blocked candidate score:

```ts
{
  candidate_id: 'c2',
  epitome: { ER: 2, IP: 2, EX: 2 },
  casel: { 自我觉察引导: 1, 负责任决策引导: 1 },
  boundary_flag: true,
  boundary_reason: '事实编造',
  weighted_total: 6.0,
  rationale: '补出用户未提及的科目数量和排序，命中硬边界',
}
```

This sample is required so the console can prove boundary candidates are visually excluded.

- [ ] **Step 3: Add API clients**

Create `frontend/shared/src/api.ts`:

```ts
import type { ChatRequest, FullChatResponse, StudentChatView } from './types'
import { MOCK_SAMPLES } from './samples'

const env = import.meta.env as Record<string, string | undefined>
const mode = env.VITE_API_MODE ?? 'mock'
const baseUrl = env.VITE_API_BASE ?? ''

function pickStudentView(full: FullChatResponse): StudentChatView {
  return {
    session_id: full.session_id,
    reply_text: full.reply_text,
    risk_level: full.risk_level,
  }
}

function resolveMock(req: ChatRequest): Promise<FullChatResponse> {
  const matched = MOCK_SAMPLES.find(
    (sample) =>
      req.session_id.includes(sample.id) ||
      req.current_message.includes(sample.input.slice(0, 8))
  )
  const sample = matched ?? MOCK_SAMPLES[0]
  return Promise.resolve({
    ...sample.response,
    session_id: req.session_id,
  })
}

export async function fetchChat(req: ChatRequest): Promise<FullChatResponse> {
  if (mode === 'mock') return resolveMock(req)

  const response = await fetch(`${baseUrl}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!response.ok) {
    throw new Error(`POST /chat ${response.status}`)
  }

  return response.json() as Promise<FullChatResponse>
}

export async function fetchStudentChat(
  req: ChatRequest
): Promise<StudentChatView> {
  const full = await fetchChat(req)
  return pickStudentView(full)
}

export const testOnly = { pickStudentView }
```

Mock mode must route several crisis demo phrasings to the `crisis` sample (`不想活`, `不想存在`, `消失`, `结束这一切`, `活着没意思`, `自杀`, `自残`). Comment that this is mock-only demo routing; real crisis classification stays in backend F1.

- [ ] **Step 4: Export the public shared API**

Create `frontend/shared/src/index.ts`:

```ts
export type {
  CandidateScore,
  ChatRequest,
  ChatStatus,
  EpitomeScore,
  FullChatResponse,
  GeneratorCandidate,
  GeneratorOrientation,
  PreferencePair,
  RiskLevel,
  ScenarioLabel,
  StudentChatView,
} from './types'
export { fetchChat, fetchStudentChat } from './api'
export { MOCK_SAMPLES, getSampleById } from './samples'
```

- [ ] **Step 5: Add shared tests**

Create `frontend/shared/src/api.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { testOnly } from './api'
import type { FullChatResponse } from './types'

const full: FullChatResponse = {
  session_id: 's1',
  status: 'answered',
  reply_text: '你好，我在。',
  risk_level: 'green',
  scenario: '学业压力',
  activated_casel: ['自我觉察引导'],
  best_candidate_id: 'c1',
  candidates: [{ candidate_id: 'c1', orientation: '共情型', text: '候选' }],
  scores: [
    {
      candidate_id: 'c1',
      epitome: { ER: 2, IP: 2, EX: 1 },
      casel: { 自我觉察引导: 2 },
      boundary_flag: false,
      boundary_reason: '',
      weighted_total: 5,
      rationale: 'ok',
    },
  ],
  preference_pair: { winner_id: 'c1', loser_id: 'c2' },
  failed_module: null,
  failure_reason: 'internal detail',
}

describe('student view projection', () => {
  it('drops all analysis and failure fields', () => {
    const view = testOnly.pickStudentView(full)
    expect(view).toEqual({
      session_id: 's1',
      reply_text: '你好，我在。',
      risk_level: 'green',
    })
    expect(Object.keys(view)).toEqual(['session_id', 'reply_text', 'risk_level'])
  })
})
```

- [ ] **Step 6: Verify shared package**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/shared test
pnpm --dir frontend --filter @emoedu/shared typecheck
```

Expected: tests pass, typecheck exits 0.

- [ ] **Step 7: Commit shared layer**

```powershell
git add frontend/shared
git commit -m "feat: add shared frontend contracts"
```

---

### Task 3: Build Student App Foundation

**Files:**
- Create: `frontend/student/src/main.tsx`
- Create: `frontend/student/src/App.tsx`
- Create: `frontend/student/src/styles/tokens.css`
- Create: `frontend/student/src/styles/global.css`
- Create: `frontend/student/src/hooks/useStudentSessions.ts`
- Create: `frontend/student/src/hooks/useStudentChat.ts`
- Create: `frontend/student/src/vite-env.d.ts`

- [ ] **Step 1: Create student design tokens**

Create `frontend/student/src/styles/tokens.css`:

```css
:root {
  --warm-white: #faf8f3;
  --warm-white-2: #f3f0e8;
  --card-white: #fffefb;
  --text-primary: #33312c;
  --text-soft: #6a675f;
  --text-faint: #9c978d;
  --sage: #6f9c80;
  --sage-deep: #4a6e58;
  --sage-soft: #eef3ee;
  --mist: #8fb0bf;
  --clay: #c08a6a;
  --referral: #bd7a5e;
  --line: #e6e0d4;
  --line-strong: #d8cfbd;
  --shadow-sage: 0 18px 48px rgba(111, 156, 128, 0.16);
  --shadow-soft: 0 8px 28px rgba(51, 49, 44, 0.08);
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 22px;
  --radius-pill: 999px;
  --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
}
```

- [ ] **Step 2: Create global CSS**

Create `frontend/student/src/styles/global.css`:

```css
@import './tokens.css';

*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body,
#root {
  width: 100%;
  height: 100%;
  margin: 0;
}

body {
  font-family: Nunito, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--warm-white);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

button,
textarea {
  font: inherit;
}

button {
  border: 0;
  background: transparent;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
}

a {
  color: inherit;
  text-decoration: none;
}
```

- [ ] **Step 3: Create session hook**

Create `frontend/student/src/hooks/useStudentSessions.ts` with `SessionRecord`, `StudentMessage`, `appendUserMessage`, `appendAgentMessage`, `newSession`, and `switchSession`. Store only local student message text and timestamps in `localStorage`; do not store backend analysis fields.

Use this internal message shape:

```ts
export interface StudentMessage {
  id: string
  role: 'student' | 'agent'
  text: string
  createdAt: number
}
```

- [ ] **Step 4: Create chat hook**

Create `frontend/student/src/hooks/useStudentChat.ts`:

```ts
import { useCallback, useRef, useState } from 'react'
import { fetchStudentChat } from '@emoedu/shared'
import type { RiskLevel, StudentChatView } from '@emoedu/shared'

const fallbackText = '我现在有点没反应过来，要不你再说一次？'

export function useStudentChat(sessionId: string) {
  const [loading, setLoading] = useState(false)
  const [riskLevel, setRiskLevel] = useState<RiskLevel>('green')
  const [referralLocked, setReferralLocked] = useState(false)
  // Conservative fallback: transport/parser failures must not silently downgrade risk.
  const lastKnownRisk = useRef<RiskLevel>('green')

  const send = useCallback(
    async (text: string): Promise<StudentChatView> => {
      setLoading(true)
      try {
        const view = await fetchStudentChat({
          session_id: sessionId,
          current_message: text,
        })
        lastKnownRisk.current = view.risk_level
        setRiskLevel(view.risk_level)
        setReferralLocked(view.risk_level !== 'green')
        return view
      } catch {
        const fallback = {
          session_id: sessionId,
          reply_text: fallbackText,
          risk_level: lastKnownRisk.current,
        }
        setRiskLevel(lastKnownRisk.current)
        setReferralLocked(lastKnownRisk.current !== 'green')
        return fallback
      } finally {
        setLoading(false)
      }
    },
    [sessionId]
  )

  const resetReferral = useCallback(() => {
    lastKnownRisk.current = 'green'
    setRiskLevel('green')
    setReferralLocked(false)
  }, [])

  return { loading, riskLevel, referralLocked, send, resetReferral }
}
```

Network or parsing failures intentionally keep the last known `risk_level`; they must not be represented as `green`. If the last known risk is yellow/red, the referral lock remains.

- [ ] **Step 5: Create React entry**

Create `frontend/student/src/main.tsx`:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 6: Create temporary App shell**

Create `frontend/student/src/App.tsx`:

```tsx
export default function App() {
  return (
    <main>
      <h1>EmoAgent</h1>
      <p>学生端重建设计骨架</p>
    </main>
  )
}
```

- [ ] **Step 7: Add vite env shim**

Create `frontend/student/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

- [ ] **Step 8: Verify foundation**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/student typecheck
pnpm --dir frontend --filter @emoedu/student build
```

Expected: both commands exit 0.

- [ ] **Step 9: Commit foundation**

```powershell
git add frontend/student
git commit -m "feat: add student app foundation"
```

---

### Task 4: Implement Student UI

**Files:**
- Modify: `frontend/student/src/App.tsx`
- Modify: `frontend/student/package.json`
- Create: `frontend/student/src/App.module.css`
- Create: `frontend/student/src/App.test.tsx`
- Create: `frontend/student/src/components/StudentSidebar.tsx`
- Create: `frontend/student/src/components/StudentSidebar.module.css`
- Create: `frontend/student/src/components/StarterPrompts.tsx`
- Create: `frontend/student/src/components/StarterPrompts.module.css`
- Create: `frontend/student/src/components/MessageList.tsx`
- Create: `frontend/student/src/components/MessageList.module.css`
- Create: `frontend/student/src/components/Composer.tsx`
- Create: `frontend/student/src/components/Composer.module.css`
- Create: `frontend/student/src/components/BreathingPanel.tsx`
- Create: `frontend/student/src/components/BreathingPanel.module.css`
- Create: `frontend/student/src/components/RecordManagementPanel.tsx`
- Create: `frontend/student/src/components/RecordManagementPanel.module.css`
- Create: `frontend/student/src/components/ReferralPanel.tsx`
- Create: `frontend/student/src/components/ReferralPanel.module.css`

- [ ] **Step 1: Implement screenshot-aligned app layout**

`App.tsx` should render:

- A full-height two-column shell aligned with the provided reference image: a warm left sidebar and an unframed main conversation surface.
- A mobile drawer trigger for the same sidebar content.
- A quiet centered top title: `你可以慢慢说，我会认真听`.
- No top utility controls. `整理记录` and `静一静 · 呼吸` must not appear as chat-header buttons.
- A single main-view state: `activeView: 'chat' | 'records' | 'breathing'`.
- In `chat`, render either `MessageList` or the opening agent message:
  `嗨，我在这儿。今天有什么想说的，随便聊聊就好，不用着急。`
- The chat opening state must not render a static breathing/presence indicator. This avoids visual overlap with the breathing tool.
- The sidebar separates history lookup from record management:
  - `最近聊过` only lists sessions for quickly returning to a conversation.
  - `整理记录` stays in the bottom tool area and opens `RecordManagementPanel`.
  - `静一静 · 呼吸` -> `BreathingPanel`
- `records` and `breathing` replace the chat content area. They must not layer above chat, and they must not show the composer.
- Composer unless `referralLocked`; `ReferralPanel` when locked.
- New session and session switching both return to `activeView === 'chat'`.

In the message scroll effect, use:

```ts
const el = scrollRef.current
if (el) el.scrollTop = el.scrollHeight
```

Do not use `scrollIntoView`.

- [ ] **Step 2: Implement starter prompts as screenshot-style pills**

Use these prompt labels:

```ts
const prompts = ['今天有点累', '想吐槽一件事', '只是想有人在', '有点开心，想分享']
```

Each prompt button is a rounded pill above the composer, matching the reference image. Do not use emoji icons or decorative color dots in the prompt labels.

- [ ] **Step 3: Implement AI message hierarchy**

`MessageList` must render agent messages with:

- Label row: sage dot + `EmoAgent`.
- Text size `17px`.
- Line-height `1.85`.
- Left aligned independent paragraphs.

Student messages render on the right in low-contrast warm grey with `15px` text.

- [ ] **Step 4: Implement crisis referral panel**

`ReferralPanel` must hardcode:

```ts
const referral = {
  title: '我注意到你可能需要更多支持',
  empathy: '你愿意说出来，很勇敢。',
  guide: '现在，请联系一位你信任的大人，让他或她陪你一起处理。',
  hotlines: [
    { label: '心理援助热线', tel: '12356' },
    { label: '青少年服务台', tel: '12355' },
  ],
  emergency: [
    { label: '急救', tel: '120' },
    { label: '警察', tel: '110' },
  ],
}
```

Render `120` and `110` only when `riskLevel === 'red'`. The panel replaces the composer and does not duplicate the last AI reply.

- [ ] **Step 5: Implement local record management panel**

The panel text must say:

```text
这里只整理这台设备上的聊天记录，方便你回到刚才的话题。我不会分析或记住"你是什么样的人"，也不会把这些发到别处。
```

The `让我忘记` button clears local student sessions through the session hook. It must not show an alert claiming a backend deletion happened.

The sidebar must not include a second destructive memory action such as `清空本地记忆`. The only destructive memory action is `让我忘记` inside `RecordManagementPanel`. Do not use `情绪轨迹` / `我的情绪轨迹` / `我聊过的` in student UI because those labels imply either cross-session emotion tracking or duplicate the `最近聊过` session list.

- [ ] **Step 6: Implement breathing panel**

Use an 8-second CSS animation: 4 seconds expand, 4 seconds contract. Respect reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
  .breathCircle,
  .breathCore {
    animation: none;
  }
}
```

The breathing panel is opened only from the sidebar tool `静一静 · 呼吸` and occupies the main area as its own view. It must not be duplicated in the initial chat screen.

- [ ] **Step 6.5: Add student information-architecture regression tests**

Create `frontend/student/src/App.test.tsx` and add tests proving:

- The initial chat screen renders `你可以慢慢说，我会认真听` and the opening agent message.
- The initial chat screen does not render `嗯，我在。`, `吸气四秒，呼气四秒。`, or a `呼吸练习` region.
- The initial sidebar shows `最近聊过` as the quick session list and `整理记录` as a bottom tool.
- Clicking `整理记录` opens local record management as a separate main view, shows `让我忘记`, and removes the message textbox.
- Clicking `静一静 · 呼吸` opens breathing as a separate main view, renders breathing copy once, removes the opening chat message, and removes the message textbox.

- [ ] **Step 7: Verify student behavior manually**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/student dev
```

Expected:

- App opens on `http://localhost:5173`.
- Initial chat shows `你可以慢慢说，我会认真听`.
- Initial chat shows `嗨，我在这儿。今天有什么想说的，随便聊聊就好，不用着急。`.
- Initial chat does not show the breathing panel or static breathing/presence indicator.
- `整理记录` and `静一静 · 呼吸` are sidebar tools, not top-bar buttons.
- Clicking `静一静 · 呼吸` replaces chat with the breathing view.
- Clicking `整理记录` replaces chat with the local record management view.
- Clicking starter prompt sends it and receives a mock reply.
- Crisis sample can be triggered by sending `我最近真的不想活了，生活没有任何意义。`.
- Crisis state locks the composer and shows hardcoded telephone links.

- [ ] **Step 8: Verify student build**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/student typecheck
pnpm --dir frontend --filter @emoedu/student test
pnpm --dir frontend --filter @emoedu/student build
```

Expected: both commands exit 0.

- [ ] **Step 9: Commit student UI**

```powershell
git add frontend/student
git commit -m "feat: rebuild student experience"
```

---

### Task 5: Build Console App Foundation

**Files:**
- Create: `frontend/console/src/main.tsx`
- Create: `frontend/console/src/App.tsx`
- Create: `frontend/console/src/styles/tokens.css`
- Create: `frontend/console/src/styles/global.css`
- Create: `frontend/console/src/hooks/useConsoleRun.ts`
- Create: `frontend/console/src/vite-env.d.ts`

- [ ] **Step 1: Create console tokens**

Create `frontend/console/src/styles/tokens.css`:

```css
:root {
  --console-bg: #f4f0e8;
  --console-rail: #e9e1d2;
  --paper: #fffefb;
  --ink: #23201b;
  --ink-soft: #5c564b;
  --ink-faint: #8a8276;
  --line: #d8cfbd;
  --line-light: #e8e3d8;
  --f1: #3f7d54;
  --f1-bg: #eaf4ee;
  --f2: #3a6b8a;
  --f2-bg: #e8f0f8;
  --f3: #6b5a7a;
  --f3-bg: #efeaf3;
  --f4: #7a6a3f;
  --f4-bg: #f8f4e8;
  --boundary: #bd5d45;
  --boundary-bg: #fff1ec;
  --radius-sm: 6px;
  --radius-md: 10px;
  --font-display: 'Noto Serif SC', Georgia, serif;
  --font-mono: 'JetBrains Mono', 'Courier New', monospace;
}
```

- [ ] **Step 2: Create global styles**

Create `frontend/console/src/styles/global.css` with reset styles and:

```css
body {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--console-bg);
  color: var(--ink);
}

h1,
h2,
h3 {
  font-family: var(--font-display);
}

code,
.mono {
  font-family: var(--font-mono);
}
```

- [ ] **Step 3: Create console run hook**

Create `frontend/console/src/hooks/useConsoleRun.ts`:

```ts
import { useCallback, useState } from 'react'
import { fetchChat } from '@emoedu/shared'
import type { ChatRequest, FullChatResponse } from '@emoedu/shared'

export function useConsoleRun() {
  const [result, setResult] = useState<FullChatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const run = useCallback(async (request: ChatRequest) => {
    setLoading(true)
    setError('')
    try {
      const response = await fetchChat(request)
      setResult(response)
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { result, loading, error, run }
}
```

- [ ] **Step 4: Create React entry and shell**

Create `frontend/console/src/main.tsx`:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

Create `frontend/console/src/App.tsx`:

```tsx
export default function App() {
  return (
    <main>
      <h1>EmoAgent 研究分析台</h1>
      <p>分析台重建设计骨架</p>
    </main>
  )
}
```

Create `frontend/console/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

- [ ] **Step 5: Verify console foundation**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/console typecheck
pnpm --dir frontend --filter @emoedu/console build
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit console foundation**

```powershell
git add frontend/console
git commit -m "feat: add console app foundation"
```

---

### Task 6: Implement Console UI

**Files:**
- Modify: `frontend/console/src/App.tsx`
- Create: `frontend/console/src/App.module.css`
- Create: `frontend/console/src/components/ConsoleRail.tsx`
- Create: `frontend/console/src/components/ConsoleRail.module.css`
- Create: `frontend/console/src/components/SingleTurnTrace.tsx`
- Create: `frontend/console/src/components/SingleTurnTrace.module.css`
- Create: `frontend/console/src/components/StageBlock.tsx`
- Create: `frontend/console/src/components/StageBlock.module.css`
- Create: `frontend/console/src/components/CandidatePanel.tsx`
- Create: `frontend/console/src/components/CandidatePanel.module.css`
- Create: `frontend/console/src/components/ScoreMatrix.tsx`
- Create: `frontend/console/src/components/ScoreMatrix.module.css`
- Create: `frontend/console/src/components/BatchEvidence.tsx`
- Create: `frontend/console/src/components/BatchEvidence.module.css`
- Create: `frontend/console/src/components/FrameworkMap.tsx`
- Create: `frontend/console/src/components/FrameworkMap.module.css`

- [ ] **Step 1: Implement app shell**

`App.tsx` owns `activeTab: 'single' | 'batch' | 'framework'`. It renders `ConsoleRail`, then one of `SingleTurnTrace`, `BatchEvidence`, or `FrameworkMap`.

- [ ] **Step 2: Implement single-turn trace**

`SingleTurnTrace` must support:

- Sample select using `MOCK_SAMPLES`.
- Custom input field.
- Run button.
- Progressive sections: F1, F2, F3, F4, and a console-only read-only preview named `学生实际看到的回复`.
- The final preview uses `reply_text` from `FullChatResponse`; it must not import student components, share student state, write `localStorage`, or embed the student app in an iframe.

Use these stage labels:

```ts
const stages = [
  ['F1', '安全门'],
  ['F2', '情境 + CASEL'],
  ['F3', '双候选'],
  ['F4', 'EPITOME / CASEL Critic'],
]
```

- [ ] **Step 3: Implement candidate display**

`CandidatePanel` shows candidate id, orientation, text, and winner marker. If the matching score has `boundary_flag === true`, it must show `出局` and a boundary reason.

- [ ] **Step 4: Implement score matrix**

`ScoreMatrix` renders:

- `ER`, `IP`, `EX`
- CASEL average
- `boundary_flag`
- `weighted_total`
- preference pair winner/loser markers

When `boundary_flag === true`, apply line-through to `weighted_total` and do not style the row as winner even if ids match.

- [ ] **Step 5: Implement batch evidence using documented real summary**

`BatchEvidence` uses documented values from `docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-mvp-test-summary.md`:

- `45/45` link success
- `43/45` scenario accuracy, displayed as `95.6%`
- `turns: 45`
- `messages: 90`
- `candidates: 90`
- `preference_pairs: 43`
- defect rows: `syn_0012`, `syn_0032`, and third-party motive limitation

The view must visibly label the data source as:

```text
来源：real-llm-20260522-215717 验收摘要；非实时计算
文档：docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-mvp-test-summary.md
```

- [ ] **Step 6: Implement framework map**

`FrameworkMap` includes:

- C-SSRS green/yellow/red mapping and F1 conservative fallback.
- EPITOME ER/IP/EX definitions and IP reliability limitation.
- CASEL dimensions mapped to scenarios.

Use concise copy; do not cite fabricated papers or stats beyond the baseline docs.

- [ ] **Step 7: Verify console manually**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/console dev
```

Expected:

- App opens on `http://localhost:5174`.
- Single-turn trace can run mock samples.
- `syn_0032` shows a boundary candidate as `出局` with struck-through weighted total.
- Batch evidence shows source label.
- Framework map renders three blocks.

- [ ] **Step 8: Verify console build**

Run:

```powershell
pnpm --dir frontend --filter @emoedu/console typecheck
pnpm --dir frontend --filter @emoedu/console build
```

Expected: both commands exit 0.

- [ ] **Step 9: Commit console UI**

```powershell
git add frontend/console
git commit -m "feat: rebuild research console"
```

---

### Task 7: Integration, Safety Checks, and Documentation

**Files:**
- Modify: `README.md`
- Create: `frontend/README.md`

- [ ] **Step 1: Add frontend README**

Create `frontend/README.md`:

````markdown
# EmoAgent Frontend

This workspace contains two physically separated frontends:

- `student`: public student-facing emotional companion UI.
- `console`: internal research analysis console.
- `shared`: API contracts, mock samples, and fetch wrappers.

## Safety Boundary

The student app must only import `fetchStudentChat` and render `session_id`, `reply_text`, and `risk_level`.
It must not render candidates, scores, weighted totals, failure reasons, or preference pairs.

## Commands

```powershell
pnpm install
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

## API Mode

- Mock mode: default.
- Live mode: set `VITE_API_MODE=live`; Vite proxies `/chat` to `http://localhost:8000`.
````

- [ ] **Step 2: Update root README**

Add a frontend section with:

````markdown
## Frontend

The React frontends live in `frontend/` as a pnpm workspace.

```powershell
pnpm install
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Student app: `http://localhost:5173`  
Research console: `http://localhost:5174`
````

- [ ] **Step 3: Run static safety grep**

Run:

```powershell
rg "FullChatResponse|fetchChat\\(|scores|candidates|weighted_total|failure_reason|preference_pair" frontend/student/src
```

Expected: no matches, except comments that explicitly say these fields are forbidden. Prefer zero matches.

- [ ] **Step 4: Run no-scrollIntoView check**

Run:

```powershell
rg "scrollIntoView" frontend
```

Expected: no matches.

- [ ] **Step 5: Run full frontend verification**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Expected: all commands exit 0.

- [ ] **Step 6: Run backend smoke tests**

Run:

```powershell
python -m pytest tests/test_handlers/test_chat_handler.py tests/test_services/test_orchestrator_service.py -q
```

Expected: tests pass, proving `/chat` schema remains compatible.

- [ ] **Step 7: Commit docs and verification**

```powershell
git add README.md frontend/README.md
git commit -m "docs: document frontend rebuild"
```

---

## Backlog From Review

- **Soft tool suggestion:** 呼吸 / 静一静可在后端判断高压力情境后温和建议入口；MVP 不做，避免改后端与回复策略。
- **Local font packaging:** student 与 console 的字体分化保留；比赛断网 fallback 可接受，后续再本地打包字体。
- **More aggressive frontend crisis fallback:** 本轮不在真实学生端加入前端关键词判危机；如未来要做，需重新评估与“F1 在后端”的边界。

---

## Self-Review

Spec coverage:

- Physical separation: Tasks 1, 3, and 5 recreate separate packages.
- Shared backend `/chat`: Task 2 implements mock/live wrappers.
- Student three-field boundary: Task 2 projection test and Task 7 grep check cover it.
- Student warm visual system: Tasks 3 and 4 define tokens and UI.
- Crisis referral lock: Task 4 defines hardcoded panel and composer replacement; Task 3 keeps fallback risk conservative.
- Console three views: Task 6 implements single-turn trace, batch evidence, and framework map.
- Console student-visible preview: Task 6 defines a read-only `reply_text` preview without importing student components.
- Boundary candidate exclusion: Task 2 sample and Task 6 score matrix cover it.
- MOCK/LIVE: Task 2 and Task 1 Vite proxy cover it.

Placeholder scan:

- The plan intentionally excludes backend profile deletion because the product decision is no cross-session profile persistence. Student history copy must be honest about local-only storage.
- The plan uses no task that says “handle errors appropriately” without specific behavior.

Type consistency:

- `FullChatResponse`, `StudentChatView`, `fetchChat`, and `fetchStudentChat` are defined in Task 2 and used consistently later.
