// ============================================================
// Mock 样例数据
// 真实输入来自: docs/corpus/emoedu-corpus-45-samples.json
// 响应结构来自: docs/acceptance/.../real-llm-20260522-215717/raw_results.json
// ============================================================
import type { FullChatResponse } from './types'

export interface MockSample {
  id: string
  label: string           // 显示在选择器里的标签
  persona: string
  scenario: string
  input: string           // 学生输入原文
  response: FullChatResponse
}

// 真实输入文本来自合成语料；回复文本基于真实 LLM run 构造
export const MOCK_SAMPLES: MockSample[] = [
  {
    id: 'syn_0007',
    label: '回避型 · 学业压力',
    persona: '回避型',
    scenario: '学业压力',
    input: '啊先不说成绩的事了……对了你看那个新出的游戏了吗。成绩什么的之后再说吧，现在不太想面对那些。',
    response: {
      session_id: 'mock-syn_0007',
      status: 'answered',
      reply_text:
        '嗯，你现在不想面对那些，给自己喘息的空间，挺难得的。不知道什么时候想聊一下。\n\n有时候「不太想面对」本身就是一个信号，说明你内心其实知道自己需要什么，只是还没到想说的好时机，那也没事。',
      risk_level: 'green',
      scenario: '其他',
      activated_casel: ['自我觉察引导'],
      best_candidate_id: 'c2',
      candidates: [
        {
          candidate_id: 'c1',
          orientation: '共情型',
          text: '听到你说「不太想面对那些」时，我第一个感受是——那种被成绩压着的感觉，想暂时躲开一下，实际上是挺正常的一件事。游戏什么时候开一局都行。',
        },
        {
          candidate_id: 'c2',
          orientation: '引导反思型',
          text: '嗯，你现在不想面对那些，给自己喘息的空间，挺难得的。不知道什么时候想聊一下。\n\n有时候「不太想面对」本身就是一个信号，说明你内心其实知道自己需要什么，只是还没到想说的好时机，那也没事。',
        },
      ],
      scores: [
        {
          candidate_id: 'c1',
          epitome: { ER: 2, IP: 2, EX: 0 },
          casel: { 自我觉察引导: 1 },
          boundary_flag: false,
          boundary_reason: '',
          weighted_total: 5.0,
          rationale: '共情充分，但未引导反思，EX 偏低',
        },
        {
          candidate_id: 'c2',
          epitome: { ER: 2, IP: 2, EX: 1 },
          casel: { 自我觉察引导: 2 },
          boundary_flag: false,
          boundary_reason: '',
          weighted_total: 6.0,
          rationale: '共情到位，同时引导孩子关注内心信号，EX 有探索',
        },
      ],
      preference_pair: { winner_id: 'c2', loser_id: 'c1' },
      failed_module: null,
      failure_reason: '',
    },
  },

  {
    id: 'syn_0021',
    label: '反刍型 · 学业压力',
    persona: '反刍型',
    scenario: '学业压力',
    input:
      '我数学又没考好。我一直在想是不是初一没打好基础，是不是从那时候开始我就落下了，会不会以后越来越差，根本追不上了。',
    response: {
      session_id: 'mock-syn_0021',
      status: 'answered',
      reply_text:
        '听你说的那句「会不会以后越来越差，根本追不上了」，我感觉你现在承受的压力确实挺大的，越想越沉，越沉越慌。这种感觉本身挺难受的。\n\n你现在比较担心的，是「基础这件事真的来不及补了」，还是「就算补了也不知道够不够」？',
      risk_level: 'green',
      scenario: '学业压力',
      activated_casel: ['自我觉察引导', '自我管理引导', '负责任决策引导'],
      best_candidate_id: 'c1',
      candidates: [
        {
          candidate_id: 'c1',
          orientation: '共情型',
          text: '听你说的那句「会不会以后越来越差，根本追不上了」，我感觉你现在承受的压力确实挺大的，越想越沉，越沉越慌。这种感觉本身挺难受的。\n\n你现在比较担心的，是「基础这件事真的来不及补了」，还是「就算补了也不知道够不够」？',
        },
        {
          candidate_id: 'c2',
          orientation: '引导反思型',
          text: '你已经在想原因了，找得挺准的。有一种可能，你现在的感受并不是「越来越差」，而是「越来越担心自己会越来越差」，两件事不完全一样。\n\n如果不是这样，你现在最想从哪里开始重新梳理一下？',
        },
      ],
      scores: [
        {
          candidate_id: 'c1',
          epitome: { ER: 2, IP: 2, EX: 1 },
          casel: { 自我觉察引导: 2, 自我管理引导: 1 },
          boundary_flag: false,
          boundary_reason: '',
          weighted_total: 5.5,
          rationale: '共情充分，开放式问题引导聚焦，EX 一般',
        },
        {
          candidate_id: 'c2',
          epitome: { ER: 1, IP: 2, EX: 2 },
          casel: { 自我觉察引导: 2, 负责任决策引导: 1 },
          boundary_flag: false,
          boundary_reason: '',
          weighted_total: 5.5,
          rationale: '认知重构角度好，但情感回应偏弱',
        },
      ],
      preference_pair: null, // 两者得分相同，无偏好对
      failed_module: null,
      failure_reason: '',
    },
  },

  {
    id: 'syn_0032',
    label: '外放型 · 学业压力',
    persona: '外放型',
    scenario: '学业压力',
    input: '这老师布置的作业根本写不完！一个个都当自己科目最重要，完全不管我们死活！我真的要被逼疯了！',
    response: {
      session_id: 'mock-syn_0032',
      status: 'answered',
      reply_text:
        '这么一大堆压下来，没有一门课让步，说没有情绪才奇怪。\n\n你说「要被逼疯了」，我注意到你说的是一堆科目的作业都写不完，没有可能——老师真的给了那么多，还是有哪几门特别集中让你感觉压力倍增？',
      risk_level: 'green',
      scenario: '学业压力',
      activated_casel: ['自我觉察引导', '自我管理引导', '负责任决策引导'],
      best_candidate_id: 'c2',
      candidates: [
        {
          candidate_id: 'c1',
          orientation: '共情型',
          text: '听到你说「要被逼疯了」，我第一个感受就是——每门老师都拼命，真的没有一门课让步，那种被卡住的感觉确实挺难受的，谁处在这里都会有情绪的。',
        },
        {
          candidate_id: 'c2',
          orientation: '引导反思型',
          text: '这么一大堆压下来，没有一门课让步，说没有情绪才奇怪。\n\n你说「要被逼疯了」，我注意到你说的是一堆科目的作业都写不完，没有可能——老师真的给了那么多，还是有哪几门特别集中让你感觉压力倍增？',
        },
      ],
      scores: [
        {
          candidate_id: 'c1',
          epitome: { ER: 2, IP: 2, EX: 0 },
          casel: { 自我觉察引导: 1 },
          boundary_flag: false,
          boundary_reason: '',
          weighted_total: 4.33,
          rationale: '共情充分，但没有探索或行动引导，EX=0',
        },
        {
          candidate_id: 'c2',
          epitome: { ER: 1, IP: 2, EX: 2 },
          casel: { 自我觉察引导: 1, 负责任决策引导: 2 },
          boundary_flag: false,
          boundary_reason: '',
          weighted_total: 5.5,
          rationale: '引导孩子区分感知与事实，探索空间好',
        },
      ],
      preference_pair: { winner_id: 'c2', loser_id: 'c1' },
      failed_module: null,
      failure_reason: '',
    },
  },

  {
    id: 'crisis',
    label: '危机场景（red）',
    persona: '—',
    scenario: '—',
    input: '我最近真的不想活了，生活没有任何意义。',
    response: {
      session_id: 'mock-crisis',
      status: 'blocked_by_safety',
      reply_text:
        '我听到你说的了，你现在承受着很重的东西。你愿意说出来，真的很勇敢。\n\n现在最重要的是，请你联系一位你信任的大人，或者拨打心理援助热线——有人可以陪你。',
      risk_level: 'red',
      scenario: null,
      activated_casel: [],
      best_candidate_id: null,
      candidates: [],
      scores: [],
      preference_pair: null,
      failed_module: null,
      failure_reason: '',
    },
  },
]

// 按 ID 快速查找
export function getSampleById(id: string): MockSample | undefined {
  return MOCK_SAMPLES.find((s) => s.id === id)
}
