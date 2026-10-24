import LoginCard from "@/components/LoginCard";

export default async function Page({ searchParams }: { searchParams: Promise<{ returnTo?: string }> }) {
  const { returnTo } = await searchParams;
  return <LoginCard kind="admin" returnTo={returnTo} />;
}
