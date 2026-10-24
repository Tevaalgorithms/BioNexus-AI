import { PageHeader } from "@/components/ui";
import { currentSession } from "@/lib/session";

export default async function Page() {
  const { user } = (await currentSession())!;
  return (
    <>
      <PageHeader title="Account" subtitle="Who you are signed in as and which projects you can open." />
      <dl className="card facts">
        <dt>User</dt><dd>{user.user_id}</dd><dt>Role</dt><dd>{user.role}</dd>
        <dt>Organisation</dt><dd>{user.tenant_id}</dd><dt>Projects</dt><dd>{user.projects.join(", ") || "none"}</dd>
      </dl>
      <p className="hint">Multi-factor authentication and password changes are managed on the secure sign-in page.</p>
    </>
  );
}
