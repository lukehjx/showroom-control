# 展厅智控 Robot APK

## 技术方案

### UI 架构：Native + WebView 混合

```
┌─────────────────────────────────┐
│  顶部状态栏（Native，40dp高）    │  连接状态点 + 系统名 + 电量
├─────────────────────────────────┤
│                                 │
│   WebView（全屏内容区）          │  ← 后端控制：待机页/媒体/讲解页
│                                 │
│   http://robot.sidex.cn/display │
│                                 │
├─────────────────────────────────┤
│  底部状态条（Native，48dp高）    │  当前状态/AI回复文字
└─────────────────────────────────┘
```

**为什么用 WebView？**
- 展示内容（图片/视频/PPT/二维码）改变不需要重新发包
- 后端直接推送展示页URL给APK
- 支持复杂布局（多媒体混排）
- Native 层只管 SDK 通道，WebView 管内容展示

### 通信流程

```
ASR（机器人语音识别）
    ↓
APK 收到语音文本
    ↓
发给云端 WebSocket（type: speech_input）
    ↓
后端意图识别 → 执行动作
    ↓
云端推送指令（navigate/speak/display...）
    ↓
APK 调用 RobotOS SDK 执行
    ↓
回调结果上报云端
```

### 关键文件

- `MainActivity.java` — 主入口，UI控制，消息分发
- `CloudWebSocketClient.java` — 云端WS连接（自动重连）
- `RobotController.java` — RobotOS SDK封装

## 构建要求

- Android Studio Arctic Fox 或以上
- minSdk: 21
- targetSdk: 30
- 将 RobotService.jar 放入 `app/libs/` 目录
- 修改 `CloudWebSocketClient.java` 中的 `WS_URL` 为实际后端地址

## APK 安装

```bash
adb install -r app-debug.apk
```

豹小秘设置为 developer mode 后，会将此APK设为默认启动应用。
