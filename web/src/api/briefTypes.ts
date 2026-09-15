export interface Setup { name: string; context: string; constraints: string }
export interface MemberInput { id: string; label: string; text: string; file?: File }
export interface Claim { text: string; evidence_ids: string[] }
export interface Evidence { id: string; source_id: string; source_part: string; location: string; quote: string }
export interface MemberBrief {
  id: string; cv_name: Claim; evidence: Evidence[]; roles: Claim[]; strengths: Claim[];
  gaps: { area: string; relevance: string }[]; stack: Claim[]; experience: Claim; working_style: Claim[];
  coverage: { area: string; level: 'strong' | 'some' | 'none'; evidence_ids: string[] }[];
}
export interface TeamBrief { members: MemberBrief[]; open_questions: string[] }
export interface Statement { text: string; source_ids: string[] }
export interface ProjectBrief {
  one_liner: Statement; problem: Statement; target_user: Statement; vision: Statement; value_proposition: Statement;
  must_have: Statement[]; nice_to_have: Statement[]; constraints: Statement[]; success_criteria: Statement[];
  impact: Statement; open_questions: string[]; source_notes: { source_id: string; contribution: string }[];
  contradictions: Statement[];
}
export interface DocumentResult<T> {
  filename: 'team.md' | 'project.md'; markdown: string; schema_version: string; structured: T;
  sources: { id: string; label: string; member_id?: string | null }[]; warnings: string[]; ms: number;
}
export interface BriefInputs { setup: Setup; members: MemberInput[]; projectText: string; projectFiles: File[] }
export interface Output<T> { document?: DocumentResult<T>; busy: boolean; error?: string }
export interface FlowNode { id: number; label: string; title: string; group: string; estimated_time_hours: number; people_needed: number }
export interface FlowEdge { from: number; to: number }
export interface TaskGraphResult {
  graph: { nodes: FlowNode[]; edges: FlowEdge[] };
  tasks: { id: number; name: string; description: string; prerequisites: number[]; estimated_time_hours: number; people_needed: number; group?: string }[];
  team_size: number; rounds: number; ms: number;
  validation: { ok: boolean; summary: string; errors: string[]; warnings: string[]; makespan_hours: number; total_person_hours: number; idle_person_hours: number; idle_fraction: number; idle_intervals: { start: number; end: number; idle_people: number }[] };
}
