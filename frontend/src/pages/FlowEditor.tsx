import { useCallback, useEffect, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  type ReactFlowInstance,
  Handle,
  Position,
  BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  Button,
  Input,
  Select,
  InputNumber,
  Typography,
  Space,
  Divider,
  message,
  Form,
} from 'antd'
import {
  SaveOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography
const { TextArea } = Input

// ─── 节点类型定义 ───────────────────────────────────────────────────────────

interface NodeData {
  label?: string
  poi?: string
  text?: string
  seconds?: number
  command?: string
  onSelect?: (id: string) => void
}

function makeNodeCard(
  borderColor: string,
  icon: string,
  getLabel: (data: NodeData) => string
) {
  return function CustomNode({ id, data, selected }: { id: string; data: NodeData; selected: boolean }) {
    return (
      <div
        onClick={() => data.onSelect?.(id)}
        style={{
          background: 'rgba(8,24,42,0.92)',
          border: `2px solid ${selected ? '#ffffff' : borderColor}`,
          borderRadius: 10,
          padding: '10px 16px',
          minWidth: 140,
          maxWidth: 200,
          boxShadow: selected
            ? `0 0 16px ${borderColor}88`
            : `0 0 8px ${borderColor}33`,
          cursor: 'pointer',
          transition: 'all 0.15s',
          color: '#e2f4ff',
          fontSize: 13,
        }}
      >
        <Handle type="target" position={Position.Top} style={{ background: borderColor, border: 'none', width: 8, height: 8 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 16 }}>{icon}</span>
          <span style={{ color: borderColor, fontWeight: 600 }}>{getLabel(data)}</span>
        </div>
        <Handle type="source" position={Position.Bottom} style={{ background: borderColor, border: 'none', width: 8, height: 8 }} />
      </div>
    )
  }
}

const StartNode = ({ id, data, selected }: { id: string; data: NodeData; selected: boolean }) => (
  <div
    onClick={() => data.onSelect?.(id)}
    style={{
      background: 'rgba(8,24,42,0.92)',
      border: `2px solid ${selected ? '#fff' : '#39ff14'}`,
      borderRadius: 24,
      padding: '8px 20px',
      boxShadow: selected ? '0 0 16px #39ff1488' : '0 0 8px #39ff1433',
      cursor: 'pointer',
      color: '#39ff14',
      fontWeight: 700,
      fontSize: 14,
      letterSpacing: 1,
    }}
  >
    <Handle type="source" position={Position.Bottom} style={{ background: '#39ff14', border: 'none', width: 8, height: 8 }} />
    ▶ 开始
  </div>
)

const EndNode = ({ id, data, selected }: { id: string; data: NodeData; selected: boolean }) => (
  <div
    onClick={() => data.onSelect?.(id)}
    style={{
      background: 'rgba(8,24,42,0.92)',
      border: `2px solid ${selected ? '#fff' : '#ff1744'}`,
      borderRadius: 24,
      padding: '8px 20px',
      boxShadow: selected ? '0 0 16px #ff174488' : '0 0 8px #ff174433',
      cursor: 'pointer',
      color: '#ff1744',
      fontWeight: 700,
      fontSize: 14,
      letterSpacing: 1,
    }}
  >
    <Handle type="target" position={Position.Top} style={{ background: '#ff1744', border: 'none', width: 8, height: 8 }} />
    ⏹ 结束
  </div>
)

const NavigateNode = makeNodeCard('#00d4ff', '🧭', d => d.poi || '未设置POI')
const SpeakNode = makeNodeCard('#52c41a', '💬', d => d.text ? d.text.slice(0, 20) + (d.text.length > 20 ? '…' : '') : '未设置文本')
const DelayNode = makeNodeCard('#ff7c00', '⏱', d => d.seconds != null ? `${d.seconds}秒` : '未设置时长')
const CommandNode = makeNodeCard('#ff4d4f', '⚡', d => d.command || '未设置命令')
const NotifyNode = makeNodeCard('#722ed1', '🔔', d => d.text ? d.text.slice(0, 20) + (d.text.length > 20 ? '…' : '') : '未设置文本')

const nodeTypes: NodeTypes = {
  start: StartNode,
  end: EndNode,
  navigate: NavigateNode,
  speak: SpeakNode,
  delay: DelayNode,
  command: CommandNode,
  notify: NotifyNode,
}

// ─── 节点面板配置 ────────────────────────────────────────────────────────────

const nodeTypeConfig = [
  { type: 'start', label: '▶ 开始', color: '#39ff14', icon: '▶' },
  { type: 'end', label: '⏹ 结束', color: '#ff1744', icon: '⏹' },
  { type: 'navigate', label: '🧭 导航', color: '#00d4ff', icon: '🧭' },
  { type: 'speak', label: '💬 播报', color: '#52c41a', icon: '💬' },
  { type: 'delay', label: '⏱ 延时', color: '#ff7c00', icon: '⏱' },
  { type: 'command', label: '⚡ 命令', color: '#ff4d4f', icon: '⚡' },
  { type: 'notify', label: '🔔 通知', color: '#722ed1', icon: '🔔' },
]

// ─── 遍历 nodes/edges 转换成 steps ───────────────────────────────────────────

function buildSteps(nodes: Node[], edges: Edge[]) {
  // 找到 StartNode
  const startNode = nodes.find(n => n.type === 'start')
  if (!startNode) return []

  const edgeMap: Record<string, string> = {}
  for (const e of edges) {
    edgeMap[e.source] = e.target
  }

  const steps: { type: string; config: Record<string, unknown> }[] = []
  let current: string | undefined = startNode.id
  const visited = new Set<string>()

  while (current) {
    if (visited.has(current)) break
    visited.add(current)
    const node = nodes.find(n => n.id === current)
    if (!node) break
    if (node.type !== 'start' && node.type !== 'end') {
      const data = node.data as NodeData
      steps.push({
        type: node.type || 'unknown',
        config: {
          poi: data.poi,
          text: data.text,
          seconds: data.seconds,
          command: data.command,
        },
      })
    }
    current = edgeMap[current]
  }
  return steps
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────

let nodeIdCounter = 100

export default function FlowEditor() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [flowName, setFlowName] = useState('')
  const [flowId, setFlowId] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [flowList, setFlowList] = useState<{ id: string; name: string }[]>([])
  const [positions, setPositions] = useState<{ name: string; id?: string }[]>([])
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null)

  useEffect(() => {
    axios.get('/api/flows/').then(r => {
      const data = r.data
      if (Array.isArray(data)) setFlowList(data)
      else if (data?.items) setFlowList(data.items)
    }).catch(() => {})

    axios.get('/api/robot/positions').then(r => {
      const data = r.data
      if (Array.isArray(data)) setPositions(data)
      else if (data?.positions) setPositions(data.positions)
    }).catch(() => {})
  }, [])

  const handleSelect = useCallback((id: string) => {
    setSelectedNodeId(id)
  }, [])

  // 注入 onSelect 回调到每个节点的 data
  const nodesWithCallback = nodes.map(n => ({
    ...n,
    data: { ...n.data, onSelect: handleSelect },
  }))

  const onConnect = useCallback((params: Connection) => {
    setEdges(eds => addEdge({ ...params, style: { stroke: '#00d4ff', strokeWidth: 2 } }, eds))
  }, [setEdges])

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    const type = event.dataTransfer.getData('application/reactflow')
    if (!type || !reactFlowWrapper.current || !rfInstance) return

    const bounds = reactFlowWrapper.current.getBoundingClientRect()
    const position = rfInstance.project({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    })

    const newNode: Node = {
      id: `node_${++nodeIdCounter}`,
      type,
      position,
      data: {
        label: type,
        poi: '',
        text: '',
        seconds: 3,
        command: '',
        onSelect: handleSelect,
      },
    }
    setNodes(nds => [...nds, newNode])
  }, [rfInstance, handleSelect, setNodes])

  const updateSelectedNode = (patch: Partial<NodeData>) => {
    if (!selectedNodeId) return
    setNodes(nds =>
      nds.map(n =>
        n.id === selectedNodeId
          ? { ...n, data: { ...n.data, ...patch } }
          : n
      )
    )
  }

  const selectedNode = nodes.find(n => n.id === selectedNodeId)

  const handleSave = async () => {
    if (!flowName.trim()) {
      message.warning('请输入流程名称')
      return
    }
    setSaving(true)
    try {
      const steps = buildSteps(nodes, edges)
      const payload = {
        name: flowName,
        steps,
        nodes: nodes.map(n => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
        edges,
      }
      if (flowId) {
        await axios.put(`/api/flows/${flowId}`, payload)
      } else {
        const r = await axios.post('/api/flows/', payload)
        if (r.data?.id) setFlowId(r.data.id)
      }
      message.success('保存成功')
      // 刷新列表
      axios.get('/api/flows/').then(r => {
        const data = r.data
        if (Array.isArray(data)) setFlowList(data)
        else if (data?.items) setFlowList(data.items)
      }).catch(() => {})
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLoad = (id: string) => {
    axios.get(`/api/flows/${id}`).then(r => {
      const data = r.data
      setFlowId(id)
      setFlowName(data.name || '')
      if (Array.isArray(data.nodes)) {
        setNodes(data.nodes.map((n: Node) => ({ ...n, data: { ...n.data, onSelect: handleSelect } })))
      } else {
        setNodes([])
      }
      if (Array.isArray(data.edges)) {
        setEdges(data.edges)
      } else {
        setEdges([])
      }
      setSelectedNodeId(null)
    }).catch(() => message.error('加载流程失败'))
  }

  const handleRun = async () => {
    if (!flowId) {
      message.warning('请先保存流程')
      return
    }
    setRunning(true)
    try {
      await axios.post(`/api/flows/${flowId}/run`)
      message.success('流程已启动')
    } catch {
      message.error('启动失败')
    } finally {
      setRunning(false)
    }
  }

  const handleClear = () => {
    setNodes([])
    setEdges([])
    setFlowId(null)
    setFlowName('')
    setSelectedNodeId(null)
  }

  const addDefaultNode = (type: string) => {
    const newNode: Node = {
      id: `node_${++nodeIdCounter}`,
      type,
      position: { x: 200 + Math.random() * 100, y: 100 + Math.random() * 100 },
      data: {
        label: type,
        poi: '',
        text: '',
        seconds: 3,
        command: '',
        onSelect: handleSelect,
      },
    }
    setNodes(nds => [...nds, newNode])
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 104px)', gap: 0 }}>
      {/* 顶部工具栏 */}
      <div style={{
        background: 'rgba(8,24,42,0.9)',
        border: '1px solid rgba(0,212,255,0.15)',
        borderRadius: '12px 12px 0 0',
        padding: '10px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexShrink: 0,
      }}>
        <Text style={{ color: '#4a7fa0', fontSize: 12, whiteSpace: 'nowrap' }}>流程名</Text>
        <Input
          value={flowName}
          onChange={e => setFlowName(e.target.value)}
          placeholder="输入流程名称"
          style={{ width: 200, background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
        />
        <Button
          icon={<SaveOutlined />}
          loading={saving}
          onClick={handleSave}
          style={{ background: 'rgba(0,212,255,0.1)', borderColor: '#00d4ff', color: '#00d4ff' }}
        >
          保存
        </Button>
        <Select
          placeholder="加载已有流程"
          style={{ width: 180 }}
          onChange={handleLoad}
          value={flowId}
          options={flowList.map(f => ({ label: f.name, value: f.id }))}
        />
        <Button
          icon={<PlayCircleOutlined />}
          loading={running}
          onClick={handleRun}
          style={{ background: 'rgba(57,255,20,0.1)', borderColor: '#39ff14', color: '#39ff14' }}
        >
          执行
        </Button>
        <Button
          icon={<DeleteOutlined />}
          onClick={handleClear}
          danger
        >
          清空
        </Button>
      </div>

      {/* 三栏主体 */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', borderRadius: '0 0 12px 12px' }}>
        {/* 左侧节点面板 */}
        <div style={{
          width: 200,
          background: 'rgba(4,8,15,0.95)',
          border: '1px solid rgba(0,212,255,0.1)',
          borderTop: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: 12,
          overflowY: 'auto',
        }}>
          <Text style={{ fontSize: 12, color: '#4a7fa0', marginBottom: 4 }}>拖拽节点到画布</Text>
          {nodeTypeConfig.map(cfg => (
            <div
              key={cfg.type}
              draggable
              onDragStart={e => {
                e.dataTransfer.setData('application/reactflow', cfg.type)
                e.dataTransfer.effectAllowed = 'move'
              }}
              onClick={() => addDefaultNode(cfg.type)}
              style={{
                padding: '8px 12px',
                borderRadius: 8,
                background: 'rgba(8,24,42,0.8)',
                border: `1px solid ${cfg.color}44`,
                color: cfg.color,
                cursor: 'grab',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 13,
                fontWeight: 500,
                transition: 'all 0.15s',
                userSelect: 'none',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.background = `${cfg.color}18`
                ;(e.currentTarget as HTMLDivElement).style.borderColor = `${cfg.color}88`
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.background = 'rgba(8,24,42,0.8)'
                ;(e.currentTarget as HTMLDivElement).style.borderColor = `${cfg.color}44`
              }}
            >
              <PlusOutlined style={{ fontSize: 10, color: cfg.color }} />
              {cfg.label}
            </div>
          ))}
          <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '8px 0' }} />
          <Text style={{ fontSize: 11, color: '#4a7fa0', lineHeight: 1.5 }}>
            点击节点选中后可在右侧编辑属性
          </Text>
        </div>

        {/* 中间 ReactFlow 画布 */}
        <div ref={reactFlowWrapper} style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodesWithCallback}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onInit={setRfInstance}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode="Delete"
            style={{ background: '#080f1a' }}
            defaultEdgeOptions={{ style: { stroke: '#00d4ff', strokeWidth: 2 } }}
          >
            <Background color="#0d2a3e" gap={20} variant={BackgroundVariant.Dots} />
            <Controls />
            <MiniMap
              nodeColor={n => {
                const cfg = nodeTypeConfig.find(c => c.type === n.type)
                return cfg?.color || '#4a7fa0'
              }}
              maskColor="rgba(4,8,15,0.6)"
            />
          </ReactFlow>
          {nodes.length === 0 && (
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}>
              <Text style={{ color: '#4a7fa0', fontSize: 14 }}>
                从左侧拖拽节点到这里，或点击节点添加
              </Text>
            </div>
          )}
        </div>

        {/* 右侧属性面板 */}
        <div style={{
          width: 260,
          background: 'rgba(4,8,15,0.95)',
          border: '1px solid rgba(0,212,255,0.1)',
          borderTop: 'none',
          borderLeft: 'none',
          padding: 16,
          overflowY: 'auto',
        }}>
          {selectedNode ? (
            <>
              <Text style={{ fontSize: 13, fontWeight: 600, color: '#00d4ff', display: 'block', marginBottom: 12 }}>
                节点属性
              </Text>
              <Text style={{ fontSize: 11, color: '#4a7fa0', display: 'block', marginBottom: 12 }}>
                类型：{selectedNode.type} | ID：{selectedNode.id}
              </Text>
              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '8px 0' }} />

              {selectedNode.type === 'navigate' && (
                <Form layout="vertical" size="small">
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>目标POI</Text>}>
                    {positions.length > 0 ? (
                      <Select
                        value={(selectedNode.data as NodeData).poi}
                        onChange={val => updateSelectedNode({ poi: val })}
                        placeholder="选择导航点位"
                        options={positions.map(p => ({ label: p.name, value: p.name }))}
                        style={{ width: '100%' }}
                      />
                    ) : (
                      <Input
                        value={(selectedNode.data as NodeData).poi}
                        onChange={e => updateSelectedNode({ poi: e.target.value })}
                        placeholder="输入POI名称"
                        style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
                      />
                    )}
                  </Form.Item>
                </Form>
              )}

              {selectedNode.type === 'speak' && (
                <Form layout="vertical" size="small">
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>播报文本</Text>}>
                    <TextArea
                      value={(selectedNode.data as NodeData).text}
                      onChange={e => updateSelectedNode({ text: e.target.value })}
                      placeholder="输入播报内容"
                      rows={5}
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff', resize: 'vertical' }}
                    />
                  </Form.Item>
                </Form>
              )}

              {selectedNode.type === 'delay' && (
                <Form layout="vertical" size="small">
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>等待时长（秒）</Text>}>
                    <InputNumber
                      value={(selectedNode.data as NodeData).seconds}
                      onChange={val => updateSelectedNode({ seconds: val ?? 0 })}
                      min={1}
                      max={3600}
                      style={{ width: '100%', background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
                    />
                  </Form.Item>
                </Form>
              )}

              {selectedNode.type === 'command' && (
                <Form layout="vertical" size="small">
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>命令</Text>}>
                    <Input
                      value={(selectedNode.data as NodeData).command}
                      onChange={e => updateSelectedNode({ command: e.target.value })}
                      placeholder="输入命令"
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
                    />
                  </Form.Item>
                </Form>
              )}

              {selectedNode.type === 'notify' && (
                <Form layout="vertical" size="small">
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>通知内容</Text>}>
                    <TextArea
                      value={(selectedNode.data as NodeData).text}
                      onChange={e => updateSelectedNode({ text: e.target.value })}
                      placeholder="输入通知内容"
                      rows={5}
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff', resize: 'vertical' }}
                    />
                  </Form.Item>
                </Form>
              )}

              {(selectedNode.type === 'start' || selectedNode.type === 'end') && (
                <Text style={{ color: '#4a7fa0', fontSize: 12 }}>
                  起止节点无需配置属性
                </Text>
              )}

              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '16px 0' }} />
              <Button
                block
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={() => {
                  setNodes(nds => nds.filter(n => n.id !== selectedNodeId))
                  setEdges(eds => eds.filter(e => e.source !== selectedNodeId && e.target !== selectedNodeId))
                  setSelectedNodeId(null)
                }}
              >
                删除此节点
              </Button>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Text style={{ color: '#4a7fa0', fontSize: 12, lineHeight: 1.8 }}>
                点击画布中的节点<br />以编辑其属性
              </Text>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
