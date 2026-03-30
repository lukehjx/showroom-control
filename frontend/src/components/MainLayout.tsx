import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Badge, Tooltip, Space } from 'antd'
import {
  DashboardOutlined, RocketOutlined, ReadOutlined, ApartmentOutlined,
  CompassOutlined, EnvironmentOutlined, CalendarOutlined, ClockCircleOutlined,
  SyncOutlined, BellOutlined, FileTextOutlined, MessageOutlined,
  SettingOutlined, RobotOutlined, ThunderboltOutlined
} from '@ant-design/icons'
import { useEffect, useState } from 'react'
import axios from 'axios'

const { Sider, Content, Header } = Layout

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '系统监控' },
  { key: '/presets', icon: <RocketOutlined />, label: '接待套餐' },
  { key: '/exhibits', icon: <ReadOutlined />, label: '展项讲解' },
  { key: '/flows', icon: <ApartmentOutlined />, label: '流程编排' },
  { key: '/tours', icon: <CompassOutlined />, label: '导览路线' },
  { key: '/positions', icon: <EnvironmentOutlined />, label: '点位映射' },
  { key: '/appointments', icon: <CalendarOutlined />, label: '预约管理' },
  { key: '/tasks', icon: <ClockCircleOutlined />, label: '定时任务' },
  { key: '/sync', icon: <SyncOutlined />, label: '数据同步' },
  { key: '/notify', icon: <BellOutlined />, label: '通知群配置' },
  { key: '/chat-logs', icon: <MessageOutlined />, label: '对话记录' },
  { key: '/logs', icon: <FileTextOutlined />, label: '操作日志' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
]

export default function MainLayout() {
  const nav = useNavigate()
  const loc = useLocation()
  const [robotStatus, setRobotStatus] = useState<any>(null)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get('/api/robot/status')
        setRobotStatus(res.data.data)
      } catch {}
    }
    fetchStatus()
    const timer = setInterval(fetchStatus, 5000)
    return () => clearInterval(timer)
  }, [])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={200} style={{ background: '#080f1a', borderRight: '1px solid rgba(0,212,255,0.1)' }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px', borderBottom: '1px solid rgba(0,212,255,0.1)' }}>
          <div style={{ color: '#00d4ff', fontSize: 16, fontWeight: 700, letterSpacing: 2 }}>
            <ThunderboltOutlined /> 展厅智控
          </div>
          <div style={{ color: '#4a7fa0', fontSize: 11, marginTop: 4 }}>SHOWROOM CONTROL</div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[loc.pathname]}
          items={menuItems}
          onClick={({ key }) => nav(key)}
          style={{ background: '#080f1a', border: 'none' }}
        />
      </Sider>

      <Layout>
        {/* 顶栏 */}
        <Header style={{
          background: '#0a1628',
          borderBottom: '1px solid rgba(0,212,255,0.1)',
          padding: '0 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between'
        }}>
          <div style={{ color: '#8ab4cc', fontSize: 13 }}>
            {menuItems.find(m => m.key === loc.pathname)?.label || '展厅智控系统'}
          </div>
          {/* 机器人状态指示 */}
          <Space size={16}>
            {robotStatus && (
              <Tooltip title={`${robotStatus.status} | POI: ${robotStatus.current_poi || '-'}`}>
                <Space>
                  <RobotOutlined style={{ color: robotStatus.online ? '#00d4ff' : '#4a7fa0' }} />
                  <span style={{ color: robotStatus.online ? '#00d4ff' : '#4a7fa0', fontSize: 12 }}>
                    {robotStatus.online ? '在线' : '离线'}
                  </span>
                  {robotStatus.online && (
                    <Badge
                      count={`${robotStatus.battery}%`}
                      style={{
                        background: robotStatus.battery > 20 ? '#52c41a' : '#ff4d4f',
                        fontSize: 10
                      }}
                    />
                  )}
                </Space>
              </Tooltip>
            )}
            <div style={{ color: '#4a7fa0', fontSize: 12 }}>
              robot.sidex.cn
            </div>
          </Space>
        </Header>

        <Content style={{ padding: 24, background: '#0d1b2a', overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
