import { useEffect, useState } from 'react'
import { Card, Table, Button, Select, Space, Tag, Badge, Popconfirm, message, Tooltip } from 'antd'
import { ReloadOutlined, DeleteOutlined } from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

interface Log {
  id: number; level: string; action: string; detail: string | null
  operator: string | null; result: string | null; created_at: number
}

const LEVEL_COLOR: Record<string, string> = {
  info: 'blue', warn: 'orange', error: 'red', debug: 'default'
}

export default function OperationLogs() {
  const [logs, setLogs] = useState<Log[]>([])
  const [loading, setLoading] = useState(false)
  const [level, setLevel] = useState<string | undefined>()

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const r = await axios.get('/api/logs/operations', { params: { limit: 200, level } })
      setLogs(r.data.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchLogs() }, [level])

  const columns = [
    {
      title: '级别', dataIndex: 'level', key: 'level', width: 80,
      render: (v: string) => <Tag color={LEVEL_COLOR[v] || 'default'}>{v?.toUpperCase()}</Tag>
    },
    { title: '操作', dataIndex: 'action', key: 'action', width: 200 },
    {
      title: '详情', dataIndex: 'detail', key: 'detail',
      render: (v: string) => <Tooltip title={v}><span>{v ? v.slice(0, 60) + (v.length > 60 ? '...' : '') : '-'}</span></Tooltip>
    },
    { title: '操作者', dataIndex: 'operator', key: 'op', width: 120, render: (v: string) => v || '系统' },
    {
      title: '结果', dataIndex: 'result', key: 'result', width: 100,
      render: (v: string) => v === 'success'
        ? <Badge status="success" text="成功" />
        : v === 'failed'
          ? <Badge status="error" text="失败" />
          : v || '-'
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'time', width: 160,
      render: (v: number) => dayjs(v).format('MM-DD HH:mm:ss')
    },
  ]

  return (
    <Card
      title={`操作日志（${logs.length}条）`}
      extra={
        <Space>
          <Select allowClear placeholder="日志级别" style={{ width: 120 }}
            options={[
              { label: 'INFO', value: 'info' }, { label: 'WARN', value: 'warn' },
              { label: 'ERROR', value: 'error' }, { label: 'DEBUG', value: 'debug' }
            ]}
            onChange={setLevel}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchLogs}>刷新</Button>
          <Popconfirm title="清理30天前的日志？" onConfirm={async () => {
            await axios.delete('/api/logs/operations?days=30')
            message.success('已清理')
            fetchLogs()
          }}>
            <Button danger icon={<DeleteOutlined />}>清理旧日志</Button>
          </Popconfirm>
        </Space>
      }
    >
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 50, showTotal: t => `共 ${t} 条` }}
      />
    </Card>
  )
}
