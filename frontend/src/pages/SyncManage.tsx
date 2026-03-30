import { useEffect, useState } from 'react'
import { Row, Col, Button, Tag, Typography, Space, Table, message } from 'antd'
import { SyncOutlined } from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

const { Text } = Typography

interface SyncStatus {
  presets?: string[]
  preset_count?: number
  host_count?: number
  command_count?: number
  exhibit_count?: number
  commands?: string[]
  hosts?: string[]
}

interface SyncLog {
  id?: string
  created_at?: string
  type?: string
  status?: string
  message?: string
  duration?: number
}

const cardStyle: React.CSSProperties = {
  background: 'rgba(8,24,42,0.85)',
  border: '1px solid rgba(0,212,255,0.15)',
  borderRadius: 12,
  backdropFilter: 'blur(12px)',
  padding: 20,
  height: '100%',
}

export default function SyncManage() {
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({})
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([])
  const [syncing, setSyncing] = useState(false)

  const fetchData = () => {
    axios.get('/api/sync/status').then(r => setSyncStatus(r.data || {})).catch(() => {})
    axios.get('/api/sync/logs').then(r => {
      const data = r.data
      if (Array.isArray(data)) setSyncLogs(data)
      else if (data?.items) setSyncLogs(data.items)
    }).catch(() => {})
  }

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 10000)
    return () => clearInterval(timer)
  }, [])

  const handleFullSync = async () => {
    setSyncing(true)
    try {
      await axios.post('/api/sync/full')
      message.success('全量同步已触发')
      setTimeout(fetchData, 1500)
    } catch {
      message.error('同步失败，请重试')
    } finally {
      setSyncing(false)
    }
  }

  const presets: string[] = Array.isArray(syncStatus.presets) ? syncStatus.presets : []
  const commands: string[] = Array.isArray(syncStatus.commands) ? syncStatus.commands : []
  const hosts: string[] = Array.isArray(syncStatus.hosts) ? syncStatus.hosts : []
  const presetCount = syncStatus.preset_count ?? presets.length
  const hostCount = syncStatus.host_count ?? hosts.length
  const commandCount = syncStatus.command_count ?? commands.length
  const exhibitCount = syncStatus.exhibit_count ?? 0

  const statCards = [
    { label: '专场数量', value: presetCount, color: '#00d4ff' },
    { label: '展品话术', value: exhibitCount, color: '#39ff14' },
    { label: '主机设备', value: hostCount, color: '#ff7c00' },
    { label: '命令数量', value: commandCount, color: '#8ab4cc' },
    { label: '同步日志', value: syncLogs.length, color: '#722ed1' },
  ]

  const logColumns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => (
        <Text style={{ color: '#4a7fa0', fontSize: 12, fontFamily: 'monospace' }}>
          {v ? dayjs(v).format('MM-DD HH:mm:ss') : '--'}
        </Text>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (v: string) => (
        <Tag style={{
          background: 'rgba(0,212,255,0.1)',
          border: '1px solid rgba(0,212,255,0.3)',
          color: '#00d4ff',
          fontSize: 11,
        }}>
          {v || 'full'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => {
        const color = v === 'success' ? '#39ff14' : v === 'error' ? '#ff1744' : '#ff7c00'
        return (
          <Tag style={{
            background: color + '22',
            border: `1px solid ${color}44`,
            color,
            fontSize: 11,
          }}>
            {v || 'pending'}
          </Tag>
        )
      },
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      render: (v: string) => <Text style={{ color: '#e2f4ff', fontSize: 12 }}>{v || '--'}</Text>,
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 80,
      render: (v: number) => (
        <Text style={{ color: '#8ab4cc', fontSize: 12 }}>{v ? `${v}ms` : '--'}</Text>
      ),
    },
  ]

  return (
    <div style={{ color: '#e2f4ff' }}>
      {/* 顶部统计卡片 + 同步按钮 */}
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 16, marginBottom: 20 }}>
        {statCards.map((card, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              background: 'rgba(8,24,42,0.85)',
              border: '1px solid rgba(0,212,255,0.15)',
              borderRadius: 12,
              backdropFilter: 'blur(12px)',
              padding: '16px 20px',
            }}
          >
            <div style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8 }}>{card.label}</div>
            <div className="stat-value" style={{ color: card.color }}>{card.value}</div>
          </div>
        ))}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          paddingLeft: 8,
        }}>
          <Button
            type="primary"
            icon={<SyncOutlined spin={syncing} />}
            loading={syncing}
            onClick={handleFullSync}
            size="large"
            style={{
              background: 'rgba(0,212,255,0.15)',
              borderColor: '#00d4ff',
              color: '#00d4ff',
              height: 56,
              paddingLeft: 24,
              paddingRight: 24,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            全量同步
          </Button>
        </div>
      </div>

      {/* 中间三栏 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        {/* 左：专场列表 */}
        <Col span={8}>
          <div style={cardStyle}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#00d4ff', marginBottom: 16 }}>
              🎭 专场列表
            </div>
            {presets.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {presets.map((p: string) => (
                  <Tag
                    key={p}
                    style={{
                      background: 'rgba(0,212,255,0.1)',
                      border: '1px solid rgba(0,212,255,0.25)',
                      color: '#00d4ff',
                      borderRadius: 6,
                      fontSize: 13,
                      padding: '2px 10px',
                    }}
                  >
                    {p}
                  </Tag>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <Text style={{ color: '#4a7fa0', fontSize: 12 }}>
                  共 {presetCount} 个专场，点击"全量同步"获取详情
                </Text>
              </div>
            )}
          </div>
        </Col>

        {/* 中：主机设备 */}
        <Col span={8}>
          <div style={cardStyle}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#ff7c00', marginBottom: 16 }}>
              🖥 主机设备
            </div>
            {hosts.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {hosts.map((h: string, i: number) => (
                  <div
                    key={i}
                    style={{
                      padding: '6px 10px',
                      borderRadius: 6,
                      background: 'rgba(255,124,0,0.08)',
                      border: '1px solid rgba(255,124,0,0.2)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <span className="online-dot" style={{ background: '#ff7c00', animationDuration: '3s' }} />
                    <Text style={{ color: '#e2f4ff', fontSize: 13 }}>{h}</Text>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <div className="stat-value" style={{ color: '#ff7c00', marginBottom: 8 }}>
                  {hostCount}
                </div>
                <Text style={{ color: '#8ab4cc', fontSize: 13 }}>台主机设备</Text>
              </div>
            )}
          </div>
        </Col>

        {/* 右：命令列表 */}
        <Col span={8}>
          <div style={cardStyle}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#8ab4cc', marginBottom: 16 }}>
              ⚡ 命令列表
            </div>
            {commands.length > 0 ? (
              <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {commands.map((cmd: string, i: number) => (
                  <div
                    key={i}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 4,
                      background: 'rgba(0,212,255,0.04)',
                      border: '1px solid rgba(0,212,255,0.08)',
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: '#8ab4cc',
                    }}
                  >
                    {cmd}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <div className="stat-value" style={{ marginBottom: 8 }}>{commandCount}</div>
                <Text style={{ color: '#8ab4cc', fontSize: 13 }}>条可用命令</Text>
              </div>
            )}
          </div>
        </Col>
      </Row>

      {/* 底部同步日志表格 */}
      <div style={{
        background: 'rgba(8,24,42,0.85)',
        border: '1px solid rgba(0,212,255,0.15)',
        borderRadius: 12,
        backdropFilter: 'blur(12px)',
        padding: 20,
      }}>
        <Space style={{ marginBottom: 16 }} size={8}>
          <Text style={{ fontSize: 14, fontWeight: 600, color: '#00d4ff' }}>📋 同步日志</Text>
        </Space>
        <Table
          dataSource={syncLogs}
          columns={logColumns}
          rowKey={(r, i) => r.id || String(i)}
          pagination={{ pageSize: 10, size: 'small' }}
          size="small"
          style={{ background: 'transparent' }}
          rowClassName={(_, i) => i % 2 === 0 ? 'log-row-even' : ''}
        />
      </div>
    </div>
  )
}
