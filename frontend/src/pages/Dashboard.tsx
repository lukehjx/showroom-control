import { useEffect, useState, useRef } from 'react'
import { Row, Col, Card, Tag, Button, Progress, Typography, Space, Divider } from 'antd'
import {
  StopOutlined,
  ThunderboltOutlined,
  HomeOutlined,
  PlayCircleOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

const { Text, Title } = Typography

interface RobotStatus {
  state?: string
  battery?: number
  current_poi?: string
  online?: boolean
}

interface SyncStatus {
  presets?: string[]
  preset_count?: number
  host_count?: number
  command_count?: number
  exhibit_count?: number
  commands?: string[]
  hosts?: string[]
}

interface Position {
  name: string
  id?: string
}

interface ChatLog {
  id?: string
  source?: string
  intent?: string
  created_at?: string
  text?: string
}

interface OpLog {
  id?: string
  created_at?: string
  level?: string
  action?: string
  result?: string
}

const stateLabel: Record<string, string> = {
  idle: '待机中',
  navigating: '导航中',
  speaking: '讲解中',
  charging: '充电中',
  error: '故障',
}

const stateLabelColor: Record<string, string> = {
  idle: '#8ab4cc',
  navigating: '#00d4ff',
  speaking: '#39ff14',
  charging: '#ff7c00',
  error: '#ff1744',
}

const levelColor: Record<string, string> = {
  info: '#00d4ff',
  warn: '#ff7c00',
  warning: '#ff7c00',
  error: '#ff1744',
  success: '#39ff14',
  debug: '#4a7fa0',
}

// SVG 机器人
function RobotSVG({ state }: { state?: string }) {
  const color = stateLabelColor[state || 'idle'] || '#8ab4cc'
  return (
    <svg width="80" height="100" viewBox="0 0 80 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* 天线 */}
      <line x1="40" y1="8" x2="40" y2="0" stroke={color} strokeWidth="2"/>
      <circle cx="40" cy="0" r="3" fill={color}/>
      {/* 头部 */}
      <rect x="18" y="8" width="44" height="30" rx="6" stroke={color} strokeWidth="2" fill="rgba(0,212,255,0.05)"/>
      {/* 眼睛 */}
      <circle cx="30" cy="22" r="4" fill={color} opacity="0.8"/>
      <circle cx="50" cy="22" r="4" fill={color} opacity="0.8"/>
      {/* 嘴 */}
      <path d="M28 32 Q40 38 52 32" stroke={color} strokeWidth="1.5" fill="none"/>
      {/* 颈部 */}
      <line x1="40" y1="38" x2="40" y2="44" stroke={color} strokeWidth="2"/>
      {/* 躯干 */}
      <rect x="14" y="44" width="52" height="36" rx="6" stroke={color} strokeWidth="2" fill="rgba(0,212,255,0.05)"/>
      {/* 胸口圆形装饰 */}
      <circle cx="40" cy="62" r="8" stroke={color} strokeWidth="1.5" fill="none"/>
      <circle cx="40" cy="62" r="3" fill={color} opacity="0.6"/>
      {/* 左臂 */}
      <rect x="2" y="46" width="12" height="28" rx="6" stroke={color} strokeWidth="1.5" fill="rgba(0,212,255,0.03)"/>
      {/* 右臂 */}
      <rect x="66" y="46" width="12" height="28" rx="6" stroke={color} strokeWidth="1.5" fill="rgba(0,212,255,0.03)"/>
      {/* 左腿 */}
      <rect x="18" y="80" width="16" height="18" rx="4" stroke={color} strokeWidth="1.5" fill="rgba(0,212,255,0.03)"/>
      {/* 右腿 */}
      <rect x="46" y="80" width="16" height="18" rx="4" stroke={color} strokeWidth="1.5" fill="rgba(0,212,255,0.03)"/>
    </svg>
  )
}

export default function Dashboard() {
  const [robotStatus, setRobotStatus] = useState<RobotStatus>({})
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({})
  const [positions, setPositions] = useState<Position[]>([])
  const [chatLogs, setChatLogs] = useState<ChatLog[]>([])
  const [opLogs, setOpLogs] = useState<OpLog[]>([])
  const logRef = useRef<HTMLDivElement>(null)

  const fetchAll = () => {
    axios.get('/api/robot/status').then(r => setRobotStatus(r.data || {})).catch(() => {})
    axios.get('/api/sync/status').then(r => setSyncStatus(r.data || {})).catch(() => {})
    axios.get('/api/robot/positions').then(r => {
      const data = r.data
      if (Array.isArray(data)) setPositions(data)
      else if (data?.positions) setPositions(data.positions)
    }).catch(() => {})
    axios.get('/api/logs/chats?limit=5').then(r => {
      const data = r.data
      if (Array.isArray(data)) setChatLogs(data)
      else if (data?.items) setChatLogs(data.items)
    }).catch(() => {})
    axios.get('/api/logs/operations?limit=20').then(r => {
      const data = r.data
      if (Array.isArray(data)) setOpLogs(data)
      else if (data?.items) setOpLogs(data.items)
    }).catch(() => {})
  }

  useEffect(() => {
    fetchAll()
    const timer = setInterval(fetchAll, 5000)
    return () => clearInterval(timer)
  }, [])

  const sendChat = (text: string) => {
    axios.post('/api/chat/input', { text }).catch(() => {})
  }

  const isOnline = robotStatus.online !== false && robotStatus.state !== undefined
  const battery = typeof robotStatus.battery === 'number' ? robotStatus.battery : null
  const batteryColor = battery !== null && battery < 20 ? '#ff1744' : '#39ff14'
  const state = robotStatus.state || 'idle'
  const stateColor = stateLabelColor[state] || '#8ab4cc'

  const presets: string[] = Array.isArray(syncStatus.presets) ? syncStatus.presets : []
  const presetCount = syncStatus.preset_count ?? presets.length
  const hostCount = syncStatus.host_count ?? 0
  const commandCount = syncStatus.command_count ?? 0
  const exhibitCount = syncStatus.exhibit_count ?? 0

  const cardStyle: React.CSSProperties = {
    background: 'rgba(8,24,42,0.85)',
    border: '1px solid rgba(0,212,255,0.15)',
    borderRadius: 12,
    backdropFilter: 'blur(12px)',
    height: '100%',
  }

  // 指标卡数据
  const statCards = [
    {
      label: '机器人状态',
      value: stateLabel[state] || state,
      color: stateColor,
      extra: isOnline
        ? <span className="online-dot" style={{ marginLeft: 6 }} />
        : <span className="offline-dot" style={{ marginLeft: 6 }} />,
    },
    {
      label: '电量',
      value: battery !== null ? `${battery}%` : '--',
      color: batteryColor,
      extra: battery !== null
        ? <Progress percent={battery} size="small" showInfo={false} strokeColor={batteryColor}
            trailColor="rgba(0,212,255,0.1)" style={{ width: 80, marginTop: 4 }} />
        : null,
    },
    {
      label: '当前点位',
      value: robotStatus.current_poi || '--',
      color: '#e2f4ff',
    },
    {
      label: '专场数量',
      value: String(presetCount),
      color: '#00d4ff',
    },
    {
      label: '主机设备',
      value: String(hostCount),
      color: '#00d4ff',
    },
    {
      label: '命令数',
      value: String(commandCount),
      color: '#00d4ff',
    },
  ]

  return (
    <div style={{ color: '#e2f4ff' }}>
      {/* 区域1：指标卡 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        {statCards.map((card, i) => (
          <Col span={4} key={i}>
            <div style={cardStyle}>
              <div style={{ padding: '16px 20px' }}>
                <div style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8 }}>{card.label}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span className="stat-value" style={{ color: card.color, fontSize: 22 }}>
                    {card.value}
                  </span>
                  {card.extra}
                </div>
                {card.extra && typeof card.extra !== 'string' && card.label === '电量' && card.extra}
              </div>
            </div>
          </Col>
        ))}
      </Row>

      {/* 区域2：三列主内容 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        {/* 左列：机器人实时卡 */}
        <Col span={8}>
          <div style={{ ...cardStyle, padding: 20 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#00d4ff', marginBottom: 16 }}>
              🤖 机器人实时状态
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
              <RobotSVG state={state} />
            </div>
            <div style={{ textAlign: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 20, fontWeight: 700, color: stateColor }}>
                {stateLabel[state] || state}
              </span>
            </div>
            {robotStatus.current_poi && (
              <div style={{ textAlign: 'center', marginBottom: 12, color: '#8ab4cc', fontSize: 13 }}>
                📍 {robotStatus.current_poi}
              </div>
            )}
            {battery !== null && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text style={{ fontSize: 12, color: '#8ab4cc' }}>电量</Text>
                  <Text style={{ fontSize: 12, color: batteryColor }}>{battery}%</Text>
                </div>
                <Progress
                  percent={battery}
                  size="small"
                  showInfo={false}
                  strokeColor={batteryColor}
                  trailColor="rgba(0,212,255,0.1)"
                />
              </div>
            )}
            <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
            <Row gutter={8}>
              <Col span={8}>
                <Button
                  block size="small"
                  danger
                  icon={<StopOutlined />}
                  onClick={() => sendChat('停止')}
                  style={{ fontSize: 12 }}
                >
                  停止
                </Button>
              </Col>
              <Col span={8}>
                <Button
                  block size="small"
                  icon={<ThunderboltOutlined />}
                  onClick={() => sendChat('去充电')}
                  style={{ background: 'rgba(0,212,255,0.1)', borderColor: 'rgba(0,212,255,0.3)', color: '#00d4ff', fontSize: 12 }}
                >
                  去充电
                </Button>
              </Col>
              <Col span={8}>
                <Button
                  block size="small"
                  icon={<HomeOutlined />}
                  onClick={() => sendChat('回入口')}
                  style={{ background: 'rgba(0,212,255,0.1)', borderColor: 'rgba(0,212,255,0.3)', color: '#00d4ff', fontSize: 12 }}
                >
                  回入口
                </Button>
              </Col>
            </Row>
          </div>
        </Col>

        {/* 中列：专场&设备 */}
        <Col span={8}>
          <div style={{ ...cardStyle, padding: 20 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#00d4ff', marginBottom: 16 }}>
              🎭 专场 &amp; 点位
            </div>
            <div style={{ marginBottom: 12 }}>
              <Text style={{ fontSize: 12, color: '#8ab4cc' }}>当前专场</Text>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#00d4ff', marginTop: 4 }}>
                {presets[0] || '--'}
              </div>
            </div>
            <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
            <div style={{ marginBottom: 12 }}>
              <Text style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8, display: 'block' }}>
                专场列表（点击切换）
              </Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {presets.slice(0, 8).map((p: string) => (
                  <Tag
                    key={p}
                    style={{
                      cursor: 'pointer',
                      background: 'rgba(0,212,255,0.1)',
                      border: '1px solid rgba(0,212,255,0.3)',
                      color: '#00d4ff',
                      borderRadius: 6,
                    }}
                    onClick={() => sendChat(`切换到${p}专场`)}
                  >
                    {p}
                  </Tag>
                ))}
                {presets.length === 0 && (
                  <Text style={{ color: '#4a7fa0', fontSize: 12 }}>暂无专场数据</Text>
                )}
              </div>
            </div>
            <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
            <div>
              <Text style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8, display: 'block' }}>
                导航点位
              </Text>
              <div style={{ maxHeight: 140, overflowY: 'auto' }}>
                {positions.length > 0 ? positions.map((p, i) => (
                  <div
                    key={p.id || i}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 4,
                      marginBottom: 2,
                      background: 'rgba(0,212,255,0.05)',
                      border: '1px solid rgba(0,212,255,0.08)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span style={{ color: '#4a7fa0', fontSize: 11 }}>📍</span>
                    <Text style={{ fontSize: 12, color: '#e2f4ff' }}>{p.name}</Text>
                  </div>
                )) : (
                  <Text style={{ color: '#4a7fa0', fontSize: 12 }}>暂无点位数据</Text>
                )}
              </div>
            </div>
          </div>
        </Col>

        {/* 右列：快捷控制 */}
        <Col span={8}>
          <div style={{ ...cardStyle, padding: 20 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#00d4ff', marginBottom: 16 }}>
              ⚡ 快捷控制
            </div>
            <div style={{ marginBottom: 16 }}>
              <Text style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8, display: 'block' }}>
                组策略
              </Text>
              <Row gutter={[8, 8]}>
                {[
                  { label: '一键开馆', text: '一键开馆', color: '#39ff14' },
                  { label: '一键关馆', text: '一键关馆', color: '#ff1744' },
                  { label: '灯全开', text: '所有灯光全开', color: '#ff7c00' },
                  { label: '灯全关', text: '所有灯光全关', color: '#4a7fa0' },
                ].map(btn => (
                  <Col span={12} key={btn.label}>
                    <Button
                      block size="small"
                      onClick={() => sendChat(btn.text)}
                      style={{
                        background: 'rgba(8,24,42,0.6)',
                        borderColor: btn.color + '66',
                        color: btn.color,
                        fontSize: 12,
                      }}
                    >
                      {btn.label}
                    </Button>
                  </Col>
                ))}
              </Row>
            </div>
            <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
            <div style={{ marginBottom: 16 }}>
              <Text style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8, display: 'block' }}>
                机器人快捷
              </Text>
              <Row gutter={[8, 8]}>
                {[
                  { label: '开始导览', text: '开始导览', icon: <PlayCircleOutlined /> },
                  { label: '回入口', text: '回入口', icon: <HomeOutlined /> },
                  { label: '去充电', text: '去充电', icon: <ThunderboltOutlined /> },
                ].map(btn => (
                  <Col span={8} key={btn.label}>
                    <Button
                      block size="small"
                      icon={btn.icon}
                      onClick={() => sendChat(btn.text)}
                      style={{
                        background: 'rgba(0,212,255,0.08)',
                        borderColor: 'rgba(0,212,255,0.25)',
                        color: '#00d4ff',
                        fontSize: 11,
                      }}
                    >
                      {btn.label}
                    </Button>
                  </Col>
                ))}
              </Row>
            </div>
            <Divider style={{ borderColor: 'rgba(0,212,255,0.1)', margin: '12px 0' }} />
            <div>
              <Text style={{ fontSize: 12, color: '#8ab4cc', marginBottom: 8, display: 'block' }}>
                最近对话
              </Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {chatLogs.length > 0 ? chatLogs.slice(0, 5).map((log, i) => (
                  <div
                    key={log.id || i}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 4,
                      background: 'rgba(0,212,255,0.04)',
                      border: '1px solid rgba(0,212,255,0.08)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <Space size={4}>
                      <Tag style={{
                        fontSize: 10, padding: '0 4px',
                        background: 'rgba(0,212,255,0.1)',
                        border: '1px solid rgba(0,212,255,0.2)',
                        color: '#8ab4cc',
                        margin: 0,
                      }}>
                        {log.source || '用户'}
                      </Tag>
                      <Text style={{ fontSize: 11, color: '#e2f4ff' }}>
                        {log.intent || log.text || '--'}
                      </Text>
                    </Space>
                    <Text style={{ fontSize: 10, color: '#4a7fa0' }}>
                      {log.created_at ? dayjs(log.created_at).format('HH:mm') : ''}
                    </Text>
                  </div>
                )) : (
                  <Text style={{ color: '#4a7fa0', fontSize: 12 }}>暂无对话记录</Text>
                )}
              </div>
            </div>
          </div>
        </Col>
      </Row>

      {/* 区域3：底部实时日志流 */}
      <div style={{
        ...cardStyle,
        padding: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <Text style={{ fontSize: 14, fontWeight: 600, color: '#00d4ff' }}>
            📋 实时操作日志
          </Text>
          <Space align="center" size={6}>
            <span className="online-dot" style={{ width: 6, height: 6 }} />
            <Text style={{ fontSize: 11, color: '#4a7fa0' }}>每5秒刷新</Text>
          </Space>
        </div>
        <div
          ref={logRef}
          style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}
        >
          {opLogs.length > 0 ? opLogs.map((log, i) => (
            <div
              key={log.id || i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 8px',
                borderRadius: 4,
                background: i % 2 === 0 ? 'rgba(0,212,255,0.03)' : 'transparent',
                fontSize: 12,
              }}
            >
              <Text style={{ color: '#4a7fa0', fontFamily: 'monospace', minWidth: 56 }}>
                {log.created_at ? dayjs(log.created_at).format('HH:mm:ss') : '--:--:--'}
              </Text>
              <Tag
                style={{
                  fontSize: 10,
                  padding: '0 6px',
                  background: (levelColor[log.level?.toLowerCase() || ''] || '#4a7fa0') + '22',
                  border: `1px solid ${levelColor[log.level?.toLowerCase() || ''] || '#4a7fa0'}44`,
                  color: levelColor[log.level?.toLowerCase() || ''] || '#4a7fa0',
                  margin: 0,
                  minWidth: 44,
                  textAlign: 'center',
                }}
              >
                {(log.level || 'info').toUpperCase()}
              </Tag>
              <Text style={{ color: '#e2f4ff', flex: 1 }}>{log.action || '--'}</Text>
              <Text style={{ color: '#8ab4cc' }}>{log.result || ''}</Text>
            </div>
          )) : (
            <Text style={{ color: '#4a7fa0', fontSize: 12, padding: '8px' }}>暂无日志数据</Text>
          )}
        </div>
      </div>
    </div>
  )
}
