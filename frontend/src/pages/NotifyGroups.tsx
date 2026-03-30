import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Switch, Space, Tag, Popconfirm, message, Badge, Select } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, BellOutlined } from '@ant-design/icons'
import axios from 'axios'

interface Group {
  id: number; name: string; chat_id: string; enabled: boolean; notify_types: string[]
}

const NOTIFY_TYPES = [
  { label: '访客到达', value: 'arrival' },
  { label: '设备指令', value: 'command' },
  { label: '系统错误', value: 'error' },
  { label: '数据同步', value: 'sync' },
  { label: '定时任务', value: 'task' },
]

export default function NotifyGroups() {
  const [items, setItems] = useState<Group[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Group | null>(null)
  const [form] = Form.useForm()

  const fetchAll = async () => {
    setLoading(true)
    try {
      const r = await axios.get('/api/notify-groups/')
      setItems(r.data.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const handleTest = async (id: number) => {
    try {
      await axios.post(`/api/notify-groups/${id}/test`)
      message.success('测试消息已发送')
    } catch { message.error('发送失败') }
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    try {
      if (editing) {
        await axios.put(`/api/notify-groups/${editing.id}`, vals)
      } else {
        await axios.post('/api/notify-groups/', vals)
      }
      message.success('保存成功')
      setOpen(false)
      fetchAll()
    } catch { message.error('保存失败') }
  }

  const columns = [
    { title: '群组名称', dataIndex: 'name', key: 'name' },
    {
      title: '企微群ID', dataIndex: 'chat_id', key: 'chat_id',
      render: (v: string) => <code style={{ fontSize: 11, color: '#8ab4cc' }}>{v}</code>
    },
    {
      title: '通知类型', dataIndex: 'notify_types', key: 'types',
      render: (types: string[]) => (types || []).map(t => {
        const label = NOTIFY_TYPES.find(x => x.value === t)?.label || t
        return <Tag key={t} color="cyan">{label}</Tag>
      })
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean) => <Badge status={v ? 'success' : 'default'} text={v ? '启用' : '停用'} />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Group) => (
        <Space>
          <Button size="small" icon={<BellOutlined />} onClick={() => handleTest(r.id)}>测试</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r); form.setFieldsValue(r); setOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/notify-groups/${r.id}`)
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
        title={`通知群组（${items.length}个）`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); form.resetFields(); setOpen(true)
        }}>新增群组</Button>}
      >
        <div style={{ color: '#8ab4cc', fontSize: 13, marginBottom: 12 }}>
          配置企业微信群，系统事件自动推送通知到对应群。
        </div>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑通知群组' : '新增通知群组'} open={open}
        onOk={handleSubmit} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="群组名称" rules={[{ required: true }]}>
            <Input placeholder="如 展厅运营群" />
          </Form.Item>
          <Form.Item name="chat_id" label="企微群ChatID" rules={[{ required: true }]}
            extra="在企微中通过 wecom_mcp 获取，或从现有配置获取">
            <Input placeholder="wrsFDcBgAA5Vyl..." />
          </Form.Item>
          <Form.Item name="notify_types" label="接收通知类型">
            <Select mode="multiple" options={NOTIFY_TYPES} placeholder="选择通知类型" />
          </Form.Item>
          <Form.Item name="enabled" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
