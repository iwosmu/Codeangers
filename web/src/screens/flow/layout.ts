import type { FlowNode, FlowEdge } from '../../api/briefTypes'
export const NODE_WIDTH = 244, NODE_HEIGHT = 140, COLUMN_GAP = 90, ROW_GAP = 36, PADDING = 28
export function layoutGraph(nodes: FlowNode[], edges: FlowEdge[]) {
  const degree = new Map(nodes.map(n => [n.id, 0]))
  const children = new Map(nodes.map(n => [n.id, [] as number[]]))
  const depth = new Map(nodes.map(n => [n.id, 0]))
  for (const e of edges) {
    if (!degree.has(e.from) || !degree.has(e.to)) throw new Error('A dependency references a missing task.')
    degree.set(e.to, degree.get(e.to)! + 1); children.get(e.from)!.push(e.to)
  }
  const queue = nodes.filter(n => degree.get(n.id) === 0).map(n => n.id)
  for (let i = 0; i < queue.length; i++) {
    const id = queue[i]
    for (const child of children.get(id)!) {
      depth.set(child, Math.max(depth.get(child)!, depth.get(id)! + 1))
      degree.set(child, degree.get(child)! - 1)
      if (degree.get(child) === 0) queue.push(child)
    }
  }
  if (queue.length !== nodes.length) throw new Error('The task graph contains a dependency cycle.')
  const rows = new Map<number, number>()
  const positioned = nodes.map(node => {
    const column = depth.get(node.id)!, row = rows.get(column) ?? 0
    rows.set(column, row + 1)
    return { ...node, x: PADDING + column * (NODE_WIDTH + COLUMN_GAP), y: PADDING + row * (NODE_HEIGHT + ROW_GAP), column }
  })
  return { nodes: positioned, width: PADDING * 2 + (Math.max(0, ...depth.values()) + 1) * (NODE_WIDTH + COLUMN_GAP) - COLUMN_GAP, height: PADDING * 2 + Math.max(1, ...rows.values()) * (NODE_HEIGHT + ROW_GAP) - ROW_GAP }
}
