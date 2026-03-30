import { useEffect, useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Progress, Typography, Space } from 'antd'
import {
  DashboardOutlined,
  SettingOutlined,
  SyncOutlined,
  MessageOutlined,
  FileTextOutlined,
  EnvironmentOutlined,
  BranchesOutlined,
  CalendarOutlined,
  ScheduleOutlined,
  BellOutlined,
  UnorderedListOutlined,
  PlayCircleOutlined,
  BookOutlined,
} from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

const { Sider, Header, Content } = Layout
const { Text } = Typography

interface RobotStatus {
  state?: string
  battery?: number
  current_poi?: string
  online?: boolean
}

const menuItems = [
  {
    type: 'group' as const,
    label: '监控中心',
    children: [
      { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
    ],
  },
  {
    type: 'group' as const,
    label: '业务配置',
    children: [
      { key: '/presets', icon: <PlayCircleOutlined />, label: '接待套餐' },
      { key: '/exhibits', icon: <BookOutlined />, label: '展品话术' },
      { key: '/flows', icon: <BranchesOutlined />, label: '流程编辑' },
      { key: '/tours', icon: <EnvironmentOutlined />, label: '导览路线' },
      { key: '/positions', icon: <EnvironmentOutlined />, label: '导航点位' },
    ],
  },
  {
    type: 'group' as const,
    label: '运营管理',
    children: [
      { key: '/appointments', icon: <CalendarOutlined />, label: '预约管理' },
      { key: '/tasks', icon: <ScheduleOutlined />, label: '定时任务' },
      { key: '/notify', icon: <BellOutlined />, label: '通知分组' },
    ],
  },
  {
    type: 'group' as const,
    label: '数据管理',
    children: [
      { key: '/sync', icon: <SyncOutlined />, label: '数据同步' },
      { key: '/chat-logs', icon: <MessageOutlined />, label: '对话日志' },
      { key: '/logs', icon: <UnorderedListOutlined />, label: '操作日志' },
    ],
  },
  {
    type: 'group' as const,
    label: '系统',
    children: [
      { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
    ],
  },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [robotStatus, setRobotStatus] = useState<RobotStatus>({})
  const [clock, setClock] = useState(dayjs().format('HH:mm:ss'))

  // 实时时钟
  useEffect(() => {
    const timer = setInterval(() => {
      setClock(dayjs().format('HH:mm:ss'))
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // 轮询机器人状态
  useEffect(() => {
    const fetchStatus = () => {
      axios.get('/api/robot/status').then(res => {
        setRobotStatus(res.data || {})
      }).catch(() => {
        setRobotStatus(prev => ({ ...prev, online: false }))
      })
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const isOnline = robotStatus.online !== false && robotStatus.state !== undefined
  const battery = typeof robotStatus.battery === 'number' ? robotStatus.battery : null
  const batteryColor = battery !== null && battery < 20 ? '#ff1744' : '#39ff14'

  const stateLabel: Record<string, string> = {
    idle: '待机中',
    navigating: '导航中',
    speaking: '讲解中',
    charging: '充电中',
    error: '故障',
  }

  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <Layout style={{ minHeight: '100vh', background: '#04080f' }}>
      {/* 左侧导航 */}
      <Sider
        width={220}
        style={{
          background: '#04080f',
          borderRight: '1px solid rgba(0,212,255,0.1)',
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
          overflow: 'hidden',
        }}
      >
        {/* Logo 区 */}
        <div style={{
          padding: '20px 16px 16px',
          borderBottom: '1px solid rgba(0,212,255,0.1)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 22 }}>⚡</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#00d4ff', letterSpacing: 1 }}>
              展厅智控
            </span>
          </div>
          <div style={{ fontSize: 10, color: '#4a7fa0', letterSpacing: 2, paddingLeft: 30 }}>
            SHOWROOM CONTROL v1.0.0
          </div>
        </div>

        {/* 菜单 */}
        <div style={{ flex: 1, overflowY: 'auto', paddingTop: 8 }}>
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{
              background: 'transparent',
              border: 'none',
            }}
          />
        </div>

        {/* 底部版权 */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid rgba(0,212,255,0.08)',
          textAlign: 'center',
        }}>
          <Text style={{ fontSize: 11, color: '#4a7fa0' }}>Powered by Sidex</Text>
        </div>
      </Sider>

      {/* 右侧主区域 */}
      <Layout style={{ marginLeft: 220, background: '#04080f' }}>
        {/* 顶栏 */}
        <Header style={{
          background: '#080f1a',
          borderBottom: '1px solid rgba(0,212,255,0.1)',
          height: 56,
          lineHeight: '56px',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 99,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 24,
        }}>
          {/* 机器人状态 */}
          <Space align="center" size={8}>
            {isOnline
              ? <span className="online-dot" />
              : <span className="offline-dot" />
            }
            <Text style={{ color: isOnline ? '#39ff14' : '#4a7fa0', fontSize: 13 }}>
              {isOnline
                ? (stateLabel[robotStatus.state || ''] || '在线')
                : '离线'
              }
            </Text>
          </Space>

          {/* 电量 */}
          {battery !== null && (
            <Space align="center" size={6}>
              <Text style={{ color: '#8ab4cc', fontSize: 12 }}>电量</Text>
              <Progress
                percent={battery}
                size="small"
                showInfo={false}
                strokeColor={batteryColor}
                trailColor="rgba(0,212,255,0.1)"
                style={{ width: 80 }}
              />
              <Text style={{ color: batteryColor, fontSize: 12, minWidth: 32 }}>
                {battery}%
              </Text>
            </Space>
          )}

          {/* 当前POI */}
          {robotStatus.current_poi && (
            <Space align="center" size={4}>
              <Text style={{ color: '#4a7fa0', fontSize: 12 }}>📍</Text>
              <Text style={{ color: '#8ab4cc', fontSize: 12 }}>{robotStatus.current_poi}</Text>
            </Space>
          )}

          {/* 实时时钟 */}
          <Text style={{ color: '#00d4ff', fontFamily: 'monospace', fontSize: 14, letterSpacing: 1 }}>
            {clock}
          </Text>
        </Header>

        {/* 内容区 */}
        <Content style={{ padding: 24, minHeight: 'calc(100vh - 56px)', background: '#04080f' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
