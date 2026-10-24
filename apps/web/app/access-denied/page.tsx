const MESSAGES: Record<string, string> = {
  "wrong-role": "Your account does not have the role required for this sign-in. Use the other sign-in page if you have that role.",
  "no-account": "You do not have an active BioNexus account. Ask your administrator for an invitation.",
  "login-expired": "Your sign-in attempt expired. Please start again.",
  "state-mismatch": "The sign-in response could not be verified. Please start again.",
  "token-exchange": "Sign-in could not be completed. Please try again.",
};

export default async function Page({ searchParams }: { searchParams: Promise<{ reason?: string }> }) {
  const { reason = "" } = await searchParams;
  return (
    <main className="login" id="content">
      <h1>Access denied</h1>
      <div className="notice bad" role="alert">{MESSAGES[reason] ?? "You are not permitted to view this page."}</div>
      <p><a href="/login">Scientist sign-in</a> · <a href="/admin/login">Administrator sign-in</a></p>
    </main>
  );
}
