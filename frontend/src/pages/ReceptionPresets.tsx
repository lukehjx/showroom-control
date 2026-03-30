import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, Switch, Space,
  Tag, Popconfirm, message, Badge, Divider, List, Typography, Select
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined, PlusCircleOutlined } from '@ant-design/icons'
import axios from 'axios'

interface Step {
  type: string; value?: string; wait?: boolean; delay?: number
}

interface Preset {
  id: number; name: string; description: string | null; trigger_keywords: string[]
  steps: Step[]; sort: number; enabled: boolean
}

const STEP_TYPES = [
  { label: '导航到POI', value: 'navigate' },
  { label: '机器人播报(TTS)', value: 'speak' },
  { label: '停留等待(秒)', value: 'wait' },
  { label: '发送中控命令', value: 'command' },
  { label: '企微发消息', value: 'notify' },
]

export default function ReceptionPresets() {
  const [items, setItems] = useState<Preset[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Preset | null>(null)
  const [steps, setSteps] = useState<Step[]>([])
  const [form] = Form.useForm()
  const [stepForm] = Form.useForm()
  const [stepOpen, setStepOpen] = useState(false)
  const [poiList, setPoiList] = useState<string[]>([])

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/reception/presets'),
        axios.get('/api/robot/status'),
      ])
      setItems(r1.data.data || [])
      setPoiList(r2.data.data?.poi_list || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const handleExecute = async (id: number) => {
    try {
      await axios.post(`/api/reception/presets/${id}/execute`)
      message.success('接待套餐已启动')
    } catch { message.error('启动失败') }
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
        await axios.put(`/api/reception/presets/${editing.id}`, payload)
      } else {
        await axios.post('/api/reception/presets', payload)
      }
      message.success('保存成功')
      setOpen(false)
      fetchAll()
    } catch { message.error('保存失败') }
  }

  const stepDesc = (s: Step) => {
    const t = STEP_TYPES.find(x => x.value === s.type)?.label || s.type
    return `${t}: ${s.value || s.delay || ''}`
  }

  const columns = [
    { title: '套餐名称', dataIndex: 'name', key: 'name' },
    {
      title: '步骤数', dataIndex: 'steps', key: 'steps',
      render: (s: Step[]) => <Tag>{(s || []).length}步</Tag>
    },
    {
      title: '触发词', dataIndex: 'trigger_keywords', key: 'kw',
      render: (kw: string[]) => (kw || []).map(k => <Tag key={k} color="purple">{k}</Tag>)
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean) => <Badge status={v ? 'success' : 'default'} text={v ? '启用' : '停用'} />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Preset) => (
        <Space>
          <Button size="small" type="primary" icon={<PlayCircleOutlined />}
            onClick={() => handleExecute(r.id)}>执行</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r); setSteps(r.steps || [])
            form.setFieldsValue({ ...r, trigger_keywords: (r.trigger_keywords || []).join('，') })
            setOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/reception/presets/${r.id}`)
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
        title={`接待套餐管理（${items.length}套）`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); setSteps([]); form.resetFields(); setOpen(true)
        }}>新增套餐</Button>}
      >
        <div style={{ color: '#8ab4cc', fontSize: 13, marginBottom: 12 }}>
          接待套餐是一系列动作的组合（导航+播报+命令+通知），可通过语音触发或手动执行。
        </div>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑接待套餐' : '新增接待套餐'} open={open}
        onOk={handleSubmit} onCancel={() => setOpen(false)} width={620}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="套餐名称" rules={[{ required: true }]}>
            <Input placeholder="如 VIP接待、标准参观" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input />
          </Form.Item>
          <Form.Item name="trigger_keywords" label="触发词（逗号分隔）">
            <Input placeholder="如 VIP接待,接待贵宾" />
          </Form.Item>
          <Divider>执行步骤（{steps.length}步）</Divider>
          <List size="small" dataSource={steps} renderItem={(s, i) => (
            <List.Item actions={[
              <Button type="link" danger size="small"
                onClick={() => setSteps(steps.filter((_, j) => j !== i))}>删除</Button>
            ]}>
              <Typography.Text><strong>#{i + 1}</strong> {stepDesc(s)}</Typography.Text>
            </List.Item>
          )} />
          <Button icon={<PlusCircleOutlined />} onClick={() => setStepOpen(true)} style={{ marginTop: 8 }}>
            添加步骤
          </Button>
          <Form.Item name="enabled" valuePropName="checked" initialValue={true} style={{ marginTop: 12 }}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="添加步骤" open={stepOpen} onOk={async () => {
        const vals = await stepForm.validateFields()
        setSteps([...steps, vals])
        stepForm.resetFields()
        setStepOpen(false)
      }} onCancel={() => setStepOpen(false)}>
        <Form form={stepForm} layout="vertical">
          <Form.Item name="type" label="步骤类型" rules={[{ required: true }]}>
            <Select options={STEP_TYPES} onChange={() => stepForm.setFieldValue('value', undefined)} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(p, c) => p.type !== c.type}>
            {({ getFieldValue }) => {
              const t = getFieldValue('type')
              if (t === 'navigate') return (
                <Form.Item name="value" label="POI点位" rules={[{ required: true }]}>
                  <Select showSearch options={poiList.map(p => ({ label: p, value: p }))} />
                </Form.Item>
              )
              if (t === 'speak') return (
                <Form.Item name="value" label="播报文本" rules={[{ required: true }]}>
                  <Input.TextArea rows={3} />
                </Form.Item>
              )
              if (t === 'wait') return (
                <Form.Item name="delay" label="等待秒数" rules={[{ required: true }]}>
                  <Input type="number" />
                </Form.Item>
              )
              if (t === 'command') return (
                <Form.Item name="value" label="指令字符串" rules={[{ required: true }]}>
                  <Input placeholder="如 0_all_on" />
                </Form.Item>
              )
              if (t === 'notify') return (
                <Form.Item name="value" label="通知内容" rules={[{ required: true }]}>
                  <Input.TextArea rows={2} />
                </Form.Item>
              )
              return null
            }}
          </Form.Item>
          <Form.Item name="wait" valuePropName="checked" label="等待完成再执行下一步">
            <Switch defaultChecked />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
