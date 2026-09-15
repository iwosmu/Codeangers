export interface ExportInput {
  repository: string; export_id: string; title: string; summary: string;
  members: { id: string; login: string }[];
  tasks: { id: number; title: string; description: string; hours: number; people: number; owners: string[]; prerequisites: number[] }[];
}
export interface ExportPreview { account: { login: string; repository: string; private: boolean }; issues: { key: string; title: string; body: string; assignees: string[] }[] }
export interface ExportResult { complete: boolean; issues: { key: string; number: number; url: string }[]; error: string | null }
