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

import com.orionstar.robotapi.RobotApi;
import com.sidex.showroom.R;
import com.sidex.showroom.robot.RobotController;
import com.sidex.showroom.ws.CloudWebSocketClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Timer;
import java.util.TimerTask;

/**
 * 主Activity - 豹小秘展厅智控APK
 *
 * UI结构（覆盖层）：
 *   ┌─────────────────────────┐
 *   │   [顶部状态栏]           │  ← Native View（电量/状态/连接）
 *   ├─────────────────────────┤
 *   │                         │
 *   │   WebView（全屏内容区）  │  ← 后端推送展示内容/待机页
 *   │                         │
 *   ├─────────────────────────┤
 *   │   [底部状态条]           │  ← 当前状态文字提示
 *   └─────────────────────────┘
 */
public class MainActivity extends AppCompatActivity {
    private static final String TAG = "MainActivity";
    private static final String ROBOT_SN = "MC1BCN2K100262058CA0";
    private static final String BACKEND_URL = "https://robot.sidex.cn";
    private static final String IDLE_PAGE = BACKEND_URL + "/display/idle";   // 待机页
    private static final String DISPLAY_PAGE = BACKEND_URL + "/display/";     // 内容展示页

    private WebView contentWebView;
    private TextView statusText;
    private TextView batteryText;
    private View connectionDot;

    private CloudWebSocketClient wsClient;
    private RobotController robotController;
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private Timer statusTimer;
    private boolean isConnected = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 全屏，隐藏系统UI
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );

        initViews();
        initWebView();
        initRobotSdk();
        initWebSocket();
        startStatusReporter();
    }

    private void initViews() {
        contentWebView = findViewById(R.id.webview_content);
        statusText = findViewById(R.id.tv_status);
        batteryText = findViewById(R.id.tv_battery);
        connectionDot = findViewById(R.id.view_connection_dot);
    }

    private void initWebView() {
        WebSettings settings = contentWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        // 自动播放视频
        settings.setAllowContentAccess(true);

        contentWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                Log.d(TAG, "页面加载完成: " + url);
            }
        });

        // 加载待机页
        loadPage(IDLE_PAGE);
    }

    private void loadPage(String url) {
        mainHandler.post(() -> contentWebView.loadUrl(url));
    }

    private void initRobotSdk() {
        robotController = RobotController.getInstance();
        // 连接RobotOS
        try {
            RobotApi.getInstance().connectServer(this, () -> {
                Log.i(TAG, "RobotOS连接成功");
                updateStatus("RobotOS已连接");
                // 上报POI列表
                reportPoiList();
            });
        } catch (Exception e) {
            Log.e(TAG, "RobotOS连接失败: " + e.getMessage());
        }
    }

    private void initWebSocket() {
        wsClient = new CloudWebSocketClient(ROBOT_SN, new CloudWebSocketClient.MessageHandler() {
            @Override
            public void onConnected() {
                isConnected = true;
                updateConnectionDot(true);
                updateStatus("已连接云端");
            }

            @Override
            public void onMessage(JSONObject msg) {
                handleCloudMessage(msg);
            }

            @Override
            public void onDisconnected() {
                isConnected = false;
                updateConnectionDot(false);
                updateStatus("云端断线，重连中...");
            }
        });
        wsClient.connect();
    }

    private void handleCloudMessage(JSONObject msg) {
        try {
            String type = msg.getString("type");
            String callbackId = msg.optString("callback_id", null);

            switch (type) {
                case "auth_ok":
                    Log.i(TAG, "云端认证成功");
                    break;

                case "navigate":
                    String poi = msg.getString("poi");
                    boolean waitArrival = msg.optBoolean("wait_arrival", false);
                    updateStatus("导航中: " + poi);
                    robotController.navigateTo(poi, new RobotController.ActionCallback() {
                        @Override
                        public void onSuccess(String data) {
                            updateStatus("已到达: " + poi);
                            if (callbackId != null && !callbackId.isEmpty()) {
                                wsClient.sendCallback(callbackId, "navigation_arrived", true);
                                // 额外发送arrived事件（用于触发到达后逻辑）
                                try {
                                    JSONObject arrivedMsg = new JSONObject();
                                    arrivedMsg.put("type", "callback");
                                    arrivedMsg.put("event", "navigation_arrived");
                                    arrivedMsg.put("poi", poi);
                                    arrivedMsg.put("success", true);
                                    if (callbackId != null) arrivedMsg.put("callback_id", callbackId);
                                    wsClient.send(arrivedMsg);
                                } catch (Exception ignored) {}
                            }
                        }
                        @Override
                        public void onFail(String reason) {
                            updateStatus("导航失败: " + reason);
                            if (callbackId != null) wsClient.sendCallback(callbackId, "navigation_failed", false);
                        }
                    });
                    break;

                case "speak":
                    String text = msg.getString("text");
                    boolean waitDone = msg.optBoolean("wait_done", false);
                    updateStatus("播报中...");
                    robotController.speak(text, new RobotController.ActionCallback() {
                        @Override
                        public void onSuccess(String data) {
                            updateStatus("播报完成");
                            if (callbackId != null) wsClient.sendCallback(callbackId, "speak_done", true);
                        }
                        @Override
                        public void onFail(String reason) {
                            if (callbackId != null) wsClient.sendCallback(callbackId, "speak_failed", false);
                        }
                    });
                    break;

                case "stop":
                    robotController.stop();
                    updateStatus("已停止");
                    break;

                case "go_charge":
                    robotController.goCharge(new RobotController.ActionCallback() {
                        @Override public void onSuccess(String data) { updateStatus("充电中"); }
                        @Override public void onFail(String reason) { updateStatus("回充失败"); }
                    });
                    break;

                case "get_poi_list":
                    reportPoiList();
                    break;

                case "set_free_wake":
                    int duration = msg.optInt("duration", 30);
                    robotController.setFreeWakeMode(duration);
                    break;

                case "display":
                    // 控制大屏显示内容
                    String displayUrl = msg.optString("url", IDLE_PAGE);
                    String displayType = msg.optString("display_type", "url");
                    if ("idle".equals(displayType)) {
                        loadPage(IDLE_PAGE);
                    } else {
                        loadPage(displayUrl);
                    }
                    break;

                case "reply":
                    // 收到AI回复文本，显示在状态栏
                    String replyText = msg.optString("text", "");
                    if (!replyText.isEmpty()) {
                        updateStatus(replyText);
                    }
                    break;

                case "heartbeat_ack":
                    break;

                default:
                    Log.w(TAG, "未知消息类型: " + type);
            }
        } catch (Exception e) {
            Log.e(TAG, "处理消息异常: " + e.getMessage());
        }
    }

    private void reportPoiList() {
        robotController.getPoiList(new RobotController.ActionCallback() {
            @Override
            public void onSuccess(String data) {
                try {
                    JSONArray poiArray = new JSONArray(data);
                    wsClient.sendPoiList(poiArray);
                    Log.i(TAG, "上报 " + poiArray.length() + " 个POI点位");
                } catch (Exception e) {
                    Log.e(TAG, "POI解析失败: " + e.getMessage());
                }
            }
            @Override
            public void onFail(String reason) {
                Log.e(TAG, "获取POI失败: " + reason);
            }
        });
    }

    /** 定时上报状态（每10秒） */
    private void startStatusReporter() {
        statusTimer = new Timer();
        statusTimer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                if (isConnected) {
                    int battery = robotController.getBattery();
                    if (battery >= 0) {
                        mainHandler.post(() -> batteryText.setText(battery + "%"));
                        wsClient.sendStatus(battery, null, "idle");
                    }
                    // 发心跳
                    try {
                        JSONObject hb = new JSONObject();
                        hb.put("type", "heartbeat");
                        wsClient.send(hb);
                    } catch (Exception ignored) {}
                }
            }
        }, 5000, 10000);
    }

    private void updateStatus(String status) {
        mainHandler.post(() -> {
            if (statusText != null) statusText.setText(status);
            Log.i(TAG, "状态: " + status);
        });
    }

    private void updateConnectionDot(boolean connected) {
        mainHandler.post(() -> {
            if (connectionDot != null) {
                connectionDot.setBackgroundResource(connected ?
                        R.drawable.dot_green : R.drawable.dot_red);
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (statusTimer != null) statusTimer.cancel();
        if (wsClient != null) wsClient.disconnect();
        try { RobotApi.getInstance().disconnectServer(); } catch (Exception ignored) {}
    }
}
