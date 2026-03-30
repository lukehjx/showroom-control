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
          colorBgContainer: '#0f2336',
          colorBgElevated: '#132840',
          borderRadius: 8,
          fontFamily: '"PingFang SC", "Microsoft YaHei", sans-serif',
        },
        components: {
          Layout: { siderBg: '#080f1a', headerBg: '#0a1628' },
          Menu: { darkItemBg: '#080f1a', darkSubMenuItemBg: '#0a1628' },
        }
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
)
