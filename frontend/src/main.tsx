import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#00d4ff',
          colorBgBase: '#0d1b2a',
          colorBgContainer: '#0f2035',
          colorBgElevated: '#152840',
          colorBorder: 'rgba(0,212,255,0.2)',
          colorText: '#e2f4ff',
          colorTextSecondary: '#8ab4cc',
          borderRadius: 8,
          fontFamily: '"PingFang SC", "Microsoft YaHei", monospace, sans-serif',
        },
        components: {
          Layout: {
            siderBg: '#04080f',
            headerBg: '#080f1a',
          },
          Menu: {
            darkItemBg: '#04080f',
            darkSubMenuItemBg: '#080f1a',
            darkItemSelectedBg: 'rgba(0,212,255,0.15)',
          },
          Card: {
            colorBgContainer: 'rgba(8,24,42,0.85)',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
)
