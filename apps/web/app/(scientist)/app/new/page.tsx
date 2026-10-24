import NewAnalysisForm from "@/components/NewAnalysisForm";
import { PageHeader } from "@/components/ui";

export default function Page() {
  return (
    <>
      <PageHeader title="New analysis" subtitle="Choose any disease and up to five genes. The agent team gathers and checks the published evidence; you stay in control of what is accepted." />
      <NewAnalysisForm />
    </>
  );
}
