import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Switch,
  Space, Tag, Popconfirm, message, Badge, Divider, Select,
  List, Typography
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, CaretRightOutlined, PlusCircleOutlined } from '@ant-design/icons'
import axios from 'axios'

interface RouteStep {
  poi: string; speak_text?: string; dwell_seconds: number; script_id?: number
}

interface Route {
  id: number; name: string; description: string | null; trigger_keywords: string[]
  steps: RouteStep[]; sort: number; enabled: boolean; estimated_minutes: number
}

export default function TourRoutes() {
  const [items, setItems] = useState<Route[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Route | null>(null)
  const [steps, setSteps] = useState<RouteStep[]>([])
  const [poiList, setPoiList] = useState<string[]>([])
  const [form] = Form.useForm()
  const [stepForm] = Form.useForm()
  const [stepModalOpen, setStepModalOpen] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/routes/'),
        axios.get('/api/robot/status'),
      ])
      setItems(r1.data.data || [])
      setPoiList(r2.data.data?.poi_list || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const handleStart = async (id: number) => {
    try {
      await axios.post(`/api/routes/${id}/start`)
      message.success('导览路线已启动，机器人开始执行')
    } catch { message.error('启动失败') }
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    const payload = {
      ...vals,
      trigger_keywords: vals.trigger_keywords
        ? vals.trigger_keywords.split(/[，,]/).map((s: string) => s.trim()).filter(Boolean)
        : [],
      steps,
    }
    try {
      if (editing) {
        await axios.put(`/api/routes/${editing.id}`, payload)
        message.success('更新成功')
      } else {
        await axios.post('/api/routes/', payload)
        message.success('添加成功')
      }
      setOpen(false)
      fetchAll()
    } catch { message.error('保存失败') }
  }

  const addStep = async () => {
    const vals = await stepForm.validateFields()
    setSteps([...steps, { ...vals }])
    stepForm.resetFields()
    setStepModalOpen(false)
  }

  const columns = [
    { title: '路线名称', dataIndex: 'name', key: 'name' },
    {
      title: '站点数', dataIndex: 'steps', key: 'steps',
      render: (s: RouteStep[]) => <Tag>{(s || []).length} 站</Tag>
    },
    { title: '预计时长', dataIndex: 'estimated_minutes', key: 'min', render: (v: number) => `${v}分钟` },
    {
      title: '触发词', dataIndex: 'trigger_keywords', key: 'kw',
      render: (kw: string[]) => (kw || []).map(k => <Tag key={k} color="blue">{k}</Tag>)
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean) => <Badge status={v ? 'success' : 'default'} text={v ? '启用' : '停用'} />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Route) => (
        <Space>
          <Button size="small" type="primary" icon={<CaretRightOutlined />}
            onClick={() => handleStart(r.id)}>启动</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r)
            setSteps(r.steps || [])
            form.setFieldsValue({ ...r, trigger_keywords: (r.trigger_keywords || []).join('，') })
            setOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/routes/${r.id}`)
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
        title={`导览路线管理（${items.length}条）`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); setSteps([]); form.resetFields(); setOpen(true)
        }}>新增路线</Button>}
      >
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑路线' : '新增导览路线'} open={open}
        onOk={handleSubmit} onCancel={() => setOpen(false)} width={640}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="路线名称" rules={[{ required: true }]}>
            <Input placeholder="如 标准参观路线" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="trigger_keywords" label="触发词（逗号分隔）">
            <Input placeholder="如 参观,导览,带我参观" />
          </Form.Item>
          <Form.Item name="estimated_minutes" label="预计时长(分钟)" initialValue={15}>
            <InputNumber min={1} max={120} />
          </Form.Item>

          <Divider>站点列表（{steps.length}站）</Divider>
          <List
            size="small"
            dataSource={steps}
            renderItem={(s, i) => (
              <List.Item actions={[
                <Button type="link" danger size="small" onClick={() => setSteps(steps.filter((_, j) => j !== i))}>删除</Button>
              ]}>
                <Typography.Text><strong>#{i + 1}</strong> {s.poi}
                  {s.speak_text && <span style={{ color: '#8ab4cc' }}> — {s.speak_text.slice(0, 20)}...</span>}
                  <Tag style={{ marginLeft: 8 }}>{s.dwell_seconds}秒</Tag>
                </Typography.Text>
              </List.Item>
            )}
          />
          <Button icon={<PlusCircleOutlined />} onClick={() => setStepModalOpen(true)} style={{ marginTop: 8 }}>
            添加站点
          </Button>

          <Form.Item name="sort" label="排序" initialValue={0} style={{ marginTop: 12 }}>
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="enabled" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="添加站点" open={stepModalOpen} onOk={addStep} onCancel={() => setStepModalOpen(false)}>
        <Form form={stepForm} layout="vertical">
          <Form.Item name="poi" label="POI点位" rules={[{ required: true }]}>
            <Select showSearch options={poiList.map(p => ({ label: p, value: p }))}
              placeholder="选择导航点" />
          </Form.Item>
          <Form.Item name="speak_text" label="到达后播报文本">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="dwell_seconds" label="停留时长（秒）" initialValue={30}>
            <InputNumber min={5} max={600} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
