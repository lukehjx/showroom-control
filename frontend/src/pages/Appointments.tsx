import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Select,
  Space, Tag, Popconfirm, message, DatePicker, Badge
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

interface Appointment {
  id: number; visitor_name: string; visitor_company: string | null
  visitor_count: number; visit_time: string; preset_id: number | null
  contact: string | null; status: string; notes: string | null; created_at: number
}

interface Preset { id: number; name: string }

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  pending: { color: 'orange', label: '待确认' },
  confirmed: { color: 'green', label: '已确认' },
  cancelled: { color: 'red', label: '已取消' },
  completed: { color: 'blue', label: '已完成' },
}

export default function Appointments() {
  const [items, setItems] = useState<Appointment[]>([])
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/reception/appointments'),
        axios.get('/api/reception/presets'),
      ])
      setItems(r1.data.data || [])
      setPresets(r2.data.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const updateStatus = async (id: number, status: string) => {
    await axios.put(`/api/reception/appointments/${id}/status?status=${status}`)
    message.success('状态已更新')
    fetchAll()
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    const payload = { ...vals, visit_time: vals.visit_time.toISOString() }
    try {
      await axios.post('/api/reception/appointments', payload)
      message.success('预约已创建')
      setOpen(false)
      fetchAll()
    } catch { message.error('创建失败') }
  }

  const columns = [
    { title: '访客姓名', dataIndex: 'visitor_name', key: 'vname' },
    { title: '单位', dataIndex: 'visitor_company', key: 'company', render: (v: string) => v || '-' },
    { title: '人数', dataIndex: 'visitor_count', key: 'cnt' },
    {
      title: '参观时间', dataIndex: 'visit_time', key: 'time',
      render: (t: string) => dayjs(t).format('MM-DD HH:mm')
    },
    {
      title: '接待套餐', dataIndex: 'preset_id', key: 'preset',
      render: (id: number) => {
        const p = presets.find(x => x.id === id)
        return p ? <Tag color="purple">{p.name}</Tag> : '-'
      }
    },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Badge
        status={s === 'confirmed' ? 'success' : s === 'cancelled' ? 'error' : s === 'completed' ? 'processing' : 'warning'}
        text={STATUS_MAP[s]?.label || s}
      />
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: Appointment) => (
        <Space>
          {r.status === 'pending' && (
            <Button size="small" type="primary" onClick={() => updateStatus(r.id, 'confirmed')}>确认</Button>
          )}
          {r.status === 'confirmed' && (
            <Button size="small" onClick={() => updateStatus(r.id, 'completed')}>完成</Button>
          )}
          {(r.status === 'pending' || r.status === 'confirmed') && (
            <Button size="small" danger onClick={() => updateStatus(r.id, 'cancelled')}>取消</Button>
          )}
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await axios.delete(`/api/reception/appointments/${r.id}`)
            fetchAll()
          }}>
            <Button size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    },
  ]

  return (
    <div>
      <Card
        title={`预约管理（${items.length}条）`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setOpen(true) }}>
          新增预约
        </Button>}
      >
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title="新增预约" open={open} onOk={handleSubmit} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="visitor_name" label="访客姓名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="visitor_company" label="单位/公司">
            <Input />
          </Form.Item>
          <Form.Item name="visitor_count" label="参观人数" initialValue={1}>
            <InputNumber min={1} max={200} />
          </Form.Item>
          <Form.Item name="visit_time" label="参观时间" rules={[{ required: true }]}>
            <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="preset_id" label="接待套餐（可选）">
            <Select allowClear options={presets.map(p => ({ label: p.name, value: p.id }))} />
          </Form.Item>
          <Form.Item name="contact" label="联系方式">
            <Input />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
