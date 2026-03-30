import { useCallback, useEffect, useRef, useState } from 'react'
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
  Row,
  Col,
} from 'antd'
import {
  SaveOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography
const { TextArea } = Input

interface StopNodeData {
  poiName?: string
  dwellSeconds?: number
  speakText?: string
  index?: number
  onSelect?: (id: string) => void
}

function StopNode({ id, data, selected }: { id: string; data: StopNodeData; selected: boolean }) {
  return (
    <div
      onClick={() => data.onSelect?.(id)}
      style={{
        background: 'rgba(8,24,42,0.92)',
        border: `2px solid ${selected ? '#ffffff' : '#00d4ff'}`,
        borderRadius: 10,
        padding: '10px 16px',
        minWidth: 160,
        maxWidth: 220,
        boxShadow: selected ? '0 0 16px #00d4ff88' : '0 0 8px #00d4ff33',
        cursor: 'pointer',
        color: '#e2f4ff',
        fontSize: 12,
        transition: 'all 0.15s',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#00d4ff', border: 'none', width: 8, height: 8 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 16 }}>📍</span>
        <span style={{ color: '#00d4ff', fontWeight: 600, fontSize: 13 }}>
          {data.poiName || '未命名站点'}
        </span>
        {data.index != null && (
          <span style={{
            marginLeft: 'auto',
            background: 'rgba(0,212,255,0.15)',
            border: '1px solid rgba(0,212,255,0.3)',
            borderRadius: 10,
            padding: '0 6px',
            fontSize: 10,
            color: '#8ab4cc',
          }}>
            #{data.index + 1}
          </span>
        )}
      </div>
      {data.dwellSeconds != null && (
        <div style={{ color: '#ff7c00', fontSize: 11 }}>⏱ 停留 {data.dwellSeconds}秒</div>
      )}
      {data.speakText && (
        <div style={{ color: '#8ab4cc', fontSize: 11, marginTop: 2 }}>
          💬 {data.speakText.slice(0, 24)}{data.speakText.length > 24 ? '…' : ''}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: '#00d4ff', border: 'none', width: 8, height: 8 }} />
    </div>
  )
}

const nodeTypes: NodeTypes = { stop: StopNode }

let nodeIdCounter = 200

export default function TourRoutes() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [routeName, setRouteName] = useState('')
  const [routeId, setRouteId] = useState<string | null>(null)
  const [routeList, setRouteList] = useState<{ id: string; name: string }[]>([])
  const [positions, setPositions] = useState<{ name: string }[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [readonly, setReadonly] = useState(false)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null)

  useEffect(() => {
    axios.get('/api/tours/').then(r => {
      const d = r.data
      if (Array.isArray(d)) setRouteList(d)
      else if (d?.items) setRouteList(d.items)
    }).catch(() => {})
    axios.get('/api/robot/positions').then(r => {
      const d = r.data
      if (Array.isArray(d)) setPositions(d)
      else if (d?.positions) setPositions(d.positions)
    }).catch(() => {})
  }, [])

  const handleSelect = useCallback((id: string) => {
    if (!readonly) setSelectedId(id)
  }, [readonly])

  const nodesWithCallback = nodes.map((n, i) => ({
    ...n,
    data: { ...n.data, index: i, onSelect: handleSelect },
  }))

  const onConnect = useCallback((params: Connection) => {
    setEdges(eds => addEdge({ ...params, style: { stroke: '#00d4ff', strokeWidth: 2 } }, eds))
  }, [setEdges])

  const addStop = () => {
    const idx = nodes.length
    const newNode: Node = {
      id: `stop_${++nodeIdCounter}`,
      type: 'stop',
      position: { x: 240, y: 80 + idx * 120 },
      data: {
        poiName: '',
        dwellSeconds: 30,
        speakText: '',
        onSelect: handleSelect,
      },
    }
    // 自动连接上一个节点
    setNodes(nds => {
      if (nds.length > 0) {
        const prev = nds[nds.length - 1]
        setEdges(eds => [
          ...eds,
          {
            id: `e_${prev.id}_${newNode.id}`,
            source: prev.id,
            target: newNode.id,
            style: { stroke: '#00d4ff', strokeWidth: 2 },
          },
        ])
      }
      return [...nds, newNode]
    })
  }

  const updateSelected = (patch: Partial<StopNodeData>) => {
    if (!selectedId) return
    setNodes(nds =>
      nds.map(n => n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n)
    )
  }

  const selectedNode = nodes.find(n => n.id === selectedId)

  const handleSave = async () => {
    if (!routeName.trim()) { message.warning('请输入路线名称'); return }
    setSaving(true)
    try {
      const stops = nodes.map(n => ({
        poiName: (n.data as StopNodeData).poiName,
        dwellSeconds: (n.data as StopNodeData).dwellSeconds,
        speakText: (n.data as StopNodeData).speakText,
      }))
      const payload = { name: routeName, stops, nodes, edges }
      if (routeId) {
        await axios.put(`/api/tours/${routeId}`, payload)
      } else {
        const r = await axios.post('/api/tours/', payload)
        if (r.data?.id) setRouteId(r.data.id)
      }
      message.success('路线保存成功')
      axios.get('/api/tours/').then(r => {
        const d = r.data
        if (Array.isArray(d)) setRouteList(d)
        else if (d?.items) setRouteList(d.items)
      }).catch(() => {})
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLoad = (id: string) => {
    axios.get(`/api/tours/${id}`).then(r => {
      const d = r.data
      setRouteId(id)
      setRouteName(d.name || '')
      if (Array.isArray(d.nodes)) {
        setNodes(d.nodes.map((n: Node) => ({ ...n, data: { ...n.data, onSelect: handleSelect } })))
      }
      if (Array.isArray(d.edges)) setEdges(d.edges)
      setSelectedId(null)
    }).catch(() => message.error('加载失败'))
  }

  const handleRun = async () => {
    if (!routeId) { message.warning('请先保存路线'); return }
    setRunning(true)
    try {
      await axios.post(`/api/tours/${routeId}/run`)
      message.success('路线已启动')
    } catch {
      message.error('启动失败')
    } finally {
      setRunning(false)
    }
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
        <Input
          value={routeName}
          onChange={e => setRouteName(e.target.value)}
          placeholder="路线名称"
          style={{ width: 200, background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
        />
        <Button
          icon={<PlusOutlined />}
          onClick={addStop}
          disabled={readonly}
          style={{ background: 'rgba(0,212,255,0.08)', borderColor: 'rgba(0,212,255,0.3)', color: '#00d4ff' }}
        >
          新增站点
        </Button>
        <Button
          icon={<SaveOutlined />}
          loading={saving}
          onClick={handleSave}
          disabled={readonly}
          style={{ background: 'rgba(0,212,255,0.1)', borderColor: '#00d4ff', color: '#00d4ff' }}
        >
          保存
        </Button>
        <Select
          placeholder="加载已有路线"
          style={{ width: 180 }}
          onChange={handleLoad}
          value={routeId}
          options={routeList.map(r => ({ label: r.name, value: r.id }))}
        />
        <Button
          icon={<PlayCircleOutlined />}
          loading={running}
          onClick={handleRun}
          style={{ background: 'rgba(57,255,20,0.1)', borderColor: '#39ff14', color: '#39ff14' }}
        >
          启动路线
        </Button>
        <Button
          icon={readonly ? <EditOutlined /> : <EyeOutlined />}
          onClick={() => setReadonly(!readonly)}
          style={{ marginLeft: 'auto', borderColor: 'rgba(0,212,255,0.3)', color: '#8ab4cc' }}
        >
          {readonly ? '编辑' : '只读'}
        </Button>
      </div>

      {/* 画布 + 属性面板 */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', borderRadius: '0 0 12px 12px' }}>
        {/* ReactFlow 画布 */}
        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodesWithCallback}
            edges={edges}
            onNodesChange={readonly ? undefined : onNodesChange}
            onEdgesChange={readonly ? undefined : onEdgesChange}
            onConnect={readonly ? undefined : onConnect}
            onInit={setRfInstance}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode={readonly ? null : 'Delete'}
            nodesDraggable={!readonly}
            nodesConnectable={!readonly}
            style={{ background: '#080f1a' }}
            defaultEdgeOptions={{ style: { stroke: '#00d4ff', strokeWidth: 2 } }}
          >
            <Background color="#0d2a3e" gap={20} variant={BackgroundVariant.Dots} />
            <Controls />
          </ReactFlow>
          {nodes.length === 0 && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              pointerEvents: 'none',
            }}>
              <Text style={{ color: '#4a7fa0', fontSize: 14 }}>点击"新增站点"开始规划路线</Text>
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
          {selectedNode && !readonly ? (
            <>
              <Text style={{ fontSize: 13, fontWeight: 600, color: '#00d4ff', display: 'block', marginBottom: 12 }}>
                站点属性
              </Text>
              <Form layout="vertical" size="small">
                <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>POI 名称</Text>}>
                  {positions.length > 0 ? (
                    <Select
                      value={(selectedNode.data as StopNodeData).poiName}
                      onChange={val => updateSelected({ poiName: val })}
                      placeholder="选择点位"
                      options={positions.map(p => ({ label: p.name, value: p.name }))}
                      style={{ width: '100%' }}
                    />
                  ) : (
                    <Input
                      value={(selectedNode.data as StopNodeData).poiName}
                      onChange={e => updateSelected({ poiName: e.target.value })}
                      placeholder="输入POI名称"
                      style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff' }}
                    />
                  )}
                </Form.Item>
                <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>停留时长（秒）</Text>}>
                  <InputNumber
                    value={(selectedNode.data as StopNodeData).dwellSeconds}
                    onChange={val => updateSelected({ dwellSeconds: val ?? 0 })}
                    min={0}
                    max={3600}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
                <Form.Item label={<Text style={{ color: '#8ab4cc', fontSize: 12 }}>播报文本</Text>}>
                  <TextArea
                    value={(selectedNode.data as StopNodeData).speakText}
                    onChange={e => updateSelected({ speakText: e.target.value })}
                    placeholder="到达此站点时的播报内容"
                    rows={5}
                    style={{ background: 'rgba(0,212,255,0.05)', borderColor: 'rgba(0,212,255,0.2)', color: '#e2f4ff', resize: 'vertical' }}
                  />
                </Form.Item>
              </Form>
              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
              <Button
                block danger size="small" icon={<DeleteOutlined />}
                onClick={() => {
                  setNodes(nds => nds.filter(n => n.id !== selectedId))
                  setEdges(eds => eds.filter(e => e.source !== selectedId && e.target !== selectedId))
                  setSelectedId(null)
                }}
              >
                删除此站点
              </Button>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Text style={{ color: '#4a7fa0', fontSize: 12, lineHeight: 1.8 }}>
                {readonly ? '只读模式\n点击"编辑"进行修改' : '点击站点节点\n以编辑属性'}
              </Text>
            </div>
          )}

          {/* 路线概览 */}
          {nodes.length > 0 && (
            <>
              <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '16px 0' }} />
              <Text style={{ fontSize: 12, color: '#4a7fa0', display: 'block', marginBottom: 8 }}>路线概览</Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {nodes.map((n, i) => (
                  <div
                    key={n.id}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 4,
                      background: selectedId === n.id ? 'rgba(0,212,255,0.1)' : 'rgba(0,212,255,0.04)',
                      border: `1px solid ${selectedId === n.id ? 'rgba(0,212,255,0.4)' : 'rgba(0,212,255,0.08)'}`,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                    onClick={() => !readonly && setSelectedId(n.id)}
                  >
                    <span style={{ fontSize: 10, color: '#4a7fa0' }}>#{i + 1}</span>
                    <Text style={{ fontSize: 12, color: '#e2f4ff' }}>
                      {(n.data as StopNodeData).poiName || '未命名'}
                    </Text>
                    <Text style={{ fontSize: 10, color: '#8ab4cc', marginLeft: 'auto' }}>
                      {(n.data as StopNodeData).dwellSeconds || 0}s
                    </Text>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
