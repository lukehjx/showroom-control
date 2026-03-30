package com.sidex.showroom.ui;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.ainirobot.coreservice.client.RobotApi;
import com.sidex.showroom.R;
import com.sidex.showroom.robot.RobotController;
import com.sidex.showroom.robot.SpeechManager;
import com.sidex.showroom.ws.CloudWebSocketClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Timer;
import java.util.TimerTask;

/**
 * 主Activity - 展厅智控APK
 * 集成豹小秘mini全部SDK能力
 *
 * 状态机：idle → navigating → speaking → following → patrolling
 * 交互路径：唤醒词 → ASR → WebSocket → 后端意图分析 → 执行动作 → 回调
 */
public class MainActivity extends AppCompatActivity
        implements RobotController.StatusListener {

    private static final String TAG = "MainActivity";
    private static final String ROBOT_SN = "MC1BCN2K100262058CA0";
    private static final String BACKEND_URL = "https://robot.sidex.cn";
    private static final String IDLE_PAGE   = BACKEND_URL + "/display/idle";

    // UI
    private WebView contentWebView;
    private TextView tvStatus;
    private TextView tvBattery;
    private TextView tvPoi;
    private View viewConnectionDot;
    private View viewListeningIndicator;  // ASR监听指示器

    // 核心组件
    private CloudWebSocketClient wsClient;
    private RobotController robotCtrl;
    private SpeechManager speechMgr;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private Timer statusTimer;
    private boolean isConnected = false;
    private boolean faceDetectEnabled = false;
    private long lastPersonDetectedMs = 0;
    private static final long PERSON_GREET_COOLDOWN_MS = 30_000; // 30秒内不重复打招呼

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 全屏沉浸式
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );

        initViews();
        initWebView();
        initRobotSdk();
        initSpeech();
        initWebSocket();
        startPeriodicReport();
    }

    // ==================== 初始化 ====================

    private void initViews() {
        contentWebView      = findViewById(R.id.webview_content);
        tvStatus            = findViewById(R.id.tv_status);
        tvBattery           = findViewById(R.id.tv_battery);
        tvPoi               = findViewById(R.id.tv_poi);
        viewConnectionDot   = findViewById(R.id.view_connection_dot);
        viewListeningIndicator = findViewById(R.id.view_listening);
    }

    private void initWebView() {
        WebSettings s = contentWebView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setAllowContentAccess(true);
        contentWebView.setWebViewClient(new WebViewClient());
        loadPage(IDLE_PAGE);
    }

    private void initRobotSdk() {
        robotCtrl = RobotController.getInstance();
        robotCtrl.setStatusListener(this);
        try {
            RobotApi.getInstance().connectServer(this, () -> {
                Log.i(TAG, "RobotOS连接成功");
                updateStatus("RobotOS已连接");
                reportPoiList();
                // 启动人脸检测
                startFaceDetectIfIdle();
            });
        } catch (Exception e) {
            Log.e(TAG, "RobotOS连接失败: " + e.getMessage());
            updateStatus("RobotOS连接失败，功能受限");
        }
    }

    private void initSpeech() {
        speechMgr = new SpeechManager(new SpeechManager.SpeechCallback() {
            @Override
            public void onWakeUp(String keyword) {
                Log.i(TAG, "唤醒: " + keyword);
                updateStatus("正在聆听...");
                showListeningIndicator(true);
                // 设置30秒免唤醒
                robotCtrl.setFreeWakeMode(30);
            }

            @Override
            public void onSpeechResult(String text) {
                Log.i(TAG, "ASR结果: " + text);
                showListeningIndicator(false);
                updateStatus("识别: " + text);
                // 发往后端处理
                sendSpeechToBackend(text);
            }

            @Override
            public void onListeningStart() {
                showListeningIndicator(true);
            }

            @Override
            public void onListeningEnd() {
                showListeningIndicator(false);
            }

            @Override
            public void onError(String error) {
                showListeningIndicator(false);
                Log.e(TAG, "语音错误: " + error);
            }
        });

        // 开启唤醒词监听
        speechMgr.startWakeWordListening();
    }

    private void initWebSocket() {
        wsClient = new CloudWebSocketClient(ROBOT_SN, new CloudWebSocketClient.MessageHandler() {
            @Override public void onConnected() {
                isConnected = true;
                updateConnectionDot(true);
                updateStatus("已连接云端");
            }
            @Override public void onMessage(JSONObject msg) {
                handleCloudMessage(msg);
            }
            @Override public void onDisconnected() {
                isConnected = false;
                updateConnectionDot(false);
                updateStatus("云端断线，重连中...");
            }
        });
        wsClient.connect();
    }

    // ==================== 云端消息处理 ====================

    private void handleCloudMessage(JSONObject msg) {
        try {
            String type = msg.getString("type");
            String callbackId = msg.optString("callback_id", null);

            switch (type) {
                case "auth_ok":
                    Log.i(TAG, "云端认证成功");
                    break;

                case "navigate":
                    execNavigate(msg, callbackId);
                    break;

                case "speak":
                    execSpeak(msg, callbackId);
                    break;

                case "stop":
                    robotCtrl.stopAll();
                    updateStatus("已停止");
                    sendAck(callbackId, "stopped", true);
                    break;

                case "go_charge":
                    robotCtrl.goCharge(new RobotController.ActionCallback() {
                        @Override public void onSuccess(String d) {
                            updateStatus("充电中");
                            sendAck(callbackId, "charging", true);
                        }
                        @Override public void onFail(String r) {
                            updateStatus("回充失败: " + r);
                            sendAck(callbackId, "charge_failed", false);
                        }
                    });
                    break;

                case "follow":
                    boolean startFollow = msg.optBoolean("start", true);
                    if (startFollow) {
                        robotCtrl.startFollowing(new RobotController.ActionCallback() {
                            @Override public void onSuccess(String d) { /* 跟随中持续 */ }
                            @Override public void onFail(String r) {
                                updateStatus("跟随丢失");
                                sendAck(callbackId, "follow_lost", false);
                            }
                        });
                        updateStatus("跟随模式");
                        sendAck(callbackId, "following", true);
                    } else {
                        robotCtrl.stopFollowing();
                        updateStatus("跟随已停止");
                        sendAck(callbackId, "follow_stopped", true);
                    }
                    break;

                case "face_detect":
                    boolean enable = msg.optBoolean("enable", true);
                    if (enable) {
                        startFaceDetectIfIdle();
                    } else {
                        robotCtrl.stopFaceDetection();
                        faceDetectEnabled = false;
                    }
                    sendAck(callbackId, enable ? "face_detect_on" : "face_detect_off", true);
                    break;

                case "rotate_head":
                    float h = (float) msg.optDouble("horizontal", 0);
                    float v = (float) msg.optDouble("vertical", 0);
                    robotCtrl.rotateHead(h, v, new RobotController.ActionCallback() {
                        @Override public void onSuccess(String d) { sendAck(callbackId, "head_moved", true); }
                        @Override public void onFail(String r) { sendAck(callbackId, "head_failed", false); }
                    });
                    break;

                case "set_volume":
                    int vol = msg.optInt("volume", 70);
                    robotCtrl.setVolume(vol);
                    sendAck(callbackId, "volume_set", true);
                    break;

                case "set_free_wake":
                    int dur = msg.optInt("duration", 30);
                    robotCtrl.setFreeWakeMode(dur);
                    sendAck(callbackId, "free_wake_set", true);
                    break;

                case "get_poi_list":
                    reportPoiList();
                    break;

                case "display":
                    String url = msg.optString("url", IDLE_PAGE);
                    String dtype = msg.optString("display_type", "url");
                    loadPage("idle".equals(dtype) ? IDLE_PAGE : url);
                    sendAck(callbackId, "displayed", true);
                    break;

                case "reply":
                    // 后端AI回复：机器人TTS朗读
                    String replyText = msg.optString("text", "");
                    String displayText = msg.optString("display", "");
                    float speed = (float) msg.optDouble("speed", 1.0);
                    if (!replyText.isEmpty()) {
                        updateStatus(displayText.isEmpty() ? replyText : displayText);
                        robotCtrl.speak(replyText, speed, null);
                        // 朗读时设置免唤醒
                        robotCtrl.setFreeWakeMode(30);
                    }
                    break;

                case "heartbeat_ack":
                    break;

                case "reset":
                    robotCtrl.stopAll();
                    robotCtrl.resetHead();
                    loadPage(IDLE_PAGE);
                    updateStatus("系统已重置");
                    break;

                default:
                    Log.w(TAG, "未知消息类型: " + type);
            }
        } catch (Exception e) {
            Log.e(TAG, "处理消息异常: " + e.getMessage());
        }
    }

    // ==================== 动作执行 ====================

    private void execNavigate(JSONObject msg, String callbackId) throws Exception {
        String poi = msg.getString("poi");
        float speed = (float) msg.optDouble("speed", 0.3);
        updateStatus("导航中: " + poi);
        robotCtrl.navigateTo(poi, speed, new RobotController.ActionCallback() {
            @Override public void onSuccess(String data) {
                updateStatus("已到达: " + poi);
                sendAck(callbackId, "navigation_arrived", true);
                // 到达后重新开启人脸检测
                mainHandler.postDelayed(() -> startFaceDetectIfIdle(), 2000);
            }
            @Override public void onFail(String reason) {
                updateStatus("导航失败: " + reason);
                sendAck(callbackId, "navigation_failed", false);
            }
        });
    }

    private void execSpeak(JSONObject msg, String callbackId) throws Exception {
        String text = msg.getString("text");
        float speed = (float) msg.optDouble("speed", 1.0);
        updateStatus("播报: " + text.substring(0, Math.min(text.length(), 20)) + "...");
        robotCtrl.speak(text, speed, new RobotController.ActionCallback() {
            @Override public void onSuccess(String data) {
                updateStatus("播报完成");
                sendAck(callbackId, "speak_done", true);
                // 播报完后重新唤醒
                speechMgr.startWakeWordListening();
            }
            @Override public void onFail(String reason) {
                sendAck(callbackId, "speak_failed", false);
            }
        });
    }

    private void sendAck(String callbackId, String event, boolean success) {
        if (callbackId != null && !callbackId.isEmpty() && wsClient != null) {
            wsClient.sendCallback(callbackId, event, success);
        }
    }

    // ==================== 人脸检测 ====================

    private void startFaceDetectIfIdle() {
        if (faceDetectEnabled) return;
        faceDetectEnabled = true;
        robotCtrl.startFaceDetection(new RobotController.ActionCallback() {
            @Override public void onSuccess(String personCount) {
                long now = System.currentTimeMillis();
                if (now - lastPersonDetectedMs > PERSON_GREET_COOLDOWN_MS) {
                    lastPersonDetectedMs = now;
                    Log.i(TAG, "检测到 " + personCount + " 人，发送迎宾事件");
                    sendPersonDetected(personCount);
                }
            }
            @Override public void onFail(String reason) { /* 无需处理 */ }
        });
    }

    private void sendPersonDetected(String count) {
        if (wsClient == null) return;
        try {
            JSONObject msg = new JSONObject();
            msg.put("type", "person_detected");
            msg.put("count", Integer.parseInt(count));
            msg.put("poi", robotCtrl.getCurrentPoi());
            wsClient.send(msg);
        } catch (Exception ignored) {}
    }

    // ==================== 语音输入 ====================

    private void sendSpeechToBackend(String text) {
        if (wsClient == null) return;
        try {
            JSONObject msg = new JSONObject();
            msg.put("type", "speech_input");
            msg.put("text", text);
            msg.put("poi", robotCtrl.getCurrentPoi());
            msg.put("battery", robotCtrl.getCurrentBattery());
            wsClient.send(msg);
        } catch (Exception ignored) {}
    }

    // ==================== 状态上报 ====================

    private void reportPoiList() {
        robotCtrl.getPoiList(new RobotController.ActionCallback() {
            @Override public void onSuccess(String data) {
                try {
                    JSONArray arr = new JSONArray(data);
                    wsClient.sendPoiList(arr);
                    Log.i(TAG, "上报 " + arr.length() + " 个POI");
                } catch (Exception e) {
                    Log.e(TAG, "POI解析失败: " + e.getMessage());
                }
            }
            @Override public void onFail(String r) { Log.e(TAG, "获取POI失败: " + r); }
        });
    }

    /** 定时上报状态（每10秒） */
    private void startPeriodicReport() {
        statusTimer = new Timer();
        statusTimer.scheduleAtFixedRate(new TimerTask() {
            @Override public void run() {
                if (!isConnected) return;
                int battery = robotCtrl.getBattery();
                boolean charging = robotCtrl.isCharging();
                String poi = robotCtrl.getCurrentPoi();
                String status = robotCtrl.getCurrentStatus();

                if (battery >= 0) {
                    mainHandler.post(() -> {
                        tvBattery.setText(battery + "%");
                        // 低电量自动回充
                        if (battery <= 15 && !charging && !"charging".equals(status)) {
                            Log.w(TAG, "低电量，自动回充");
                            robotCtrl.goCharge(null);
                        }
                    });
                }

                wsClient.sendStatus(battery, poi, status + (charging ? "_charging" : ""));

                // 发心跳
                try {
                    JSONObject hb = new JSONObject();
                    hb.put("type", "heartbeat");
                    hb.put("battery", battery);
                    hb.put("charging", charging);
                    hb.put("poi", poi);
                    hb.put("status", status);
                    wsClient.send(hb);
                } catch (Exception ignored) {}
            }
        }, 5000, 10000);
    }

    // ==================== RobotController.StatusListener ====================

    @Override public void onBatteryChanged(int battery, boolean isCharging) {
        mainHandler.post(() -> tvBattery.setText(battery + "%" + (isCharging ? "⚡" : "")));
    }

    @Override public void onPositionChanged(String poi) {
        mainHandler.post(() -> tvPoi.setText(poi));
    }

    @Override public void onStatusChanged(String status) {
        String label = statusToLabel(status);
        mainHandler.post(() -> tvStatus.setText(label));
    }

    // ==================== 辅助方法 ====================

    private void loadPage(String url) {
        mainHandler.post(() -> contentWebView.loadUrl(url));
    }

    private void updateStatus(String status) {
        mainHandler.post(() -> {
            if (tvStatus != null) tvStatus.setText(status);
            Log.i(TAG, "[状态] " + status);
        });
    }

    private void updateConnectionDot(boolean connected) {
        mainHandler.post(() -> {
            if (viewConnectionDot != null) {
                viewConnectionDot.setBackgroundResource(
                        connected ? R.drawable.dot_green : R.drawable.dot_red);
            }
        });
    }

    private void showListeningIndicator(boolean show) {
        mainHandler.post(() -> {
            if (viewListeningIndicator != null) {
                viewListeningIndicator.setVisibility(show ? View.VISIBLE : View.GONE);
            }
        });
    }

    private String statusToLabel(String status) {
        switch (status) {
            case "navigating":  return "导航中...";
            case "speaking":    return "讲解中...";
            case "following":   return "跟随模式";
            case "charging":    return "充电中";
            case "patrolling":  return "巡逻中";
            default:            return "待机";
        }
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        if (statusTimer != null) statusTimer.cancel();
        if (wsClient != null) wsClient.disconnect();
        if (speechMgr != null) {
            speechMgr.stopWakeWordListening();
            speechMgr.stopASR();
        }
        robotCtrl.stopAll();
        try { RobotApi.getInstance().disconnectServer(); } catch (Exception ignored) {}
    }
}
