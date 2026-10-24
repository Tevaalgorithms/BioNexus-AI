"use client";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { ApiError, call } from "../../hooks/useApi";

export interface CreateProjectHandle { open: (suggestedName?: string) => void }

/** A small form in a dialog: name and (optional) description. Returns the new project id. */
const CreateProjectDialog = forwardRef<CreateProjectHandle, { onCreated: (projectId: string) => void }>(function CreateProjectDialog({ onCreated }, ref) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useImperativeHandle(ref, () => ({
    open(suggested = "") { setName(suggested); setDescription(""); setError(null); dialog.current?.showModal(); },
  }));

  async function create() {
    setBusy(true); setError(null);
    try {
      const project = await call<{ project_id: string }>("POST", "projects", { name, description });
      dialog.current?.close();
      onCreated(project.project_id);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not create the project."); }
    finally { setBusy(false); }
  }

  return (
    <dialog ref={dialog} aria-labelledby="proj-h">
      <h2 id="proj-h">Create a project space</h2>
      <p className="hint">A project is a private workspace for one study or disease. Only you and the colleagues you invite can open its investigations, and reviewed evidence is reused only inside it.</p>
      <label htmlFor="proj-name">Project name</label>
      <input id="proj-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="For example: COVID-19 host genes" aria-invalid={!!error} />
      <label htmlFor="proj-desc">Description (optional)</label>
      <input id="proj-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this project is for" />
      {error && <p className="field-error" role="alert">{error}</p>}
      <div className="row" style={{ marginTop: 16 }}>
        <button onClick={create} disabled={busy || name.trim().length < 3}>{busy ? "Creating…" : "Create project"}</button>
        <button className="secondary" onClick={() => dialog.current?.close()}>Cancel</button>
      </div>
    </dialog>
  );
});

export default CreateProjectDialog;
