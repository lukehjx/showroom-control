import { useEffect, useState } from 'react'
import { Card, Table, Button, Select, Space, Tag, Badge, Tooltip } from 'antd'
import { ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

interface ChatLog {
  id: number; source: string; input_text: string; intent: string | null
  response: string | null; success: boolean; duration_ms: number | null; created_at: number
}

const SOURCE_COLOR: Record<string, string> = {
  robot: 'green', wecom: 'blue', api: 'orange'
}

const INTENT_LABEL: Record<string, string> = {
  navigate: '导航',
  speak: '讲解',
  open_hall: '开馆',
  close_hall: '闭馆',
  tour: '导览',
  reception: '接待',
  query_status: '状态查询',
  command: '设备控制',
  unknown: '未识别',
}

export default function ChatLogs() {
  const [logs, setLogs] = useState<ChatLog[]>([])
  const [loading, setLoading] = useState(false)
  const [source, setSource] = useState<string | undefined>()

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const r = await axios.get('/api/logs/chats', { params: { limit: 100, source } })
      setLogs(r.data.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchLogs() }, [source])

  const columns = [
    {
      title: '来源', dataIndex: 'source', key: 'source', width: 80,
      render: (v: string) => <Tag color={SOURCE_COLOR[v] || 'default'}>{v}</Tag>
    },
    {
      title: '输入', dataIndex: 'input_text', key: 'input',
      render: (v: string) => <Tooltip title={v}><span>{v ? v.slice(0, 40) + (v.length > 40 ? '...' : '') : '-'}</span></Tooltip>
    },
    {
      title: '识别意图', dataIndex: 'intent', key: 'intent', width: 100,
      render: (v: string) => v ? <Tag color="geekblue">{INTENT_LABEL[v] || v}</Tag> : '-'
    },
    {
      title: '回复', dataIndex: 'response', key: 'response',
      render: (v: string) => <Tooltip title={v}><span>{v ? v.slice(0, 40) + (v.length > 40 ? '...' : '') : '-'}</span></Tooltip>
    },
    {
      title: '耗时', dataIndex: 'duration_ms', key: 'dur', width: 80,
      render: (v: number) => v ? `${v}ms` : '-'
    },
    {
      title: '结果', dataIndex: 'success', key: 'ok', width: 80,
      render: (v: boolean) => <Badge status={v ? 'success' : 'error'} text={v ? '成功' : '失败'} />
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'time', width: 140,
      render: (v: number) => dayjs(v).format('MM-DD HH:mm:ss')
    },
  ]

  // 统计
  const total = logs.length
  const successRate = total > 0
    ? Math.round(logs.filter(l => l.success).length / total * 100) : 0

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space size={32}>
          <span>总对话 <strong style={{ color: '#00d4ff' }}>{total}</strong> 次</span>
          <span>成功率 <strong style={{ color: successRate > 80 ? '#52c41a' : '#faad14' }}>{successRate}%</strong></span>
          <span>机器人 <strong>{logs.filter(l => l.source === 'robot').length}</strong> 次</span>
          <span>企微 <strong>{logs.filter(l => l.source === 'wecom').length}</strong> 次</span>
          <span>未识别 <strong style={{ color: '#ff4d4f' }}>{logs.filter(l => l.intent === 'unknown').length}</strong> 次</span>
        </Space>
      </Card>

      <Card
        title={<Space><RobotOutlined />对话记录</Space>}
        extra={
          <Space>
            <Select allowClear placeholder="来源" style={{ width: 100 }}
              options={[
                { label: '机器人', value: 'robot' }, { label: '企微', value: 'wecom' }, { label: 'API', value: 'api' }
              ]}
              onChange={setSource}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchLogs}>刷新</Button>
          </Space>
        }
      >
        <Table
          dataSource={logs}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 50 }}
          rowClassName={r => r.success ? '' : 'ant-table-row-danger'}
        />
      </Card>
    </div>
  )
}
