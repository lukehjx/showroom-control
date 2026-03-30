import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, Switch, Select, Space,
  Tag, Popconfirm, message, Tooltip, Row, Col
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import axios from 'axios'

interface NavPos {
  id: number
  robot_poi: string
  display_name: string
  terminal_id: number | null
  area_id: number | null
  aliases: string[]
  is_entry: boolean
  is_charger: boolean
}

interface RobotStatus {
  online: boolean
  poi_list: string[]
  current_poi: string
}

export default function NavPositions() {
  const [positions, setPositions] = useState<NavPos[]>([])
  const [robot, setRobot] = useState<RobotStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editPos, setEditPos] = useState<NavPos | null>(null)
  const [form] = Form.useForm()

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [posRes, robotRes] = await Promise.all([
        axios.get('/api/robot/positions'),
        axios.get('/api/robot/status'),
      ])
      setPositions(posRes.data.data || [])
      setRobot(robotRes.data.data)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const openAdd = () => {
    setEditPos(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (pos: NavPos) => {
    setEditPos(pos)
    form.setFieldsValue({ ...pos, aliases: (pos.aliases || []).join('，') })
    setModalOpen(true)
  }

  const handleDelete = async (id: number) => {
    await axios.delete(`/api/robot/positions/${id}`)
    message.success('已删除')
    fetchAll()
  }

  const handleTestNav = async (poi: string) => {
    try {
      await axios.post('/api/robot/navigate', { poi, wait_arrival: false })
      message.success(`已下发导航指令: ${poi}`)
    } catch {
      message.error('导航指令发送失败')
    }
  }

  const handleSubmit = async () => {
    const vals = await form.validateFields()
    const aliases = vals.aliases
      ? vals.aliases.split(/[，,]/).map((s: string) => s.trim()).filter(Boolean)
      : []
    const payload = { ...vals, aliases }
    try {
      if (editPos) {
        await axios.put(`/api/robot/positions/${editPos.id}`, payload)
        message.success('更新成功')
      } else {
        await axios.post('/api/robot/positions', payload)
        message.success('添加成功')
      }
      setModalOpen(false)
      fetchAll()
    } catch {
      message.error('保存失败')
    }
  }

  const columns = [
    {
      title: 'POI名称（机器人内）', dataIndex: 'robot_poi', key: 'robot_poi',
      render: (v: string) => <code style={{ color: '#00d4ff' }}>{v}</code>
    },
    { title: '展示名称', dataIndex: 'display_name', key: 'display_name' },
    {
      title: '别名（触发词）', dataIndex: 'aliases', key: 'aliases',
      render: (a: string[]) => (a || []).map(t => <Tag key={t} color="geekblue">{t}</Tag>)
    },
    {
      title: '标记', key: 'flags',
      render: (_: unknown, r: NavPos) => (
        <Space>
          {r.is_entry && <Tag color="green">入口</Tag>}
          {r.is_charger && <Tag color="orange">充电桩</Tag>}
        </Space>
      )
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, r: NavPos) => (
        <Space>
          <Tooltip title="测试导航（立即下发）">
            <Button
              size="small" icon={<RobotOutlined />}
              disabled={!robot?.online}
              onClick={() => handleTestNav(r.robot_poi)}
            >测试</Button>
          </Tooltip>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    },
  ]

  // 机器人上报的 POI 列表，过滤已映射的
  const unmapped = (robot?.poi_list || []).filter(
    poi => !positions.find(p => p.robot_poi === poi)
  )

  return (
    <div>
      {/* 机器人POI列表提示 */}
      {robot?.online && unmapped.length > 0 && (
        <Card size="small" style={{ marginBottom: 16, borderColor: '#faad14' }}
          title={<span style={{ color: '#faad14' }}>⚠️ 以下 POI 尚未映射（{unmapped.length}个）</span>}>
          <Row gutter={8}>
            {unmapped.map(poi => (
              <Col key={poi}>
                <Button size="small" type="dashed" onClick={() => {
                  form.setFieldsValue({ robot_poi: poi, display_name: poi })
                  setEditPos(null)
                  setModalOpen(true)
                }}>{poi} +映射</Button>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      <Card
        title={`点位映射管理（${positions.length}个）`}
        extra={
          <Space>
            <Tag color={robot?.online ? 'green' : 'red'}>
              机器人 {robot?.online ? '在线' : '离线'}
            </Tag>
            {robot?.online && robot.poi_list?.length > 0 && (
              <Tag color="blue">共 {robot.poi_list.length} 个POI</Tag>
            )}
            <Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>新增点位</Button>
          </Space>
        }
      >
        <Table
          dataSource={positions}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={false}
        />
      </Card>

      <Modal
        title={editPos ? '编辑点位' : '新增点位映射'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="robot_poi" label="POI名称（机器人地图中的名称）" rules={[{ required: true }]}>
            {robot?.poi_list?.length ? (
              <Select showSearch placeholder="从机器人POI列表选择或手动输入"
                options={robot.poi_list.map(p => ({ label: p, value: p }))}
                mode={undefined}
              />
            ) : <Input placeholder="如 reception、exhibit_a1" />}
          </Form.Item>
          <Form.Item name="display_name" label="展示名称（用于界面显示）" rules={[{ required: true }]}>
            <Input placeholder="如 前台接待区、A1展项" />
          </Form.Item>
          <Form.Item name="aliases" label="别名/触发词（多个用逗号分隔）"
            extra="语音识别到这些词时会导航到此点位">
            <Input placeholder="如 前台,接待处,入口" />
          </Form.Item>
          <Form.Item label="特殊标记">
            <Space>
              <Form.Item name="is_entry" valuePropName="checked" noStyle>
                <Switch checkedChildren="入口" unCheckedChildren="非入口" />
              </Form.Item>
              <Form.Item name="is_charger" valuePropName="checked" noStyle>
                <Switch checkedChildren="充电桩" unCheckedChildren="非充电桩" />
              </Form.Item>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
