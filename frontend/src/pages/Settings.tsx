import { useEffect, useState } from 'react'
import { Card, Descriptions, Button, Input, Form, message, Space, Tag, Divider, Alert } from 'antd'
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons'
import axios from 'axios'

interface RobotConfig {
  robot_sn: string; backend_ws_url: string; zhongkong_base_url: string
  zhongkong_tcp: string; wecom_bot_id: string
}

export default function Settings() {
  const [robotCfg, setRobotCfg] = useState<RobotConfig | null>(null)
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        axios.get('/api/settings/robot-config'),
        axios.get('/api/settings/'),
      ])
      setRobotCfg(r1.data.data)
      setSettings(r2.data.data || {})
      form.setFieldsValue(r2.data.data || {})
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  const saveSetting = async (key: string, value: string) => {
    try {
      await axios.put('/api/settings/', { key, value })
      message.success('保存成功')
    } catch { message.error('保存失败') }
  }

  return (
    <div>
      <Alert
        message="配置说明"
        description="敏感配置（API密钥、密码）通过服务器 .env 文件管理，不在此页面显示。此页仅显示运行时可调整的参数。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Card title="机器人配置（只读）" style={{ marginBottom: 16 }} loading={loading}>
        {robotCfg && (
          <Descriptions column={2} size="small">
            <Descriptions.Item label="机器人SN">
              <code style={{ color: '#00d4ff' }}>{robotCfg.robot_sn}</code>
            </Descriptions.Item>
            <Descriptions.Item label="后端WS地址">
              <code>{robotCfg.backend_ws_url}</code>
            </Descriptions.Item>
            <Descriptions.Item label="中控云平台">
              <code>{robotCfg.zhongkong_base_url}</code>
            </Descriptions.Item>
            <Descriptions.Item label="中控TCP">
              <code>{robotCfg.zhongkong_tcp}</code>
            </Descriptions.Item>
            <Descriptions.Item label="企微Bot ID">
              <code>{robotCfg.wecom_bot_id}</code>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card title="运行时参数" extra={<Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>}>
        <Form form={form} layout="vertical">
          <Divider>机器人行为</Divider>
          <Form.Item name="free_wake_seconds" label="免唤醒词时长（秒）"
            extra="机器人与访客交互后，多少秒内无需唤醒词即可继续对话，默认30">
            <Space>
              <Input style={{ width: 80 }} defaultValue="30" />
              <Button icon={<SaveOutlined />} onClick={async () => {
                const v = form.getFieldValue('free_wake_seconds') || '30'
                await saveSetting('free_wake_seconds', v)
              }}>保存</Button>
            </Space>
          </Form.Item>

          <Form.Item name="intent_timeout_ms" label="意图识别超时（毫秒）"
            extra="超时后使用关键词识别结果（不等待AI），默认5000">
            <Space>
              <Input style={{ width: 80 }} defaultValue="5000" />
              <Button icon={<SaveOutlined />} onClick={async () => {
                const v = form.getFieldValue('intent_timeout_ms') || '5000'
                await saveSetting('intent_timeout_ms', v)
              }}>保存</Button>
            </Space>
          </Form.Item>

          <Divider>通知</Divider>
          <Form.Item name="default_notify_chat" label="默认通知群ChatID">
            <Space>
              <Input style={{ width: 320 }} placeholder="wrsFDcBgAA5..." />
              <Button icon={<SaveOutlined />} onClick={async () => {
                const v = form.getFieldValue('default_notify_chat') || ''
                await saveSetting('default_notify_chat', v)
              }}>保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="系统信息" style={{ marginTop: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="后端服务">
            <Tag color="green">运行中</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="服务器">36.134.146.69:8200</Descriptions.Item>
          <Descriptions.Item label="前端域名">robot.sidex.cn</Descriptions.Item>
          <Descriptions.Item label="版本">v1.0.0</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  )
}
