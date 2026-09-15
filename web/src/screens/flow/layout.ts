import type { FlowNode, FlowEdge } from '../../api/briefTypes'
export const NODE_WIDTH = 236, NODE_HEIGHT = 136, COLUMN_GAP = 76, ROW_GAP = 34, PADDING = 32, HEADER_HEIGHT = 46
export function layoutGraph(nodes: FlowNode[], edges: FlowEdge[], direction: 'horizontal' | 'vertical' = 'horizontal') {
  const degree = new Map(nodes.map(n => [n.id, 0]))
  const children = new Map(nodes.map(n => [n.id, [] as number[]]))
  const parents = new Map(nodes.map(n => [n.id, [] as number[]]))
  const depth = new Map(nodes.map(n => [n.id, 0]))
  for (const e of edges) {
    if (!degree.has(e.from) || !degree.has(e.to)) throw new Error('A dependency references a missing task.')
    degree.set(e.to, degree.get(e.to)! + 1); children.get(e.from)!.push(e.to); parents.get(e.to)!.push(e.from)
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
  const columns = Array.from({ length: Math.max(0, ...depth.values()) + 1 }, (_, column) => nodes.filter(n => depth.get(n.id) === column))
  const rowOf = new Map<number, number>()
  // Keep branches near their prerequisites; centre smaller columns to make joins legible.
  const maxRows = Math.max(1, ...columns.map(column => column.length))
  const positioned = columns.flatMap((columnNodes, column) => {
    const score = (node: FlowNode) => {
      const rows = parents.get(node.id)!.map(id => rowOf.get(id)).filter((row): row is number => row !== undefined)
      return rows.length ? rows.reduce((sum, row) => sum + row, 0) / rows.length : nodes.indexOf(node)
    }
    columnNodes.sort((a, b) => score(a) - score(b))
    return columnNodes.map((node, row) => {
      const centeredRow = row + (maxRows - columnNodes.length) / 2
      rowOf.set(node.id, centeredRow)
      return { ...node, x: PADDING + (direction === 'horizontal' ? column * (NODE_WIDTH + COLUMN_GAP) : centeredRow * (NODE_WIDTH + ROW_GAP)), y: PADDING + HEADER_HEIGHT + (direction === 'horizontal' ? centeredRow * (NODE_HEIGHT + ROW_GAP) : column * (NODE_HEIGHT + COLUMN_GAP)), column }
    })
  })
  if (direction === 'vertical') return { nodes: positioned, columns: columns.length, width: PADDING * 2 + maxRows * (NODE_WIDTH + ROW_GAP) - ROW_GAP, height: PADDING * 2 + HEADER_HEIGHT + columns.length * (NODE_HEIGHT + COLUMN_GAP) - COLUMN_GAP }
  return { nodes: positioned, columns: columns.length, width: PADDING * 2 + columns.length * (NODE_WIDTH + COLUMN_GAP) - COLUMN_GAP, height: PADDING * 2 + HEADER_HEIGHT + maxRows * (NODE_HEIGHT + ROW_GAP) - ROW_GAP }
}
