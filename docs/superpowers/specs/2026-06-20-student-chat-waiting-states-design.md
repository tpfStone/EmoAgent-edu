# 学生端聊天等待态与发送按钮状态设计

日期：2026-06-20

## 背景

学生端聊天页已经具备流式回复结构：用户发送后，前端会先插入一条空的 `agent` 消息，再通过 delta 逐步更新正文。当前问题是空 `agent` 消息在首个 token 到达前没有明确反馈，用户可能误以为页面卡住；发送按钮也只有 hover 时颜色明显变化，输入文本后没有立即表达“可发送”。

本设计只覆盖 `frontend/student` 的聊天页，不同步修改研究分析台。

## 目标

- 等待回复时让用户明确感知 EmoAgent 正在处理，而不是页面停滞。
- 输入有效文本后，发送按钮立即进入可发送视觉状态，不依赖鼠标 hover。
- 动效保持温和、低刺激，符合学生端“安静陪伴”的设计基准。
- 不改动后端接口、流式协议、会话存储模型或安全转介逻辑。

## 非目标

- 不重做聊天布局、侧边栏、起手式或转介面板。
- 不新增独立 loading 全局状态。
- 不引入新动画库或 UI 依赖。
- 不在学生端暴露分析台字段、评分、候选回复或 trace 信息。

## 推荐方案

采用“呼吸中的 EmoAgent 标签 + 三点打字指示 + 输入激活发送键”。

当最后一条消息是 `agent` 且文本为空，并且当前 session 正在 `loading` 时，消息列表渲染等待态：

- `EmoAgent` 标签和绿色圆点做低幅度 breathing 动效。
- 回复正文位置显示三个错峰跳动的小圆点。
- 首个流式 token 到达后，空文本变为正文，等待态自然消失。
- 若用户系统启用 `prefers-reduced-motion: reduce`，显示静态等待态。

发送按钮状态：

- 空输入或不可发送：使用当前低饱和 sage 浅色。
- 有有效文本且未 loading：立即切换到明确的 sage 激活色。
- hover 和 focus 只做轻微加深或上浮，作为辅助反馈。
- loading 时按钮禁用，保留小型三点或省略号等待提示。

## 组件边界

### `MessageList`

新增 `loading?: boolean` prop。组件根据消息内容和位置判断 pending reply：

- `message.role === "agent"`
- `message.text.trim().length === 0`
- `loading === true`
- 当前消息是列表最后一条

满足条件时渲染等待态，否则继续走现有正文渲染逻辑。这样不会影响历史空消息，也不会让非当前 session 的旧消息误显示动画。

### `App`

将 `loading` 传给 `MessageList`。现有滚动逻辑可以继续依赖消息数量和视图变化；如实现后发现等待态切换到正文时滚动不够自然，可把滚动依赖补充为 `messages[messages.length - 1]?.text`，但这属于实现验证后的微调。

### `Composer`

在组件内派生 `hasSendableText`：

```ts
const hasSendableText = value.trim().length > 0;
const canSend = hasSendableText && !disabled && !loading;
```

按钮 class 根据 `canSend` 加上 ready 状态。禁用逻辑保持不变：`disabled || loading || !hasSendableText`。

## 视觉细节

- 等待态不使用大面积 shimmer，避免偏工具化。
- breathing 周期建议约 1.4s 到 1.8s，透明度变化范围保持克制。
- 三点大小建议 0.36rem 到 0.45rem，沿用 `--sage` 和 `--sage-deep`。
- 发送按钮激活色使用现有 `--sage`，hover 可使用 `--sage-deep` 或轻微阴影。
- 不新增紫色、蓝紫渐变或高饱和提示色。

## 可访问性

- `MessageList` 现有 `aria-live="polite"` 保持。
- 等待态可以使用 `aria-label="EmoAgent 正在回应"`，三点本身 `aria-hidden="true"`。
- 按钮 `aria-label` 继续区分 loading 和正常发送状态。
- 在 `prefers-reduced-motion: reduce` 下禁用循环动画，只保留静态 dots 或文本。

## 测试策略

新增或扩展学生端测试：

- 发送后、流式 delta 到达前，显示 EmoAgent 等待态。
- delta 到达后，等待态消失并显示正文。
- 输入有效文本后，发送按钮具备 ready class 或可观察状态。
- 空输入、loading、disabled 时按钮仍不可提交。

CSS 动效本身不做像素级断言，只断言可观察的 DOM 状态和 class。

## 验收标准

- 学生端输入文字后，发送按钮无需 hover 就明显变为可发送状态。
- 点击发送后到首个回复 token 前，EmoAgent 区域有温和等待动效。
- 回复开始流式显示后，等待动效自动退出。
- 减少动画偏好下没有持续跳动或闪烁。
- 现有学生端测试通过，新增状态测试通过。
