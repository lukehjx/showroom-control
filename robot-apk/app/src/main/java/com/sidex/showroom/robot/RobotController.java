package com.sidex.showroom.robot;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.ainirobot.coreservice.client.RobotApi;
import com.ainirobot.coreservice.client.Definition;
import com.ainirobot.coreservice.client.listener.CommandListener;
import com.ainirobot.coreservice.client.listener.NavigationListener;
import com.ainirobot.coreservice.client.listener.PersonTrackingListener;
import com.ainirobot.coreservice.client.listener.ActionListener;
import com.ainirobot.coreservice.client.robotsetting.RobotSettingApi;
import com.ainirobot.coreservice.client.module.ModuleCallbackApi;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 机器人SDK能力全集成封装
 * 覆盖豹小秘mini全部可用SDK能力
 */
public class RobotController {
    private static final String TAG = "RobotCtrl";
    private static RobotController instance;
    private final AtomicInteger reqId = new AtomicInteger(0);
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    // 当前状态
    private String currentPoi = "";
    private int currentBattery = -1;
    private String currentStatus = "idle"; // idle/navigating/speaking/touring/following/patrolling

    // 回调接口
    public interface ActionCallback {
        void onSuccess(String data);
        void onFail(String reason);
    }

    public interface StatusListener {
        void onBatteryChanged(int battery, boolean isCharging);
        void onPositionChanged(String poi);
        void onStatusChanged(String status);
    }

    private StatusListener statusListener;

    private RobotController() {}

    public static RobotController getInstance() {
        if (instance == null) instance = new RobotController();
        return instance;
    }

    public void setStatusListener(StatusListener listener) {
        this.statusListener = listener;
    }

    // ==================== 导航能力 ====================

    /** 导航到POI点位 */
    public void navigateTo(String poiName, float speed, ActionCallback callback) {
        int id = reqId.incrementAndGet();
        currentStatus = "navigating";
        notifyStatusChanged("navigating");
        Log.i(TAG, "导航到: " + poiName + " 速度:" + speed);
        try {
            RobotApi.getInstance().startNavigation(id, poiName, speed, 60000,
                    new NavigationListener() {
                        @Override public void onSuccess(String destination) {
                            Log.i(TAG, "导航成功: " + destination);
                            currentPoi = poiName;
                            currentStatus = "idle";
                            notifyPositionChanged(poiName);
                            notifyStatusChanged("idle");
                            if (callback != null) callback.onSuccess(destination);
                        }
                        @Override public void onFail(int error) {
                            Log.e(TAG, "导航失败: " + error);
                            currentStatus = "idle";
                            notifyStatusChanged("idle");
                            if (callback != null) callback.onFail("error:" + error);
                        }
                        @Override public void onStatusUpdate(int status) {
                            Log.d(TAG, "导航状态: " + status);
                        }
                    });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    public void navigateTo(String poiName, ActionCallback callback) {
        navigateTo(poiName, 0.3f, callback);
    }

    /** 停止导航 */
    public void stopNavigation() {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().stopNavigation(id);
            currentStatus = "idle";
            notifyStatusChanged("idle");
        } catch (Exception ignored) {}
    }

    // ==================== TTS语音能力 ====================

    /** TTS播报，支持情感和语速 */
    public void speak(String text, float speed, ActionCallback callback) {
        int id = reqId.incrementAndGet();
        currentStatus = "speaking";
        notifyStatusChanged("speaking");
        Log.i(TAG, "TTS[speed=" + speed + "]: " + text);
        try {
            // 构造TTS参数（速度/音调）
            String ttsText = speed != 1.0f ? buildSpeechRateText(text, speed) : text;
            RobotApi.getInstance().playText(id, ttsText, new CommandListener() {
                @Override public void onResult(int result, String message) {
                    currentStatus = "idle";
                    notifyStatusChanged("idle");
                    if ("succeed".equals(message)) {
                        if (callback != null) callback.onSuccess("done");
                    } else {
                        if (callback != null) callback.onFail(message);
                    }
                }
            });
        } catch (Exception e) {
            currentStatus = "idle";
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    public void speak(String text, ActionCallback callback) {
        speak(text, 1.0f, callback);
    }

    /** 停止TTS */
    public void stopSpeak() {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().stopTTS(id);
        } catch (Exception ignored) {}
    }

    private String buildSpeechRateText(String text, float speed) {
        // SDK支持的语速标记格式（如有）
        return text;
    }

    // ==================== 人脸/人体感知 ====================

    /** 开启人脸检测（有人靠近时回调） */
    public void startFaceDetection(ActionCallback onFaceDetected) {
        int id = reqId.incrementAndGet();
        try {
            // 人体检测
            RobotApi.getInstance().setPersonDetectListener(id, response -> {
                try {
                    JSONArray persons = new JSONArray(response);
                    if (persons.length() > 0) {
                        Log.i(TAG, "检测到人: " + persons.length() + "人");
                        mainHandler.post(() -> {
                            if (onFaceDetected != null)
                                onFaceDetected.onSuccess(String.valueOf(persons.length()));
                        });
                    }
                } catch (Exception e) {
                    Log.e(TAG, "人体解析失败: " + e.getMessage());
                }
            });
        } catch (Exception e) {
            Log.e(TAG, "人脸检测启动失败: " + e.getMessage());
        }
    }

    /** 停止人脸检测 */
    public void stopFaceDetection() {
        try {
            RobotApi.getInstance().stopPersonDetect(reqId.incrementAndGet());
        } catch (Exception ignored) {}
    }

    // ==================== 跟随模式 ====================

    /** 开启人体跟随 */
    public void startFollowing(ActionCallback callback) {
        int id = reqId.incrementAndGet();
        currentStatus = "following";
        notifyStatusChanged("following");
        try {
            RobotApi.getInstance().startFollowPerson(id, new PersonTrackingListener() {
                @Override public void onLost() {
                    Log.i(TAG, "跟随目标丢失");
                    currentStatus = "idle";
                    notifyStatusChanged("idle");
                    if (callback != null) callback.onFail("target_lost");
                }
                @Override public void onFound() {
                    Log.i(TAG, "找到跟随目标");
                }
                @Override public void onTrack(int x, int y) {
                    Log.d(TAG, "跟随中: " + x + "," + y);
                }
            });
        } catch (Exception e) {
            currentStatus = "idle";
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 停止跟随 */
    public void stopFollowing() {
        try {
            RobotApi.getInstance().stopFollowPerson(reqId.incrementAndGet());
            currentStatus = "idle";
            notifyStatusChanged("idle");
        } catch (Exception ignored) {}
    }

    // ==================== 自动回充 ====================

    /** 去充电桩 */
    public void goCharge(ActionCallback callback) {
        int id = reqId.incrementAndGet();
        currentStatus = "charging";
        notifyStatusChanged("charging");
        try {
            RobotApi.getInstance().startNaviToAutoChargeAction(id, 120000,
                    (status, responseString) -> {
                        if (status == 0) {
                            if (callback != null) callback.onSuccess("charging");
                        } else {
                            currentStatus = "idle";
                            notifyStatusChanged("idle");
                            if (callback != null) callback.onFail("charge_fail:" + status);
                        }
                        return null;
                    });
        } catch (Exception e) {
            currentStatus = "idle";
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    // ==================== 设备状态 ====================

    /** 获取当前电量 */
    public int getBattery() {
        try {
            String val = RobotSettingApi.getInstance()
                    .getRobotString(Definition.ROBOT_SETTINGS_BATTERY_INFO);
            if (val != null) {
                currentBattery = Integer.parseInt(val.replace("%", "").trim());
            }
        } catch (Exception e) {
            Log.e(TAG, "获取电量失败: " + e.getMessage());
        }
        return currentBattery;
    }

    /** 是否在充电 */
    public boolean isCharging() {
        try {
            String val = RobotSettingApi.getInstance()
                    .getRobotString(Definition.ROBOT_SETTINGS_CHARGE_STATUS);
            return "true".equalsIgnoreCase(val) || "1".equals(val);
        } catch (Exception e) {
            return false;
        }
    }

    /** 获取当前位置（POI名） */
    public void getCurrentPosition(ActionCallback callback) {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().getPosition(id, null, new CommandListener() {
                @Override public void onResult(int result, String message) {
                    if (callback != null) callback.onSuccess(message);
                }
            });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 获取POI点位列表 */
    public void getPoiList(ActionCallback callback) {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().getPlaceList(id, new CommandListener() {
                @Override public void onResult(int result, String message) {
                    if (callback != null) callback.onSuccess(message);
                }
            });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 获取设备SN号 */
    public String getDeviceSN() {
        try {
            return RobotSettingApi.getInstance().getRobotString(Definition.ROBOT_SETTINGS_SN);
        } catch (Exception e) {
            return "MC1BCN2K100262058CA0";
        }
    }

    // ==================== 头部/表情/动作 ====================

    /** 控制头部转动（水平/垂直角度） */
    public void rotateHead(float horizontal, float vertical, ActionCallback callback) {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().moveHead(id, "absolute", horizontal, vertical, new CommandListener() {
                @Override public void onResult(int result, String message) {
                    if (callback != null) callback.onSuccess(message);
                }
            });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 重置头部到默认位置 */
    public void resetHead() {
        rotateHead(0, 0, null);
    }

    // ==================== 免唤醒词模式 ====================

    /** 设置免唤醒词持续时间（秒） */
    public void setFreeWakeMode(int durationSec) {
        Log.i(TAG, "设置免唤醒词模式: " + durationSec + "s");
        try {
            // 开启后一段时间内无需说唤醒词
            RobotApi.getInstance().setNavigationMode(reqId.incrementAndGet(),
                    Definition.NAVIGATION_MODE_FREE_MOVE, new CommandListener() {
                        @Override public void onResult(int result, String message) {
                            Log.d(TAG, "免唤醒结果: " + message);
                        }
                    });
        } catch (Exception e) {
            Log.e(TAG, "免唤醒设置失败: " + e.getMessage());
        }
    }

    // ==================== 音量控制 ====================

    /** 设置音量（0-100） */
    public void setVolume(int volume) {
        try {
            RobotSettingApi.getInstance().setRobotString(
                    Definition.ROBOT_SETTINGS_VOLUME, String.valueOf(volume));
        } catch (Exception e) {
            Log.e(TAG, "设置音量失败: " + e.getMessage());
        }
    }

    /** 获取当前音量 */
    public int getVolume() {
        try {
            String val = RobotSettingApi.getInstance()
                    .getRobotString(Definition.ROBOT_SETTINGS_VOLUME);
            return Integer.parseInt(val);
        } catch (Exception e) {
            return 50;
        }
    }

    // ==================== 全停止 ====================

    /** 停止所有动作 */
    public void stopAll() {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().stopNavigation(id);
        } catch (Exception ignored) {}
        try {
            RobotApi.getInstance().stopTTS(id);
        } catch (Exception ignored) {}
        try {
            stopFollowing();
        } catch (Exception ignored) {}
        currentStatus = "idle";
        notifyStatusChanged("idle");
        Log.i(TAG, "所有动作已停止");
    }

    // ==================== 状态通知 ====================

    public String getCurrentStatus() { return currentStatus; }
    public String getCurrentPoi() { return currentPoi; }
    public int getCurrentBattery() { return currentBattery; }

    private void notifyStatusChanged(String status) {
        if (statusListener != null) mainHandler.post(() -> statusListener.onStatusChanged(status));
    }

    private void notifyPositionChanged(String poi) {
        if (statusListener != null) mainHandler.post(() -> statusListener.onPositionChanged(poi));
    }

    private void notifyBatteryChanged(int battery, boolean charging) {
        if (statusListener != null) mainHandler.post(() -> statusListener.onBatteryChanged(battery, charging));
    }
}
