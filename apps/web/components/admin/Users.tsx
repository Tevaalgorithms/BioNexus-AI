"use client";
import { useState } from "react";
import { ApiError, call, useLoad } from "../../hooks/useApi";
import { Empty } from "../ui/Async";
import { AdminPage } from "./AdminPage";
import type { UserRow } from "@/lib/types";

const ROLES = [
  { value: "scientist", label: "Scientist", note: "Runs investigations in the projects they are added to." },
  { value: "platform_admin", label: "Platform admin", note: "Manages models, users and settings. Sees no project data unless added to a project." },
];

type Notice = { tone: "ok" | "bad"; text: string } | null;

/** Invite people by email and switch accounts off. Cognito sends the temporary password, never BioNexus. */
export function Users() {
  const me = useLoad<{ user_id: string }>("me").data?.user_id;
  return (
    <AdminPage<UserRow[]> path="admin/users" title="Users" subtitle="Invite scientists and administrators by email. They receive a temporary password from Amazon Cognito and choose their own at first sign-in.">
      {(rows, reload) => <UserTable rows={rows} me={me} reload={reload} />}
    </AdminPage>
  );
}

function UserTable({ rows, me, reload }: { rows: UserRow[]; me?: string; reload: () => void }) {
  const [notice, setNotice] = useState<Notice>(null);
  const run = async (action: () => Promise<string>) => {
    try { setNotice({ tone: "ok", text: await action() }); reload(); }
    catch (e) { setNotice({ tone: "bad", text: e instanceof ApiError ? e.message : "Request failed" }); }
  };
  return (
    <>
      {notice && <div className={`notice ${notice.tone}`} role={notice.tone === "bad" ? "alert" : "status"}>{notice.text}</div>}
      <InviteForm onInvite={(email, role) => run(() => invite(email, role))} />
      {rows.length === 0 ? <Empty>No users yet.</Empty> : (
        <div className="table-wrap"><table>
          <caption className="sr-only">People with access</caption>
          <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Access</th></tr></thead>
          <tbody>{rows.map((u) => (
            <tr key={u.user_id}>
              <th scope="row">{u.user_id}{u.user_id === me && " (you)"}</th>
              <td>{ROLES.find((r) => r.value === u.role)?.label ?? u.role}</td>
              <td>{u.active ? "Active" : "Disabled"}</td>
              <td>{u.active && u.user_id !== me && <DisableButton user={u.user_id} onDisable={() => run(() => disable(u.user_id))} />}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </>
  );
}

function InviteForm({ onInvite }: { onInvite: (email: string, role: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("scientist");
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    await onInvite(email, role);
    setBusy(false);
    setEmail("");
  };
  return (
    <form onSubmit={submit} className="card" aria-labelledby="invite-h">
      <h2 id="invite-h">Invite someone</h2>
      <label htmlFor="invite-email">Email address</label>
      <input id="invite-email" type="email" required autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />
      <label htmlFor="invite-role">Role</label>
      <select id="invite-role" value={role} onChange={(e) => setRole(e.target.value)}>
        {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
      </select>
      <p className="hint">{ROLES.find((r) => r.value === role)?.note}</p>
      <p className="hint">Cognito emails the temporary password. If the address already has a sign-in, no new email is sent.</p>
      <button type="submit" disabled={busy || !email.trim()}>{busy ? "Sending…" : "Send invitation"}</button>
    </form>
  );
}

/** Two clicks, so a mis-click cannot remove someone's access. */
function DisableButton({ user, onDisable }: { user: string; onDisable: () => void }) {
  const [sure, setSure] = useState(false);
  if (!sure) return <button className="secondary" onClick={() => setSure(true)} aria-label={`Disable ${user}`}>Disable</button>;
  return (
    <span className="row">
      <button onClick={onDisable} aria-label={`Confirm disabling ${user}`}>Confirm disable</button>
      <button className="secondary" onClick={() => setSure(false)}>Cancel</button>
    </span>
  );
}

async function invite(email: string, role: string): Promise<string> {
  const r = await call<{ user_id: string; emailed: boolean; existing: boolean }>("POST", "admin/users", { email, role });
  const as = role.replace("_", " ");
  if (r.emailed) return `Invitation sent to ${r.user_id}. Cognito has emailed a temporary password.`;
  if (r.existing) return `${r.user_id} already had a sign-in, so no new email was sent. They now have access as ${as}.`;
  return `Access recorded for ${r.user_id} as ${as}. No email was sent: this environment is not connected to Cognito.`;
}

async function disable(userId: string): Promise<string> {
  const r = await call<{ user_id: string; sign_in_disabled: boolean }>("POST", "admin/users/disable", { user_id: userId });
  return r.sign_in_disabled
    ? `${r.user_id} is disabled and signed out everywhere.`
    : `${r.user_id} can no longer use BioNexus. Their sign-in account could not be switched off automatically; disable it in Cognito too.`;
}
