import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, Switch, Space, Tag, Popconfirm, message, Badge, Tooltip } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, CaretRightOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

interface Task {
  id: number; name: string; cron_expr: string; task_type: string
  payload: Record<string, unknown>; enabled: boolean; last_run: string | null; next_run: string | null
}

const TASK_TYPES = [
  { label: '一键开馆', value: 'open_hall' },
  { label: '一键闭馆', value: 'close_hall' },
  { label: '同步云平台数据', value: 'sync_data' },
  { label: '执行自定义流程', value: 'custom_flow' },
]

const CRON_PRESETS = [
  { label: '工作日 09:00', value: '0 9 * * 1-5' },
  { label: '工作日 18:00', value: '0 18 * * 1-5' },
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每天 20:00', value: '0 20 * * *' },
  { label: '每小时', value: '0 * * * *' },
  { label: '每天凌晨同步', value: '0 2 * * *' },
]

export default function ScheduledTasks() {
  const [items, setItems] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Task | null>(null)
  const [form] = Form.useForm()

  const fetchAll = async () => {
    setLoading(true)
    try {
      const r = await axios.get('/api/tasks/')
      setItems(r.data.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const handleRun = async (id: number, name: string) => {
    try {
      await axios.post(`/api/tasks/${id}/run`)
      message.success(`任务 [${name}] 已立即执行`)
    } catch { message.error('执行失败') }
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    try {
      if (editing) {
        await axios.put(`/api/tasks/${editing.id}`, vals)
      } else {
        await axios.post('/api/tasks/', vals)
      }
      message.success('保存成功')
      setOpen(false)
      fetchAll()
    } catch { message.error('保存失败') }
  }

  const columns = [
    { title: '任务名称', dataIndex: 'name', key: 'name' },
    {
      title: 'Cron表达式',
      dataIndex: 'cron_expr', key: 'cron',
      render: (v: string) => <code style={{ color: '#00d4ff' }}>{v}</code>
    },
    {
      title: '任务类型', dataIndex: 'task_type', key: 'type',
      render: (v: string) => {
        const t = TASK_TYPES.find(x => x.value === v)
        return <Tag color="blue">{t?.label || v}</Tag>
      }
    },
    {
      title: '上次执行', dataIndex: 'last_run', key: 'last',
      render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-'
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean) => <Badge status={v ? 'success' : 'default'} text={v ? '启用' : '停用'} />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Task) => (
        <Space>
          <Button size="small" icon={<CaretRightOutlined />} onClick={() => handleRun(r.id, r.name)}>立即执行</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r); form.setFieldsValue(r); setOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/tasks/${r.id}`)
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
        title={`定时任务（${items.length}个）`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); form.resetFields(); setOpen(true)
        }}>新增任务</Button>}
      >
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑定时任务' : '新增定时任务'} open={open}
        onOk={handleSubmit} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="如 每日开馆" />
          </Form.Item>
          <Form.Item name="cron_expr" label={
            <Space>
              Cron表达式
              <Tooltip title="格式: 分 时 日 月 周。例: 0 9 * * 1-5 = 工作日9点">
                <QuestionCircleOutlined />
              </Tooltip>
            </Space>
          } rules={[{ required: true }]}>
            <Select showSearch allowClear
              options={CRON_PRESETS}
              placeholder="选择预设或输入自定义表达式"
              onSelect={(v) => form.setFieldValue('cron_expr', v)}
            />
          </Form.Item>
          <Form.Item name="task_type" label="任务类型" rules={[{ required: true }]}>
            <Select options={TASK_TYPES} />
          </Form.Item>
          <Form.Item name="enabled" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
