package com.sidex.showroom.ws;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONObject;

import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * 云端WebSocket客户端
 * 连接到后端 ws://robot.sidex.cn/ws/robot/{sn}
 * 自动重连，断线后指数退避
 */
public class CloudWebSocketClient {
    private static final String TAG = "CloudWS";
    private static final String WS_URL = "wss://robot.sidex.cn/ws/robot/";
    private static final int MAX_RECONNECT_DELAY_MS = 30000;

    private final String robotSn;
    private WebSocket webSocket;
    private OkHttpClient client;
    private MessageHandler handler;
    private boolean shouldReconnect = true;
    private int reconnectDelay = 2000;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public interface MessageHandler {
        void onConnected();
        void onMessage(JSONObject msg);
        void onDisconnected();
    }

    public CloudWebSocketClient(String robotSn, MessageHandler handler) {
        this.robotSn = robotSn;
        this.handler = handler;
        this.client = new OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)  // 长连接不超时
                .build();
    }

    public void connect() {
        String url = WS_URL + robotSn;
        Request request = new Request.Builder().url(url).build();
        webSocket = client.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket ws, Response response) {
                Log.i(TAG, "WebSocket 已连接: " + url);
                reconnectDelay = 2000;
                // 发送认证消息
                send(new JSONObject() {{
                    try { put("type", "auth"); put("sn", robotSn); } catch (Exception ignored) {}
                }});
                mainHandler.post(() -> handler.onConnected());
            }

            @Override
            public void onMessage(WebSocket ws, String text) {
                try {
                    JSONObject msg = new JSONObject(text);
                    Log.d(TAG, "收到: " + text.substring(0, Math.min(text.length(), 100)));
                    mainHandler.post(() -> handler.onMessage(msg));
                } catch (Exception e) {
                    Log.e(TAG, "消息解析失败: " + text);
                }
            }

            @Override
            public void onFailure(WebSocket ws, Throwable t, Response response) {
                Log.e(TAG, "WebSocket 断开: " + t.getMessage());
                mainHandler.post(() -> handler.onDisconnected());
                scheduleReconnect();
            }

            @Override
            public void onClosed(WebSocket ws, int code, String reason) {
                Log.w(TAG, "WebSocket 关闭: " + reason);
                mainHandler.post(() -> handler.onDisconnected());
                if (shouldReconnect) scheduleReconnect();
            }
        });
    }

    public void send(JSONObject msg) {
        if (webSocket != null) {
            webSocket.send(msg.toString());
        }
    }

    public void sendStatus(int battery, String poi, String status) {
        try {
            JSONObject msg = new JSONObject();
            msg.put("type", "status");
            msg.put("battery", battery);
            msg.put("poi", poi);
            msg.put("status", status);
            send(msg);
        } catch (Exception ignored) {}
    }

    public void sendSpeechInput(String text) {
        try {
            JSONObject msg = new JSONObject();
            msg.put("type", "speech_input");
            msg.put("text", text);
            send(msg);
        } catch (Exception ignored) {}
    }

    public void sendCallback(String callbackId, String event, boolean success) {
        try {
            JSONObject msg = new JSONObject();
            msg.put("type", "callback");
            msg.put("callback_id", callbackId);
            msg.put("event", event);
            msg.put("success", success);
            send(msg);
        } catch (Exception ignored) {}
    }

    public void sendPoiList(org.json.JSONArray poiList) {
        try {
            JSONObject msg = new JSONObject();
            msg.put("type", "poi_list");
            msg.put("poi_list", poiList);
            send(msg);
        } catch (Exception ignored) {}
    }

    private void scheduleReconnect() {
        if (!shouldReconnect) return;
        Log.i(TAG, "将在 " + reconnectDelay + "ms 后重连");
        mainHandler.postDelayed(() -> {
            if (shouldReconnect) connect();
        }, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS);
    }

    public void disconnect() {
        shouldReconnect = false;
        if (webSocket != null) webSocket.close(1000, "正常关闭");
    }
}
