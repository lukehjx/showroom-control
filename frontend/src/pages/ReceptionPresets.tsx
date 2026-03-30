import { useCallback, useEffect, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
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
  InputNumber,
  Select,
  Typography,
  Space,
  Divider,
  message,
  Form,
} from 'antd'
import {
  SaveOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography
const { TextArea } = Input

// ─── 颜色配置 ─────────────────────────────────────────────────────────────────

const stepColorMap: Record<string, string> = {
  start: '#39ff14',
  end: '#ff1744',
  navigate: '#00d4ff',
  speak: '#52c41a',
  wait: '#ff7c00',
  command: '#ff4d4f',
  notify: '#722ed1',
}

const stepIconMap: Record<string, string> = {
  start: '▶',
  end: '⏹',
  navigate: '🧭',
  speak: '💬',
  wait: '⏱',
  command: '⚡',
  notify: '🔔',
}

const stepLabelMap: Record<string, string> = {
  start: '开始',
  end: '结束',
  navigate: '导航',
  speak: '播报',
  wait: '等待',
  command: '命令',
  notify: '通知',
}

// ─── 节点数据接口 ─────────────────────────────────────────────────────────────

interface StepNodeData {
  stepType: string
  poi?: string
  text?: string
  seconds?: number
  command?: string
  onSelect?: (id: string) => void
}

// ─── 通用节点渲染 ─────────────────────────────────────────────────────────────

function StepNode({ id, data, selected }: { id: string; data: StepNodeData; selected: boolean }) {
  const color = stepColorMap[data.stepType] || '#8ab4cc'
  const icon = stepIconMap[data.stepType] || '▪'
  const isTerminal = data.stepType === 'start' || data.stepType === 'end'

  const getSubLabel = () => {
    switch (data.stepType) {
      case 'navigate': return data.poi || '未设置POI'
      case 'speak': return data.text ? data.text.slice(0, 22) + (data.text.length > 22 ? '…' : '') : '未设置文本'
      case 'wait': return data.seconds != null ? `${data.seconds}秒` : '未设置时长'
      case 'command': return data.command || '未设置命令'
      case 'notify': return data.text ? data.text.slice(0, 22) + (data.text.length > 22 ? '…' : '') : '未设置内容'
      default: return ''
    }
  }

  if (isTerminal) {
    return (
      <div
        onClick={() => data.onSelect?.(id)}
        style={{
          background: 'rgba(8,24,42,0.92)',
          border: `2px solid ${selected ? '#ffffff' : color}`,
          borderRadius: 24,
          padding: '8px 20px',
          boxShadow: selected ? `0 0 16px ${color}88` : `0 0 8px ${color}33`,
          cursor: 'pointer',
          color,
          fontWeight: 700,
          fontSize: 14,
          letterSpacing: 1,
          textAlign: 'center',
          minWidth: 100,
        }}
      >
        {data.stepType === 'start' && (
          <Handle type="source" position={Position.Bottom} style={{ background: color, border: 'none', width: 8, height: 8 }} />
        )}
        {data.stepType === 'end' && (
          <Handle type="target" position={Position.Top} style={{ background: color, border: 'none', width: 8, height: 8 }} />
        )}
        {icon} {stepLabelMap[data.stepType]}
      </div>
    )
  }

  return (
    <div
      onClick={() => data.onSelect?.(id)}
      style={{
        background: 'rgba(8,24,42,0.92)',
        border: `2px solid ${selected ? '#ffffff' : color}`,
        borderRadius: 10,
        padding: '10px 16px',
        minWidth: 150,
        maxWidth: 210,
        boxShadow: selected ? `0 0 16px ${color}88` : `0 0 8px ${color}33`,
        cursor: 'pointer',
        color: '#e2f4ff',
        fontSize: 12,
        transition: 'all 0.15s',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: color, border: 'none', width: 8, height: 8 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ color, fontWeight: 600, fontSize: 13 }}>{stepLabelMap[data.stepType]}</span>
      </div>
      {getSubLabel() && (
        <div style={{ color: '#8ab4cc', fontSize: 11, marginTop: 4 }}>{getSubLabel()}</div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: color, border: 'none', width: 8, height: 8 }} />
    </div>
  )
}

const nodeTypes: NodeTypes = { step: StepNode }

// ─── 可用步骤类型 ──────────────────────────────────────────────────────────────

const availableStepTypes = [
  { stepType: 'navigate', label: '🧭 导航' },
  { stepType: 'speak', label: '💬 播报' },
  { stepType: 'wait', label: '⏱ 等待' },
  { stepType: 'command', label: '⚡ 命令' },
  { stepType: 'notify', label: '🔔 通知' },
]

let nodeIdCounter = 300

function makeInitialNodes(): Node[] {
  return [
    {
      id: 'preset_start',
      type: 'step',
      position: { x: 200, y: 40 },
      data: { stepType: 'start' },
    },
    {
      id: 'preset_end',
      type: 'step',
      position: { x: 200, y: 320 },
      data: { stepType: 'end' },
    },
  ]
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────

export default function ReceptionPresets() {
  const [nodes, setNodes, onNodesChange] = useNodesState(makeInitialNodes())
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [presetName, setPresetName] = useState('')
  const [presetId, setPresetId] = useState<string | null>(null)
  const [presetList, setPresetList] = useState<{ id: string; name: string }[]>([])
  const [positions, setPositions] = useState<{ name: string }[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null)

  useEffect(() => {
    axios.get('/api/presets/').then(r => {
      const d = r.data
      if (Array.isArray(d)) setPresetList(d)
      else if (d?.items) setPresetList(d.items)
    }).catch(() => {})
    axios.get('/api/robot/positions').then(r => {
      const d = r.data
      if (Array.isArray(d)) setPositions(d)
      else if (d?.positions) setPositions(d.positions)
    }).catch(() => {})
  }, [])

  const handleSelect = useCallback((id: string) => setSelectedId(id), [])

  const nodesWithCallback = nodes.map(n => ({
    ...n,
    data: { ...n.data, onSelect: handleSelect },
  }))

  const onConnect = useCallback((params: Connection) => {
    setEdges(eds => addEdge({ ...params, style: { stroke: '#00d4ff', strokeWidth: 2 } }, eds))
  }, [setEdges])

  const addStep = (stepType: string) => {
    const count = nodes.filter(n => (n.data as StepNodeData).stepType !== 'start' && (n.data as StepNodeData).stepType !== 'end').length
    const newNode: Node = {
      id: `step_${++nodeIdCounter}`,
      type: 'step',
      position: { x: 200, y: 120 + count * 110 },
      data: {
        stepType,
        poi: '',
        text: '',
        seconds: 3,
        command: '',
        onSelect: handleSelect,
      },
    }
    setNodes(nds => {
      // 插入到 end 节点前面
      const endIdx = nds.findIndex(n => (n.data as StepNodeData).stepType === 'end')
      if (endIdx > 0) {
        const prev = nds[endIdx - 1]
        const endNode = nds[endIdx]
        // 删除 prev->end 的边，加 prev->new, new->end
        setEdges(eds => {
          const filtered = eds.filter(e => !(e.source === prev.id && e.target === endNode.id))
          return [
            ...filtered,
            { id: `e_${prev.id}_${newNode.id}`, source: prev.id, target: newNode.id, style: { stroke: '#00d4ff', strokeWidth: 2 } },
            { id: `e_${newNode.id}_${endNode.id}`, source: newNode.id, target: endNode.id, style: { stroke: '#00d4ff', strokeWidth: 2 } },
          ]
        })
      }
      const result = [...nds]
      if (endIdx >= 0) result.splice(endIdx, 0, newNode)
      else result.push(newNode)
      return result
    })
  }

  const updateSelected = (patch: Partial<StepNodeData>) => {
    if (!selectedId) return
    setNodes(nds => nds.map(n => n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n))
  }

  const selectedNode = nodes.find(n => n.id === selectedId)
  const stepType = (selectedNode?.data as StepNodeData)?.stepType

  const buildSteps = () => {
    return nodes
      .filter(n => {
        const t = (n.data as StepNodeData).stepType
        return t !== 'start' && t !== 'end'
      })
      .map(n => {
        const d = n.data as StepNodeData
        return {
          type: d.stepType,
          config: { poi: d.poi, text: d.text, seconds: d.seconds, command: d.command },
        }
      })
  }

  const handleSave = async () => {
    if (!presetName.trim()) { message.warning('请输入套餐名称'); return }
    setSaving(true)
    try {
      const steps = buildSteps()
      const payload = { name: presetName, steps, nodes, edges }
      if (presetId) {
        await axios.put(`/api/presets/${presetId}`, payload)
      } else {
        const r = await axios.post('/api/presets/', payload)
        if (r.data?.id) setPresetId(r.data.id)
      }
      message.success('套餐保存成功')
      axios.get('/api/presets/').then(r => {
        const d = r.data
        if (Array.isArray(d)) setPresetList(d)
        else if (d?.items) setPresetList(d.items)
      }).catch(() => {})
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLoad = (id: string) => {
    axios.get(`/api/presets/${id}`).then(r => {
      const d = r.data
      setPresetId(id)
      setPresetName(d.name || '')
      if (Array.isArray(d.nodes)) {
        setNodes(d.nodes.map((n: Node) => ({ ...n, data: { ...n.data, onSelect: handleSelect } })))
      } else {
        setNodes(makeInitialNodes())
      }
      if (Array.isArray(d.edges)) setEdges(d.edges)
      else setEdges([])
      setSelectedId(null)
    }).catch(() => message.error('加载失败'))
  }

  const handleRun = async () => {
    if (!presetId) { message.warning('请先保存套餐'); return }
    setRunning(true)
    try {
      await axios.post(`/api/presets/${presetId}/run`)
      message.success('接待套餐已启动')
    } catch {
      message.error('启动失败')
    } finally {
      setRunning(false)
    }
  }

  const handleNew = () => {
    setPresetId(null)
    setPresetName('')
    setNodes(makeInitialNodes())
    setEdges([])
    setSelectedId(null)
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
        flexWrap: 'wrap',
      }}>
        <Input
          value={presetName}
          onChange={e => setPresetName(e.target.value)}
          placeholder="套餐名称"
          style={{ width: 180, background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
        />
        <Button
          icon={<PlusOutlined />}
          onClick={handleNew}
          style={{ borderColor: 'rgba(0,212,255,0.3)', color: '#8ab4cc' }}
        >
          新建
        </Button>
        {availableStepTypes.map(s => (
          <Button
            key={s.stepType}
            size="small"
            onClick={() => addStep(s.stepType)}
            style={{
              background: `${stepColorMap[s.stepType]}18`,
              borderColor: `${stepColorMap[s.stepType]}44`,
              color: stepColorMap[s.stepType],
              fontSize: 12,
            }}
          >
            {s.label}
          </Button>
        ))}
        <Button
          icon={<SaveOutlined />}
          loading={saving}
          onClick={handleSave}
          style={{ background: 'rgba(0,212,255,0.1)', borderColor: '#00d4ff', color: '#00d4ff' }}
        >
          保存
        </Button>
        <Select
          placeholder="加载已有套餐"
          style={{ width: 180 }}
          onChange={handleLoad}
          value={presetId}
          options={presetList.map(p => ({ label: p.name, value: p.id }))}
        />
        <Button
          icon={<PlayCircleOutlined />}
          loading={running}
          onClick={handleRun}
          style={{ background: 'rgba(57,255,20,0.1)', borderColor: '#39ff14', color: '#39ff14' }}
        >
          启动
        </Button>
      </div>

      {/* 画布 + 属性面板 */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', borderRadius: '0 0 12px 12px' }}>
        {/* ReactFlow 画布 */}
        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodesWithCallback}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setRfInstance}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode="Delete"
            style={{ background: '#080f1a' }}
            defaultEdgeOptions={{ style: { stroke: '#00d4ff', strokeWidth: 2 } }}
          >
            <Background color="#0d2a3e" gap={20} variant={BackgroundVariant.Dots} />
            <Controls />
          </ReactFlow>
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
              <Text style={{ fontSize: 13, fontWeight: 600, color: stepColorMap[stepType || ''] || '#00d4ff', display: 'block', marginBottom: 12 }}>
                {stepIconMap[stepType || '']} {stepLabelMap[stepType || ''] || '步骤'} 属性
              </Text>
              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '8px 0' }} />
              <Form layout="vertical" size="small">
                {stepType === 'navigate' && (
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>目标POI</Text>}>
                    {positions.length > 0 ? (
                      <Select
                        value={(selectedNode.data as StepNodeData).poi}
                        onChange={val => updateSelected({ poi: val })}
                        placeholder="选择导航点位"
                        options={positions.map(p => ({ label: p.name, value: p.name }))}
                        style={{ width: '100%' }}
                      />
                    ) : (
                      <Input
                        value={(selectedNode.data as StepNodeData).poi}
                        onChange={e => updateSelected({ poi: e.target.value })}
                        placeholder="输入POI名称"
                        style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
                      />
                    )}
                  </Form.Item>
                )}
                {stepType === 'speak' && (
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>播报文本</Text>}>
                    <TextArea
                      value={(selectedNode.data as StepNodeData).text}
                      onChange={e => updateSelected({ text: e.target.value })}
                      placeholder="输入播报内容"
                      rows={5}
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff', resize: 'vertical' }}
                    />
                  </Form.Item>
                )}
                {stepType === 'wait' && (
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>等待时长（秒）</Text>}>
                    <InputNumber
                      value={(selectedNode.data as StepNodeData).seconds}
                      onChange={val => updateSelected({ seconds: val ?? 0 })}
                      min={1}
                      max={3600}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                )}
                {stepType === 'command' && (
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>命令</Text>}>
                    <Input
                      value={(selectedNode.data as StepNodeData).command}
                      onChange={e => updateSelected({ command: e.target.value })}
                      placeholder="输入命令"
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
                    />
                  </Form.Item>
                )}
                {stepType === 'notify' && (
                  <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>通知内容</Text>}>
                    <TextArea
                      value={(selectedNode.data as StepNodeData).text}
                      onChange={e => updateSelected({ text: e.target.value })}
                      placeholder="输入通知内容"
                      rows={5}
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff', resize: 'vertical' }}
                    />
                  </Form.Item>
                )}
                {(stepType === 'start' || stepType === 'end') && (
                  <Text style={{ color: '#4a7fa0', fontSize: 12 }}>起止节点无需配置</Text>
                )}
              </Form>

              {stepType !== 'start' && stepType !== 'end' && (
                <>
                  <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
                  <Button
                    block danger size="small" icon={<DeleteOutlined />}
                    onClick={() => {
                      setNodes(nds => nds.filter(n => n.id !== selectedId))
                      setEdges(eds => eds.filter(e => e.source !== selectedId && e.target !== selectedId))
                      setSelectedId(null)
                    }}
                  >
                    删除此步骤
                  </Button>
                </>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Text style={{ color: '#4a7fa0', fontSize: 12, lineHeight: 1.8 }}>
                点击流程节点<br />以编辑步骤属性
              </Text>
              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '16px 0' }} />
              <Text style={{ color: '#4a7fa0', fontSize: 11, lineHeight: 1.8 }}>
                顶部按钮添加步骤<br />
                删除键(Delete)删除选中节点<br />
                拖动节点可调整位置
              </Text>
            </div>
          )}

          {/* 步骤列表 */}
          {nodes.filter(n => (n.data as StepNodeData).stepType !== 'start' && (n.data as StepNodeData).stepType !== 'end').length > 0 && (
            <>
              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '16px 0' }} />
              <Text style={{ fontSize: 12, color: '#4a7fa0', display: 'block', marginBottom: 8 }}>步骤列表</Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {nodes
                  .filter(n => {
                    const t = (n.data as StepNodeData).stepType
                    return t !== 'start' && t !== 'end'
                  })
                  .map((n, i) => {
                    const d = n.data as StepNodeData
                    const color = stepColorMap[d.stepType] || '#8ab4cc'
                    return (
                      <div
                        key={n.id}
                        style={{
                          padding: '4px 8px',
                          borderRadius: 4,
                          background: selectedId === n.id ? `${color}18` : 'rgba(0,212,255,0.04)',
                          border: `1px solid ${selectedId === n.id ? color + '44' : 'rgba(0,212,255,0.08)'}`,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                        onClick={() => setSelectedId(n.id)}
                      >
                        <span style={{ fontSize: 10, color: '#4a7fa0' }}>#{i + 1}</span>
                        <span style={{ fontSize: 12 }}>{stepIconMap[d.stepType]}</span>
                        <Text style={{ fontSize: 12, color }}>
                          {stepLabelMap[d.stepType]}
                        </Text>
                      </div>
                    )
                  })
                }
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
