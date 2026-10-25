import NewAnalysisForm from "@/components/runs/NewAnalysisForm";
import { PageHeader } from "@/components/ui/primitives";

export default function Page() {
  return (
    <>
      <PageHeader title="New analysis" subtitle="Choose any disease and up to five genes. The team of specialists and AI reviewers gathers and checks the published evidence; you stay in control of what is accepted." />
      <NewAnalysisForm />
    </>
  );
}
