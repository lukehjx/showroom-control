import { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic, Progress, Badge, Space, Button, Tag, Descriptions, Empty } from 'antd'
import { RobotOutlined, SyncOutlined, ThunderboltOutlined, EnvironmentOutlined, PlayCircleOutlined } from '@ant-design/icons'
import axios from 'axios'

export default function Dashboard() {
  const [robot, setRobot] = useState<any>(null)
  const [syncStatus, setSyncStatus] = useState<any>(null)

  const refresh = async () => {
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/robot/status'),
        axios.get('/api/sync/status'),
      ])
      setRobot(r1.data.data)
      setSyncStatus(r2.data.data)
    } catch {}
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [])

  const statusColor = { idle: '#00d4ff', navigating: '#faad14', speaking: '#52c41a', charging: '#a0d911', touring: '#1677ff' }

  return (
    <div>
      <Row gutter={[16, 16]}>
        {/* 机器人状态卡 */}
        <Col span={8}>
          <Card
            className="glass-card"
            title={<Space><RobotOutlined style={{ color: '#00d4ff' }} />机器人状态</Space>}
            extra={<Badge status={robot?.online ? 'success' : 'error'} text={robot?.online ? '在线' : '离线'} />}
          >
            {robot ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="SN">{robot.sn}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={statusColor[robot.status as keyof typeof statusColor] || '#666'}>
                    {robot.status || 'idle'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="当前点位">
                  {robot.current_poi || <span style={{ color: '#4a7fa0' }}>未知</span>}
                </Descriptions.Item>
                <Descriptions.Item label="电量">
                  <Progress
                    percent={robot.battery}
                    size="small"
                    strokeColor={robot.battery > 20 ? '#52c41a' : '#ff4d4f'}
                    style={{ marginBottom: 0 }}
                  />
                </Descriptions.Item>
              </Descriptions>
            ) : <Empty description="暂无数据" />}

            <Space style={{ marginTop: 16 }}>
              <Button size="small" onClick={() => axios.post('/api/robot/stop')}>停止</Button>
              <Button size="small" onClick={() => axios.post('/api/robot/charge')}>去充电</Button>
            </Space>
          </Card>
        </Col>

        {/* 数据同步状态 */}
        <Col span={8}>
          <Card
            className="glass-card"
            title={<Space><SyncOutlined style={{ color: '#00d4ff' }} />数据同步</Space>}
            extra={<Button size="small" type="primary" onClick={() => axios.post('/api/sync/all').then(refresh)}>同步</Button>}
          >
            {syncStatus ? (
              <>
                <Row gutter={16}>
                  {Object.entries(syncStatus.counts || {}).map(([key, val]) => (
                    <Col span={12} key={key}>
                      <Statistic
                        title={key}
                        value={val as number}
                        valueStyle={{ fontSize: 20, color: '#00d4ff' }}
                      />
                    </Col>
                  ))}
                </Row>
                {syncStatus.current_special && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(0,212,255,0.08)', borderRadius: 6 }}>
                    <span style={{ color: '#8ab4cc', fontSize: 12 }}>当前专场：</span>
                    <span style={{ color: '#00d4ff', fontWeight: 600 }}>{syncStatus.current_special.name}</span>
                  </div>
                )}
              </>
            ) : <Empty description="暂无同步数据" />}
          </Card>
        </Col>

        {/* 快捷控制 */}
        <Col span={8}>
          <Card className="glass-card" title={<Space><ThunderboltOutlined style={{ color: '#00d4ff' }} />快捷控制</Space>}>
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <Button
                block
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => axios.post('/api/chat/input', { text: '开始参观', source: 'admin', session_key: 'admin' })}
              >
                开始自动导览
              </Button>
              <Button block onClick={() => axios.post('/api/chat/input', { text: '一键开馆', source: 'admin', session_key: 'admin' })}>
                一键开馆
              </Button>
              <Button block onClick={() => axios.post('/api/chat/input', { text: '一键关馆', source: 'admin', session_key: 'admin' })}>
                一键关馆
              </Button>
              <Button block onClick={() => axios.post('/api/robot/charge')}>
                机器人回充
              </Button>
              <Button block onClick={() => axios.post('/api/chat/input', { text: '回入口', source: 'admin', session_key: 'admin' })}>
                机器人回入口
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 近期同步日志 */}
        <Col span={24}>
          <Card className="glass-card" title="近期同步记录">
            {syncStatus?.recent_logs?.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {syncStatus.recent_logs.map((log: any, i: number) => (
                  <Tag key={i} color={log.status === 'success' ? 'success' : 'error'}>
                    {log.type} · {log.count}条 · {new Date(log.time).toLocaleTimeString()}
                  </Tag>
                ))}
              </div>
            ) : <Empty description="暂无同步记录" />}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
