import ReviewQueue from "@/components/runs/ReviewQueue";
import { Callout, PageHeader } from "@/components/ui/primitives";

export default function Page() {
  return (
    <>
      <PageHeader title="Review queue" subtitle="Draft reports waiting for a scientist. Nothing is marked approved until you approve a specific version." />
      <Callout tone="info" title="What reviewing involves">Open an investigation, check the evidence and limitations, exclude anything you do not trust (with a reason), then approve the exact version you reviewed.</Callout>
      <ReviewQueue />
    </>
  );
}
