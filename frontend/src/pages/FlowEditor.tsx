import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, Select, Space,
  Tag, Popconfirm, message, Badge, Divider, List, Typography, InputNumber, Switch
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, CaretRightOutlined,
  PlusCircleOutlined, ArrowUpOutlined, ArrowDownOutlined
} from '@ant-design/icons'
import axios from 'axios'

// 流程步骤类型
const STEP_TYPES = [
  { label: '导航到POI', value: 'navigate', color: 'blue' },
  { label: '机器人播报', value: 'speak', color: 'green' },
  { label: '延时等待', value: 'delay', color: 'orange' },
  { label: '发送设备指令', value: 'device_command', color: 'red' },
  { label: '企微通知', value: 'wecom_notify', color: 'purple' },
  { label: '等待用户输入', value: 'wait_input', color: 'cyan' },
  { label: '切换专场', value: 'switch_special', color: 'magenta' },
]

interface FlowStep {
  type: string; config: Record<string, unknown>; wait_done?: boolean
}

interface Flow {
  id: number; name: string; description: string | null
  trigger_keywords: string[]; steps: FlowStep[]
  enabled: boolean; sort: number
}

export default function FlowEditor() {
  const [flows, setFlows] = useState<Flow[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Flow | null>(null)
  const [steps, setSteps] = useState<FlowStep[]>([])
  const [form] = Form.useForm()
  const [stepForm] = Form.useForm()
  const [stepOpen, setStepOpen] = useState(false)
  const [poiList, setPoiList] = useState<string[]>([])

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/flows/'),
        axios.get('/api/robot/status'),
      ])
      setFlows(r1.data.data || [])
      setPoiList(r2.data.data?.poi_list || [])
    } catch {
      // 流程API可能还未部署，使用本地状态
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const runFlow = async (id: number) => {
    try {
      await axios.post(`/api/flows/${id}/run`)
      message.success('流程已启动')
    } catch { message.error('启动失败') }
  }

  const moveStep = (i: number, dir: 'up' | 'down') => {
    const arr = [...steps]
    if (dir === 'up' && i > 0) { [arr[i - 1], arr[i]] = [arr[i], arr[i - 1]] }
    if (dir === 'down' && i < arr.length - 1) { [arr[i], arr[i + 1]] = [arr[i + 1], arr[i]] }
    setSteps(arr)
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    const payload = {
      ...vals,
      trigger_keywords: vals.trigger_keywords
        ? vals.trigger_keywords.split(/[，,]/).map((s: string) => s.trim()).filter(Boolean) : [],
      steps,
    }
    try {
      if (editing) {
        await axios.put(`/api/flows/${editing.id}`, payload)
      } else {
        await axios.post('/api/flows/', payload)
      }
      message.success('保存成功')
      setOpen(false)
      fetchAll()
    } catch { message.error('保存失败') }
  }

  const addStep = async () => {
    const vals = await stepForm.validateFields()
    setSteps([...steps, { type: vals.type, config: vals.config || {}, wait_done: vals.wait_done }])
    stepForm.resetFields()
    setStepOpen(false)
  }

  const stepLabel = (s: FlowStep) => {
    const t = STEP_TYPES.find(x => x.value === s.type)
    const cfg = s.config || {}
    const detail = cfg.poi || cfg.text || cfg.command || cfg.seconds ? `: ${cfg.poi || cfg.text || cfg.command || cfg.seconds}` : ''
    return { label: (t?.label || s.type) + detail, color: t?.color || 'default' }
  }

  const columns = [
    { title: '流程名称', dataIndex: 'name', key: 'name' },
    {
      title: '步骤数', dataIndex: 'steps', key: 'steps',
      render: (s: FlowStep[]) => <Tag>{(s || []).length}步</Tag>
    },
    {
      title: '触发词', dataIndex: 'trigger_keywords', key: 'kw',
      render: (kw: string[]) => (kw || []).map(k => <Tag key={k} color="gold">{k}</Tag>)
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'ok',
      render: (v: boolean) => <Badge status={v ? 'success' : 'default'} text={v ? '启用' : '停用'} />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Flow) => (
        <Space>
          <Button size="small" type="primary" icon={<CaretRightOutlined />} onClick={() => runFlow(r.id)}>执行</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r); setSteps(r.steps || [])
            form.setFieldsValue({ ...r, trigger_keywords: (r.trigger_keywords || []).join('，') })
            setOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/flows/${r.id}`)
            fetchAll()
          }}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    },
  ]

  return (
    <div>
      <Card
        title={`流程编排（${flows.length}个）`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); setSteps([]); form.resetFields(); setOpen(true)
        }}>新建流程</Button>}
      >
        <div style={{ color: '#8ab4cc', fontSize: 13, marginBottom: 12 }}>
          流程是多步骤动作序列：导航→播报→设备控制→通知，支持语音触发或手动执行。
        </div>
        <Table dataSource={flows} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑流程' : '新建流程'} open={open}
        onOk={handleSubmit} onCancel={() => setOpen(false)} width={680}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="流程名称" rules={[{ required: true }]}>
            <Input placeholder="如 接待贵宾流程" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input />
          </Form.Item>
          <Form.Item name="trigger_keywords" label="触发词（逗号分隔）">
            <Input placeholder="如 开始接待,迎宾" />
          </Form.Item>

          <Divider>步骤列表（{steps.length}步）</Divider>
          <List size="small" dataSource={steps} renderItem={(s, i) => {
            const { label, color } = stepLabel(s)
            return (
              <List.Item actions={[
                <Button type="link" size="small" icon={<ArrowUpOutlined />} onClick={() => moveStep(i, 'up')} />,
                <Button type="link" size="small" icon={<ArrowDownOutlined />} onClick={() => moveStep(i, 'down')} />,
                <Button type="link" danger size="small"
                  onClick={() => setSteps(steps.filter((_, j) => j !== i))}>删除</Button>
              ]}>
                <Typography.Text>
                  <strong style={{ color: '#8ab4cc' }}>#{i + 1}</strong>{' '}
                  <Tag color={color}>{label}</Tag>
                  {s.wait_done && <Tag color="gold">等待完成</Tag>}
                </Typography.Text>
              </List.Item>
            )
          }} />
          <Button icon={<PlusCircleOutlined />} onClick={() => setStepOpen(true)} style={{ marginTop: 8 }}>
            添加步骤
          </Button>

          <Form.Item name="sort" label="排序" initialValue={0} style={{ marginTop: 12 }}>
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="enabled" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="添加步骤" open={stepOpen} onOk={addStep} onCancel={() => setStepOpen(false)}>
        <Form form={stepForm} layout="vertical">
          <Form.Item name="type" label="步骤类型" rules={[{ required: true }]}>
            <Select options={STEP_TYPES} onChange={() => stepForm.setFieldValue('config', {})} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(p, c) => p.type !== c.type}>
            {({ getFieldValue }) => {
              const t = getFieldValue('type')
              if (t === 'navigate') return (
                <Form.Item name={['config', 'poi']} label="POI点位" rules={[{ required: true }]}>
                  <Select showSearch options={poiList.map(p => ({ label: p, value: p }))} />
                </Form.Item>
              )
              if (t === 'speak') return (
                <Form.Item name={['config', 'text']} label="播报文本" rules={[{ required: true }]}>
                  <Input.TextArea rows={3} />
                </Form.Item>
              )
              if (t === 'delay') return (
                <Form.Item name={['config', 'seconds']} label="等待秒数" rules={[{ required: true }]}>
                  <InputNumber min={1} max={300} />
                </Form.Item>
              )
              if (t === 'device_command') return (
                <Form.Item name={['config', 'command']} label="TCP指令" rules={[{ required: true }]}>
                  <Input placeholder="如 0_all_on" />
                </Form.Item>
              )
              if (t === 'wecom_notify') return (
                <Form.Item name={['config', 'text']} label="通知内容" rules={[{ required: true }]}>
                  <Input.TextArea rows={2} />
                </Form.Item>
              )
              if (t === 'switch_special') return (
                <Form.Item name={['config', 'special_id']} label="专场ID" rules={[{ required: true }]}>
                  <InputNumber min={1} />
                </Form.Item>
              )
              return null
            }}
          </Form.Item>
          <Form.Item name="wait_done" valuePropName="checked" label="等待本步骤完成后再执行下一步">
            <Switch defaultChecked />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
