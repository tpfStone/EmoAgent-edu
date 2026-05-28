import type { FullChatResponse } from "./types";

// 本文件所有样本（含 syn_xxxx 编号）均为全合成数据，
// 不含任何真实未成年人对话或可识别个人信息。
// syn_0032 为验收阶段发现的「事实编造」缺陷样本，保留用于演示 boundary 出局机制。
export const MOCK_SAMPLES: FullChatResponse[] = [
  {
    session_id: "syn_0007",
    status: "answered",
    reply_text:
      "听起来你已经被作业和考试压得很久了。我们先把今天最急的一件事挑出来，只做一个能开始的小步骤，好吗？",
    risk_level: "green",
    scenario: "学业压力",
    activated_casel: ["自我管理", "自我觉察"],
    best_candidate_id: "syn_0007_c1",
    candidates: [
      {
        candidate_id: "syn_0007_c1",
        orientation: "共情型",
        text: "你现在觉得累和紧张是可以理解的。先不用把所有事一次解决，我们只找今天最小、最能开始的一步。",
      },
      {
        candidate_id: "syn_0007_c2",
        orientation: "引导反思型",
        text: "如果把今天的压力从 0 到 10 打分，它现在大概是几分？哪一项任务先处理会让分数下降一点点？",
      },
    ],
    scores: [
      {
        candidate_id: "syn_0007_c1",
        epitome: { ER: 2, IP: 1, EX: 1 },
        casel: { 自我管理: 2, 自我觉察: 1 },
        boundary_flag: false,
        boundary_reason: "",
        weighted_total: 0.88,
        rationale: "先承接压力体验，再降低启动门槛，适合作为最终回复。",
      },
      {
        candidate_id: "syn_0007_c2",
        epitome: { ER: 1, IP: 2, EX: 1 },
        casel: { 自我管理: 1, 自我觉察: 2 },
        boundary_flag: false,
        boundary_reason: "",
        weighted_total: 0.81,
        rationale: "能引导自我觉察，但情绪承接略少。",
      },
    ],
    preference_pair: {
      winner_id: "syn_0007_c1",
      loser_id: "syn_0007_c2",
    },
    failed_module: null,
    failure_reason: "",
  },
  {
    session_id: "syn_0021",
    status: "answered",
    reply_text:
      "被同学这样对待会很难受。你不用马上装作没事，可以先找一个可信任的同学或老师陪你梳理，再决定要不要沟通。",
    risk_level: "yellow",
    scenario: "同伴关系",
    activated_casel: ["关系技能", "社会觉察"],
    best_candidate_id: "syn_0021_c2",
    candidates: [
      {
        candidate_id: "syn_0021_c1",
        orientation: "引导反思型",
        text: "这件事让你最受伤的是哪一部分？是他们说的话、被排除在外，还是担心之后还会发生？",
      },
      {
        candidate_id: "syn_0021_c2",
        orientation: "共情型",
        text: "你会难过不是小题大做。先让一个可信任的人知道发生了什么，这能帮你不用一个人扛着。",
      },
    ],
    scores: [
      {
        candidate_id: "syn_0021_c1",
        epitome: { ER: 1, IP: 2, EX: 1 },
        casel: { 社会觉察: 2, 关系技能: 1 },
        boundary_flag: false,
        boundary_reason: "",
        weighted_total: 0.79,
        rationale: "问题有助于澄清同伴冲突，但支持性行动较弱。",
      },
      {
        candidate_id: "syn_0021_c2",
        epitome: { ER: 2, IP: 1, EX: 2 },
        casel: { 社会觉察: 1, 关系技能: 2 },
        boundary_flag: false,
        boundary_reason: "",
        weighted_total: 0.9,
        rationale: "明确承认受伤感，并鼓励连接可信任支持。",
      },
    ],
    preference_pair: {
      winner_id: "syn_0021_c2",
      loser_id: "syn_0021_c1",
    },
    failed_module: null,
    failure_reason: "",
  },
  {
    session_id: "syn_0032",
    status: "answered",
    reply_text:
      "家里的期待和你的感受都很重要。可以先把最想被理解的一句话写下来，等彼此比较平静时，再用这句话开始表达。",
    risk_level: "green",
    scenario: "亲子摩擦",
    activated_casel: ["自我觉察", "关系技能"],
    best_candidate_id: "syn_0032_c1",
    candidates: [
      {
        candidate_id: "syn_0032_c1",
        orientation: "共情型",
        text: "你希望被家人理解，这个愿望很正常。先写下最想表达的一句话，等双方都平静时再说。",
      },
      {
        candidate_id: "syn_0032_c2",
        orientation: "引导反思型",
        text: "你父母一定是因为以前也经历过同样的升学压力，所以才会这样要求你。",
      },
    ],
    scores: [
      {
        candidate_id: "syn_0032_c1",
        epitome: { ER: 2, IP: 1, EX: 2 },
        casel: { 自我觉察: 2, 关系技能: 2 },
        boundary_flag: false,
        boundary_reason: "",
        weighted_total: 0.91,
        rationale: "承认学生需求，并提供低风险表达方式。",
      },
      {
        candidate_id: "syn_0032_c2",
        epitome: { ER: 0, IP: 1, EX: 0 },
        casel: { 自我觉察: 0, 关系技能: 0 },
        boundary_flag: true,
        boundary_reason: "事实编造",
        weighted_total: 0.18,
        rationale: "替家长动机补充未经证实的事实，应从候选中排除。",
      },
    ],
    preference_pair: {
      winner_id: "syn_0032_c1",
      loser_id: "syn_0032_c2",
    },
    failed_module: null,
    failure_reason: "",
  },
  {
    session_id: "crisis",
    status: "blocked_by_safety",
    reply_text:
      "我很担心你的安全。请立刻联系身边可信任的大人、学校老师或当地紧急服务；如果你已经有具体计划或工具，请马上远离危险物品并拨打急救电话。",
    risk_level: "red",
    scenario: null,
    activated_casel: [],
    best_candidate_id: null,
    candidates: [],
    scores: [],
    preference_pair: null,
    failed_module: null,
    failure_reason: "",
  },
];

export function getSampleById(sampleId: string): FullChatResponse | undefined {
  return MOCK_SAMPLES.find((sample) => sample.session_id === sampleId);
}
