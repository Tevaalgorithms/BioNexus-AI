export interface Preset { id: string; label: string; project: string; disease: string; targets: string; question: string; note: string }

/** Starting points. Any disease and genes can be typed; these just show the shape of a good question. */
export const PRESETS: Preset[] = [
  { id: "crohns", label: "Crohn's disease", project: "crohns", disease: "Crohn's disease", targets: "NOD2, IL23R",
    question: "Compare NOD2-related sensing and IL-23 signaling evidence.", note: "Included in the offline demo data." },
  { id: "covid", label: "COVID-19", project: "covid-19", disease: "COVID-19", targets: "ACE2, TMPRSS2",
    question: "Which genes involved in SARS-CoV-2 cell entry are linked to COVID-19, and how strong is the evidence?", note: "Needs live databases." },
  { id: "t2d", label: "Type 2 diabetes", project: "metabolic", disease: "Type 2 diabetes", targets: "TCF7L2, PPARG, KCNJ11",
    question: "How strong is the genetic and literature evidence for these genes in type 2 diabetes?", note: "Needs live databases." },
  { id: "alz", label: "Alzheimer's disease", project: "neurology", disease: "Alzheimer's disease", targets: "APOE, TREM2",
    question: "Compare the evidence linking APOE and TREM2 to Alzheimer's disease.", note: "Needs live databases." },
];

export const normaliseDisease = (text: string) => text.toLowerCase().replace(/['’]s\b/g, "").trim();

export function coveredByDemo(disease: string, demoDiseases: string[]): boolean {
  return demoDiseases.some((d) => normaliseDisease(d) === normaliseDisease(disease));
}
