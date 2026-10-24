import type { IconName } from "@/components/ui/icons";

/** Plain-language descriptions shown across the UI. One place, so wording stays consistent. */

export interface StageInfo { id: string; label: string; icon: IconName; plain: string }

export const STAGES: StageInfo[] = [
  { id: "scope", label: "Check request", icon: "check", plain: "Confirms the question is complete and within pilot limits." },
  { id: "recall_memory", label: "Recall reviewed work", icon: "book", plain: "Reuses evidence your team already reviewed in this project (never unreviewed work)." },
  { id: "specialists", label: "Gather evidence", icon: "search", plain: "Specialist agents query genetics, literature, pathway and trial sources in parallel." },
  { id: "critique", label: "Challenge & repair", icon: "scale", plain: "A critic looks for contradictions and missing support and asks specialists to fix what it can." },
  { id: "retrieve", label: "Rank & connect", icon: "graph", plain: "Ranks the accepted evidence for your question and maps how it connects." },
  { id: "synthesize", label: "Write findings", icon: "pen", plain: "Drafts claims that cite only accepted evidence. No causal or treatment statements." },
  { id: "finalize", label: "Build report", icon: "doc", plain: "Assembles the draft report and a reproducibility record." },
  { id: "complete", label: "Your approval", icon: "shield", plain: "Waits for a scientist to review and approve one exact report version." },
];

export interface AgentInfo { id: string; name: string; icon: IconName; role: string; sources: string[]; sourcesText: string }

export const AGENTS: AgentInfo[] = [
  { id: "supervisor", name: "Supervisor", icon: "compass", role: "Plans the work and hands tasks to the specialists. Never decides what the evidence says.", sources: [], sourcesText: "Coordinates" },
  { id: "genetics", name: "Genetics", icon: "dna", role: "Finds genetic associations between your genes and the disease, keeping ancestry and direction of effect.", sources: ["open_targets", "gwas"], sourcesText: "Open Targets, GWAS Catalog" },
  { id: "literature", name: "Literature", icon: "book", role: "Reads published studies and reports only findings backed by a passage you can open.", sources: ["europe_pmc"], sourcesText: "Europe PMC" },
  { id: "pathways", name: "Pathways", icon: "path", role: "Adds biological context: curated pathways and phenotype data. Annotation is not proof of mechanism.", sources: ["reactome", "monarch"], sourcesText: "Reactome, Monarch" },
  { id: "clinical", name: "Clinical context", icon: "flask", role: "Notes registered clinical trials and their status. Registration is not evidence a treatment works.", sources: ["clinicaltrials"], sourcesText: "ClinicalTrials.gov" },
  { id: "critic", name: "Evidence critic", icon: "scale", role: "Looks for contradictions, missing passages and over-reliance on one study, then asks for repairs.", sources: [], sourcesText: "Reviews all evidence" },
  { id: "synthesizer", name: "Synthesizer", icon: "pen", role: "Writes the draft using only evidence that was accepted; blocks causal and treatment language.", sources: [], sourcesText: "Writes the report" },
];

export const SOURCE_LABELS: Record<string, string> = {
  open_targets: "Open Targets", gwas: "GWAS Catalog", europe_pmc: "Europe PMC", reactome: "Reactome", monarch: "Monarch", clinicaltrials: "ClinicalTrials.gov",
};

export const GLOSSARY: { term: string; meaning: string }[] = [
  { term: "Study family", meaning: "One underlying study. The same paper can appear in several databases; BioNexus counts it once so repeats are not mistaken for independent confirmation." },
  { term: "Supporting / opposing / no direction", meaning: "Whether a study's finding points toward an association with the disease, away from it, or does not state a direction (for example a trial registration)." },
  { term: "Accepted evidence", meaning: "Evidence that is licensed for use, available before your cutoff date, and backed by a passage. Only accepted evidence can appear in a claim." },
  { term: "Evidence cutoff", meaning: "Only evidence available on or before this date is used, so results can be reproduced and compared fairly." },
  { term: "Draft vs approved", meaning: "Every report starts as a draft. It becomes approved only when a scientist approves that exact version." },
  { term: "Handoff", meaning: "One agent asking another for help, for example genetics asking pathways for context. Every handoff is recorded." },
  { term: "Incomplete", meaning: "The run stopped early (for example a budget limit or a source outage). What was found is shown; nothing is invented to fill the gap." },
  { term: "Configuration release", meaning: "The exact set of models, skills and prompts a run used. It is fixed when the run starts, so later admin changes never alter a run in progress." },
  { term: "Association score", meaning: "A ranking aid from a database. It is not a probability that a mechanism is true." },
];

export function statusSentence(status: string, reason?: string | null): string {
  const map: Record<string, string> = {
    queued: "Waiting for a worker to pick this up.",
    running: "The agent team is gathering and checking evidence.",
    waiting_for_review: "The draft is ready. Please review the evidence and approve a version, or exclude evidence and regenerate.",
    completed: "A scientist approved this report. It is final; later changes create a new version.",
    incomplete: `The run stopped early${reason ? `: ${reason}` : ""}. Partial results are shown and nothing was invented to fill gaps.`,
    failed: `Something went wrong${reason ? `: ${reason}` : ""}. No findings should be relied on.`,
    cancelled: "This analysis was cancelled. Partial results are kept for reference.",
    superseded: "A newer analysis replaced this one.",
  };
  return map[status] ?? status;
}

export const STANCE_LABEL: Record<string, string> = { supports: "Supports", opposes: "Opposes", unknown: "No stated direction" };
export const STANCE_HELP: Record<string, string> = {
  supports: "The study's finding points toward an association with the disease.",
  opposes: "The study found no association or an opposite effect.",
  unknown: "The source does not say which way the finding points (for example a trial registration or a pathway annotation).",
};

export const SKILL_FOR: Record<string, string> = {
  supervisor: "investigation.plan", genetics: "genetics.assess", literature: "literature.assess",
  pathways: "mechanism.context", clinical: "trials.context", critic: "evidence.critique", synthesizer: "report.synthesize",
};
