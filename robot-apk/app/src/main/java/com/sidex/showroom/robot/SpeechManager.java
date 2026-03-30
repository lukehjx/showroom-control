package com.sidex.showroom.robot;

import android.util.Log;

import com.ainirobot.coreservice.client.RobotApi;
import com.ainirobot.coreservice.client.listener.CommandListener;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 语音交互管理器
 * ASR语音识别 + 唤醒词监听（唤醒词从后端拉取，默认"旺财"）
 */
public class SpeechManager {
    private static final String TAG = "SpeechMgr";

    private final AtomicInteger reqId = new AtomicInteger(0);
    private boolean isListening = false;
    private String wakeWord = "旺财";  // 默认唤醒词，后端拉取后更新
    private SpeechCallback callback;

    public interface SpeechCallback {
        void onWakeUp(String keyword);
        void onSpeechResult(String text);
        void onListeningStart();
        void onListeningEnd();
        void onError(String error);
    }

    public SpeechManager(SpeechCallback callback) {
        this.callback = callback;
    }

    /** 设置唤醒词（从后端 /api/config/robot.wake_word 拉取后调用） */
    public void setWakeWord(String word) {
        if (word != null && !word.isEmpty()) {
            this.wakeWord = word;
            Log.i(TAG, "唤醒词已更新: " + word);
        }
    }

    public String getWakeWord() {
        return wakeWord;
    }

    /** 开启持续唤醒词监听 */
    public void startWakeWordListening() {
        try {
            RobotApi.getInstance().registerWakeUp(reqId.incrementAndGet(), new CommandListener() {
                @Override
                public void onResult(int result, String message) {
                    Log.i(TAG, "唤醒词触发: " + message + " (当前唤醒词: " + wakeWord + ")");
                    if (callback != null) {
                        callback.onWakeUp(message != null ? message : wakeWord);
                    }
                    startASROnce();
                }

                @Override
                public void onStatusUpdate(int status, String data) {
                    Log.d(TAG, "唤醒状态: " + status + " " + data);
                }
            });
            Log.i(TAG, "唤醒词监听已开启，唤醒词: " + wakeWord);
        } catch (Exception e) {
            Log.e(TAG, "唤醒词监听失败: " + e.getMessage());
            if (callback != null) callback.onError("唤醒词监听失败: " + e.getMessage());
        }
    }

    /** 一次性ASR识别（唤醒后调用，8秒超时） */
    public void startASROnce() {
        if (isListening) {
            Log.w(TAG, "ASR已在监听中，跳过");
            return;
        }
        isListening = true;
        try {
            if (callback != null) callback.onListeningStart();

            RobotApi.getInstance().startASR(reqId.incrementAndGet(), new CommandListener() {
                @Override
                public void onResult(int result, String message) {
                    isListening = false;
                    Log.i(TAG, "ASR结果[" + result + "]: " + message);
                    if (callback != null) {
                        callback.onListeningEnd();
                        if (result == 0 && message != null && !message.trim().isEmpty()) {
                            // 过滤掉唤醒词本身
                            String text = message.trim();
                            if (!text.equals(wakeWord)) {
                                callback.onSpeechResult(text);
                            } else {
                                Log.d(TAG, "识别结果仅为唤醒词，跳过");
                            }
                        }
                    }
                }

                @Override
                public void onStatusUpdate(int status, String data) {
                    Log.d(TAG, "ASR状态: " + status + " " + data);
                    if (status == -1) {
                        // 超时或错误
                        isListening = false;
                        if (callback != null) callback.onListeningEnd();
                    }
                }
            });
        } catch (Exception e) {
            isListening = false;
            Log.e(TAG, "ASR启动失败: " + e.getMessage());
            if (callback != null) {
                callback.onListeningEnd();
                callback.onError(e.getMessage());
            }
        }
    }

    /** 主动触发一次ASR（如按钮触发） */
    public void triggerASR() {
        startASROnce();
    }

    public void stopASR() {
        try {
            RobotApi.getInstance().stopASR(reqId.incrementAndGet());
            isListening = false;
        } catch (Exception ignored) {}
    }

    public void stopWakeWordListening() {
        try {
            RobotApi.getInstance().unregisterWakeUp(reqId.incrementAndGet());
        } catch (Exception ignored) {}
    }

    public boolean isListening() {
        return isListening;
    }
}
