"use client";
import { useLoad } from "./useApi";

export interface ProjectRow { project_id: string; name: string; description: string; owner: boolean }

/** The caller's projects, always fresh from the API (the sign-in session is not the source). */
export function useProjects() {
  return useLoad<ProjectRow[]>("projects");
}
