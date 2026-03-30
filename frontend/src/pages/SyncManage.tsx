import { useEffect, useState } from 'react'
import { Card, Button, Table, Tag, Space, Statistic, Row, Col, message, Spin, Badge } from 'antd'
import { SyncOutlined, CheckCircleOutlined, CloseCircleOutlined, DatabaseOutlined } from '@ant-design/icons'
import axios from 'axios'

interface SyncStatus {
  counts: { specials: number; terminals: number; resources: number; commands: number }
  current_special: { id: number; name: string } | null
  recent_logs: Array<{
    type: string; count: number; status: string; error: string | null; time: string
  }>
}

const TYPE_LABEL: Record<string, string> = {
  specials: '专场数据', areas: '展区列表', terminals: '主机设备', commands: '组策略命令', all: '全量同步'
}

export default function SyncManage() {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const fetchStatus = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/sync/status')
      setStatus(res.data.data)
    } catch {
      message.error('获取同步状态失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSyncAll = async () => {
    setSyncing(true)
    try {
      await axios.post('/api/sync/all')
      message.loading({ content: '同步任务已启动，约15秒完成...', duration: 4 })
      setTimeout(fetchStatus, 5000)
      setTimeout(fetchStatus, 12000)
    } catch {
      message.error('启动同步失败')
    } finally {
      setTimeout(() => setSyncing(false), 15000)
    }
  }

  useEffect(() => { fetchStatus() }, [])

  const columns = [
    {
      title: '同步类型', dataIndex: 'type', key: 'type',
      render: (t: string) => <Tag color="blue">{TYPE_LABEL[t] || t}</Tag>
    },
    { title: '记录数', dataIndex: 'count', key: 'count' },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => s === 'success'
        ? <Badge status="success" text="成功" />
        : <Badge status="error" text="失败" />
    },
    { title: '错误信息', dataIndex: 'error', key: 'error', render: (e: string | null) => e || '-' },
    {
      title: '时间', dataIndex: 'time', key: 'time',
      render: (t: string) => new Date(t).toLocaleString('zh-CN')
    },
  ]

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={5}>
          <Card><Statistic title="专场数量" value={status?.counts.specials ?? '-'} prefix={<DatabaseOutlined />} /></Card>
        </Col>
        <Col span={5}>
          <Card><Statistic title="主机设备" value={status?.counts.terminals ?? '-'} /></Card>
        </Col>
        <Col span={5}>
          <Card><Statistic title="资源文件" value={status?.counts.resources ?? '-'} /></Card>
        </Col>
        <Col span={5}>
          <Card><Statistic title="组策略命令" value={status?.counts.commands ?? '-'} /></Card>
        </Col>
        <Col span={4}>
          <Card>
            <div style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 4 }}>当前专场</div>
            <div style={{ color: '#00d4ff', fontWeight: 600, fontSize: 13 }}>
              {status?.current_special?.name || '未设置'}
            </div>
          </Card>
        </Col>
      </Row>

      <Card
        title="数据同步管理"
        extra={
          <Space>
            <Button icon={<SyncOutlined spin={loading} />} onClick={fetchStatus}>刷新</Button>
            <Button
              type="primary"
              icon={<SyncOutlined spin={syncing} />}
              onClick={handleSyncAll}
              loading={syncing}
            >
              全量同步
            </Button>
          </Space>
        }
      >
        <Spin spinning={loading}>
          <div style={{ marginBottom: 16, color: '#8ab4cc', fontSize: 13 }}>
            从中控云平台同步：专场、展区、主机、资源、组策略命令等数据。同步后本地数据库更新，机器人对话即可使用最新配置。
          </div>
          <Table
            dataSource={status?.recent_logs || []}
            columns={columns}
            rowKey={(r, i) => String(i)}
            pagination={false}
            size="small"
          />
        </Spin>
      </Card>
    </div>
  )
}
