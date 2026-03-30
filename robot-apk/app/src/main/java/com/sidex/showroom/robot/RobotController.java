package com.sidex.showroom.robot;

import android.content.Context;
import android.util.Log;

import com.ainirobot.coreservice.client.RobotApi;
import com.ainirobot.coreservice.client.listener.CommandListener;
import com.ainirobot.coreservice.client.listener.NavigationListener;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 机器人SDK控制封装
 * 对接猎户星空 RobotService.jar
 */
public class RobotController {
    private static final String TAG = "RobotCtrl";
    private static RobotController instance;
    private final AtomicInteger reqId = new AtomicInteger(0);

    // 回调接口
    public interface ActionCallback {
        void onSuccess(String data);
        void onFail(String reason);
    }

    private RobotController() {}

    public static RobotController getInstance() {
        if (instance == null) instance = new RobotController();
        return instance;
    }

    /** 导航到POI点位 */
    public void navigateTo(String poiName, ActionCallback callback) {
        int id = reqId.incrementAndGet();
        Log.i(TAG, "导航到: " + poiName);
        try {
            RobotApi.getInstance().startNavigation(id, poiName, 0.3f, 60000,
                    new NavigationListener() {
                        @Override
                        public void onSuccess(String destination) {
                            Log.i(TAG, "导航成功: " + destination);
                            if (callback != null) callback.onSuccess(destination);
                        }
                        @Override
                        public void onFail(int error) {
                            Log.e(TAG, "导航失败: " + error);
                            if (callback != null) callback.onFail("error:" + error);
                        }
                        @Override
                        public void onStatusUpdate(int status) {
                            Log.d(TAG, "导航状态: " + status);
                        }
                    });
        } catch (Exception e) {
            Log.e(TAG, "导航调用失败: " + e.getMessage());
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** TTS播报 */
    public void speak(String text, ActionCallback callback) {
        int id = reqId.incrementAndGet();
        Log.i(TAG, "TTS: " + text);
        try {
            RobotApi.getInstance().playText(id, text, new CommandListener() {
                @Override
                public void onResult(int result, String message) {
                    if ("succeed".equals(message)) {
                        Log.i(TAG, "TTS完成");
                        if (callback != null) callback.onSuccess("done");
                    } else {
                        Log.e(TAG, "TTS失败: " + message);
                        if (callback != null) callback.onFail(message);
                    }
                }
            });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 停止所有动作 */
    public void stop() {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().stopNavigation(id);
            RobotApi.getInstance().stopTTS(id);
        } catch (Exception ignored) {}
    }

    /** 自动回充 */
    public void goCharge(ActionCallback callback) {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().startNaviToAutoChargeAction(id, 120000,
                    (status, responseString) -> {
                        if (status == 0) {
                            if (callback != null) callback.onSuccess("charging");
                        } else {
                            if (callback != null) callback.onFail("charge fail: " + status);
                        }
                        return null;
                    });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 获取当前电量 */
    public int getBattery() {
        try {
            String val = com.ainirobot.coreservice.client.robotsetting.RobotSettingApi.getInstance()
                    .getRobotString(com.ainirobot.coreservice.client.Definition.ROBOT_SETTINGS_BATTERY_INFO);
            return Integer.parseInt(val.replace("%", "").trim());
        } catch (Exception e) {
            return -1;
        }
    }

    /** 获取当前位置 */
    public void getCurrentPosition(ActionCallback callback) {
        int id = reqId.incrementAndGet();
        try {
            RobotApi.getInstance().getPosition(id, null, new CommandListener() {
                @Override
                public void onResult(int result, String message) {
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
                @Override
                public void onResult(int result, String message) {
                    if (callback != null) callback.onSuccess(message);
                }
            });
        } catch (Exception e) {
            if (callback != null) callback.onFail(e.getMessage());
        }
    }

    /** 设置免唤醒词模式（秒） */
    public void setFreeWakeMode(int durationSec) {
        // 通过RobotOS接口或系统广播实现
        // 具体实现依赖RobotOS版本
        Log.i(TAG, "设置免唤醒词模式: " + durationSec + "s");
    }
}
