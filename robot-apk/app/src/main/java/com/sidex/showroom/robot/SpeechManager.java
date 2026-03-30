package com.sidex.showroom.robot;

import android.content.Context;
import android.util.Log;

import com.ainirobot.coreservice.client.RobotApi;
import com.ainirobot.coreservice.client.listener.CommandListener;
import com.ainirobot.coreservice.client.module.ModuleCallbackApi;

import org.json.JSONObject;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 语音交互管理器
 * ASR语音识别 + 唤醒词监听 + 对话模式
 */
public class SpeechManager {
    private static final String TAG = "SpeechMgr";
    private static final String[] WAKE_WORDS = {"云猴", "小云", "你好云猴"};

    private final AtomicInteger reqId = new AtomicInteger(0);
    private boolean isListening = false;
    private SpeechCallback callback;

    public interface SpeechCallback {
        void onWakeUp(String keyword);          // 唤醒词触发
        void onSpeechResult(String text);       // ASR识别结果
        void onListeningStart();                // 开始监听
        void onListeningEnd();                  // 监听结束
        void onError(String error);
    }

    public SpeechManager(SpeechCallback callback) {
        this.callback = callback;
    }

    /** 开启持续监听（等待唤醒词） */
    public void startWakeWordListening() {
        try {
            // 注册唤醒词回调
            RobotApi.getInstance().registerWakeUp(reqId.incrementAndGet(), new CommandListener() {
                @Override
                public void onResult(int result, String message) {
                    Log.i(TAG, "唤醒词触发: " + message);
                    // 唤醒后开始ASR
                    if (callback != null) {
                        callback.onWakeUp(message);
                    }
                    startASROnce();
                }
            });
            Log.i(TAG, "唤醒词监听已开启");
        } catch (Exception e) {
            Log.e(TAG, "唤醒词监听失败: " + e.getMessage());
        }
    }

    /** 一次性ASR识别 */
    public void startASROnce() {
        if (isListening) return;
        isListening = true;
        try {
            if (callback != null) callback.onListeningStart();

            // 开启ASR（8秒超时）
            RobotApi.getInstance().startASR(reqId.incrementAndGet(), new CommandListener() {
                @Override
                public void onResult(int result, String message) {
                    isListening = false;
                    Log.i(TAG, "ASR结果[" + result + "]: " + message);
                    if (callback != null) {
                        callback.onListeningEnd();
                        if (result == 0 && message != null && !message.isEmpty()) {
                            callback.onSpeechResult(message);
                        }
                    }
                }
            });
        } catch (Exception e) {
            isListening = false;
            Log.e(TAG, "ASR启动失败: " + e.getMessage());
            if (callback != null) callback.onError(e.getMessage());
        }
    }

    /** 停止ASR */
    public void stopASR() {
        try {
            RobotApi.getInstance().stopASR(reqId.incrementAndGet());
            isListening = false;
        } catch (Exception ignored) {}
    }

    /** 停止唤醒词监听 */
    public void stopWakeWordListening() {
        try {
            RobotApi.getInstance().unregisterWakeUp(reqId.incrementAndGet());
        } catch (Exception ignored) {}
    }

    public boolean isListening() { return isListening; }
}
