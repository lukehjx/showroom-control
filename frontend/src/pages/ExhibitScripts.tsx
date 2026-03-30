import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Switch,
  Select, Space, Tag, Popconfirm, message, Badge
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined } from '@ant-design/icons'
import axios from 'axios'

interface Script {
  id: number; title: string; trigger_keywords: string[]; nav_poi: string | null
  tts_text: string | null; resource_id: string | null; terminal_id: number | null
  duration: number; sort: number; enabled: boolean
}

export default function ExhibitScripts() {
  const [items, setItems] = useState<Script[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Script | null>(null)
  const [form] = Form.useForm()
  const [poiList, setPoiList] = useState<string[]>([])

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/scripts/'),
        axios.get('/api/robot/status'),
      ])
      setItems(r1.data.data || [])
      setPoiList(r2.data.data?.poi_list || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const handleTest = async (s: Script) => {
    try {
      if (s.nav_poi) {
        await axios.post('/api/robot/navigate', { poi: s.nav_poi })
        message.success(`导航到 ${s.nav_poi}`)
      }
      if (s.tts_text) {
        await axios.post('/api/robot/speak', { text: s.tts_text })
        message.success('TTS播报已发送')
      }
    } catch { message.error('执行失败') }
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    const payload = {
      ...vals,
      trigger_keywords: vals.trigger_keywords
        ? vals.trigger_keywords.split(/[，,]/).map((s: string) => s.trim()).filter(Boolean)
        : [],
    }
    try {
      if (editing) {
        await axios.put(`/api/scripts/${editing.id}`, payload)
        message.success('更新成功')
      } else {
        await axios.post('/api/scripts/', payload)
        message.success('添加成功')
      }
      setOpen(false)
      fetchAll()
    } catch { message.error('保存失败') }
  }

  const columns = [
    { title: '标题', dataIndex: 'title', key: 'title' },
    {
      title: '触发词', dataIndex: 'trigger_keywords', key: 'kw',
      render: (kw: string[]) => (kw || []).map(k => <Tag key={k} color="geekblue">{k}</Tag>)
    },
    {
      title: '导航POI', dataIndex: 'nav_poi', key: 'nav_poi',
      render: (v: string) => v ? <code style={{ color: '#00d4ff' }}>{v}</code> : '-'
    },
    {
      title: '讲解文本', dataIndex: 'tts_text', key: 'tts',
      render: (v: string) => v ? <span title={v}>{v.slice(0, 30)}{v.length > 30 ? '...' : ''}</span> : '-'
    },
    { title: '时长(秒)', dataIndex: 'duration', key: 'dur' },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean) => <Badge status={v ? 'success' : 'default'} text={v ? '启用' : '停用'} />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Script) => (
        <Space>
          <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleTest(r)}>测试</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r)
            form.setFieldsValue({ ...r, trigger_keywords: (r.trigger_keywords || []).join('，') })
            setOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/scripts/${r.id}`)
            message.success('已删除')
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
        title={`展项讲解词管理（${items.length}条）`}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditing(null); form.resetFields(); setOpen(true)
          }}>新增讲解词</Button>
        }
      >
        <div style={{ color: '#8ab4cc', fontSize: 13, marginBottom: 12 }}>
          机器人识别到触发词后，自动导航到对应 POI 并播报讲解内容。
        </div>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑讲解词' : '新增讲解词'} open={open}
        onOk={handleSubmit} onCancel={() => setOpen(false)} width={580}>
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="如 A1展项介绍" />
          </Form.Item>
          <Form.Item name="trigger_keywords" label="触发词（多个用逗号分隔）"
            extra="用户说出这些词时触发本讲解">
            <Input placeholder="如 A1,A1展项,第一个展项" />
          </Form.Item>
          <Form.Item name="nav_poi" label="导航到POI（可选）">
            <Select allowClear showSearch placeholder="选择点位"
              options={poiList.map(p => ({ label: p, value: p }))} />
          </Form.Item>
          <Form.Item name="tts_text" label="机器人播报内容（TTS）">
            <Input.TextArea rows={4} placeholder="机器人到达后播报的讲解词" />
          </Form.Item>
          <Form.Item name="resource_id" label="投放资源ID（可选）"
            extra="展示到屏幕的资源，需先从中控同步">
            <Input placeholder="中控资源ID" />
          </Form.Item>
          <Form.Item name="duration" label="讲解时长（秒）" initialValue={60}>
            <InputNumber min={10} max={600} />
          </Form.Item>
          <Form.Item name="sort" label="排序" initialValue={0}>
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
