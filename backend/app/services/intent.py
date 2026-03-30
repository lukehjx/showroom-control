"""
意图识别服务 - 青田城市共享客厅展厅智控系统
流程：关键词精确匹配 → 正则扩展匹配 → Qwen语义分析 → unknown兜底
"""
import re
import json
import logging
import asyncio
import aiohttp
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

QWEN_TIMEOUT = 5  # 5秒超时


# ==================== 意图定义 ====================

INTENTS = {
    # ── 导览相关 ──────────────────────────────────────────────────────────
    "start_tour":       "开始自动导览（按预设路线）",
    "stop_tour":        "停止/暂停导览",
    "next_stop":        "下一站/继续",
    "prev_stop":        "上一站/返回",
    "goto_position":    "导航到指定点位（需提取poi参数）",
    "goto_entrance":    "回到入口",
    "goto_charge":      "去充电桩充电",

    # ── 展项讲解 ──────────────────────────────────────────────────────────
    "start_explain":    "开始讲解（当前展项或指定展项）",
    "stop_explain":     "停止讲解",
    "repeat_explain":   "重复刚才的讲解",
    "explain_exhibit":  "讲解指定展项（需提取展项名）",

    # ── 场景控制 ──────────────────────────────────────────────────────────
    "open_hall":        "一键开馆（灯光+设备全开）",
    "close_hall":       "一键关馆（灯光+设备全关）",
    "lights_on":        "打开灯光",
    "lights_off":       "关闭灯光",
    "devices_on":       "开启所有设备/屏幕",
    "devices_off":      "关闭所有设备/屏幕",
    "ads_on":           "开启广告机",
    "ads_off":          "关闭广告机",
    "standby":          "一键待展（待机状态）",
    "switch_special":   "切换专场（需提取专场名）",

    # ── 机器人控制 ────────────────────────────────────────────────────────
    "robot_stop":       "停止机器人当前动作",
    "robot_follow":     "开启跟随模式",
    "robot_stop_follow":"停止跟随",
    "robot_status":     "查询机器人状态",
    "robot_dance":      "机器人跳舞/表演",
    "set_volume":       "调整音量（需提取数值）",
    "volume_up":        "调大音量",
    "volume_down":      "调小音量",

    # ── 接待服务 ──────────────────────────────────────────────────────────
    "start_reception":  "开始接待（按接待套餐）",
    "vip_reception":    "VIP接待模式",
    "welcome":          "播放欢迎词",
    "goodbye":          "送客/告别",

    # ── 问答 ──────────────────────────────────────────────────────────────
    "ask_about":        "询问展厅相关内容",
    "ask_company":      "询问思德科技公司",
    "ask_weather":      "询问天气",
    "ask_time":         "询问时间/日期",
    "chitchat":         "闲聊/问候",
    "who_are_you":      "询问机器人是谁",

    # ── 系统 ──────────────────────────────────────────────────────────────
    "system_status":    "查询系统状态",
    "sync_data":        "同步中控数据",
    "unknown":          "未识别意图，使用AI自由问答",
}


# ==================== 关键词 + 正则匹配规则 ====================

# 格式：(intent, [关键词列表], [正则列表])
KEYWORD_RULES = [
    # 导览
    ("start_tour",      ["开始导览", "开始参观", "出发", "带我参观", "开始巡游", "自动导览", "开始讲解之旅", "带我转转"],
                        [r"开始.{0,4}导览", r"带.{0,2}参观"]),
    ("stop_tour",       ["停止导览", "停下来", "暂停", "别走了", "停在这里", "先等一下"],
                        [r"停(止|下).{0,4}(导览|参观|巡)"]),
    ("next_stop",       ["下一站", "继续走", "往前走", "下一个", "继续", "走吧", "去下一个"],
                        [r"下一.{0,2}(站|个|展|处)"]),
    ("prev_stop",       ["上一站", "往回走", "返回上一个", "回去"],
                        [r"上一.{0,2}(站|个)"]),
    ("goto_entrance",   ["回入口", "回到入口", "去入口", "回门口", "回到大门"],
                        [r"回.{0,3}(入口|门口|大门|起点)"]),
    ("goto_charge",     ["去充电", "充电", "回充电桩", "电快没了", "低电量"],
                        [r"(去|回).{0,3}充电"]),

    # 展项讲解
    ("start_explain",   ["开始讲解", "讲一下", "介绍一下", "说说这个", "讲讲这个", "解说", "介绍", "讲解"],
                        [r"(讲|介绍|解说).{0,4}(这|此|一下)"]),
    ("stop_explain",    ["停止讲解", "别讲了", "停止介绍", "不用讲了"],
                        [r"停.{0,3}(讲|介绍|解说)"]),
    ("repeat_explain",  ["再说一遍", "重复", "没听清", "再讲一次", "重来"],
                        [r"再.{0,3}(说|讲|来).{0,2}(遍|次)"]),

    # 场景控制
    ("open_hall",       ["一键开馆", "开馆", "开门", "全部开", "都开", "展馆开"],
                        [r"一键开", r"全(部|都).{0,3}开"]),
    ("close_hall",      ["一键关馆", "关馆", "关门", "全部关", "都关", "展馆关"],
                        [r"一键关", r"全(部|都).{0,3}关"]),
    ("lights_on",       ["开灯", "灯打开", "灯光打开", "亮灯", "把灯开"],
                        [r"(开|打开).{0,2}灯", r"灯.{0,2}(开|亮)"]),
    ("lights_off",      ["关灯", "灯关掉", "把灯关", "灭灯", "关闭灯光"],
                        [r"(关|关闭|熄灭).{0,2}灯", r"灯.{0,2}(关|灭)"]),
    ("devices_on",      ["开屏幕", "打开屏幕", "开设备", "屏幕开", "开启设备"],
                        [r"(开|打开).{0,3}(屏|设备|显示)"]),
    ("devices_off",     ["关屏幕", "关设备", "屏幕关", "关闭设备"],
                        [r"(关|关闭).{0,3}(屏|设备|显示)"]),
    ("ads_on",          ["开广告", "广告机开", "打开广告"],
                        [r"(开|打开).{0,3}广告"]),
    ("ads_off",         ["关广告", "广告机关", "关闭广告"],
                        [r"(关|关闭).{0,3}广告"]),
    ("standby",         ["待展", "待机", "待命", "进入待展"],
                        [r"一键待展"]),

    # 机器人控制
    ("robot_stop",      ["停", "停下", "住", "停止", "不要动", "原地不动"],
                        [r"^(停|住|停下|停止)$"]),
    ("robot_follow",    ["跟我走", "跟着我", "跟随", "跟过来"],
                        [r"跟.{0,2}(我|着).{0,3}(走|来)"]),
    ("robot_stop_follow", ["停止跟随", "别跟了", "不用跟了"],
                        [r"停.{0,3}跟(随|着)"]),
    ("robot_status",    ["你在哪", "电量多少", "状态怎么样", "你好吗", "状态查询"],
                        [r"(电量|电池).{0,4}(多少|几|剩)", r"你.{0,3}在(哪|哪里)"]),
    ("volume_up",       ["调大声", "大声点", "音量大", "声音大"],
                        [r"(调大|大).{0,2}(声|音量|音量)", r"声音.{0,2}(大|响)"]),
    ("volume_down",     ["调小声", "小声点", "音量小", "声音小"],
                        [r"(调小|小).{0,2}(声|音量)", r"声音.{0,2}(小|轻)"]),

    # 接待
    ("welcome",         ["欢迎词", "欢迎语", "播放欢迎", "欢迎来到"],
                        [r"(播放|来一段|说).{0,3}欢迎"]),
    ("vip_reception",   ["VIP接待", "领导参观", "重要客人", "贵宾"],
                        [r"VIP|贵宾|领导.{0,2}参观"]),
    ("goodbye",         ["再见", "拜拜", "送客", "参观结束", "谢谢参观"],
                        [r"(再见|拜拜|谢谢.{0,3}参观)"]),

    # 问答
    ("who_are_you",     ["你是谁", "你叫什么", "自我介绍", "介绍你自己", "你叫什么名字"],
                        [r"你(是|叫).{0,4}(谁|什么|哪)"]),
    ("ask_company",     ["思德", "思德科技", "公司介绍", "公司是什么"],
                        [r"思德.{0,3}(是|介绍|科技|公司)"]),
    ("ask_weather",     ["天气", "今天天气", "下雨"],
                        [r"(今天|明天|后天).{0,3}天气"]),
    ("ask_time",        ["几点了", "现在几点", "今天几号", "今天星期几"],
                        [r"(几点|几号|星期几|现在时间)"]),
    ("chitchat",        ["你好", "hi", "hello", "嗨", "哈喽"],
                        [r"^(你好|hi|hello|嗨|哈喽|早上好|下午好|晚上好)$"]),
    ("system_status",   ["系统状态", "查看状态", "运行状态"],
                        [r"系统.{0,3}状态"]),
    ("sync_data",       ["同步数据", "刷新数据", "更新数据"],
                        [r"(同步|刷新|更新).{0,3}数据"]),
]


# ==================== 参数提取 ====================

# poi 提取
POI_KEYWORDS = {
    "入口": ["入口", "门口", "大门", "正门"],
    "大岛台": ["大岛台", "大岛", "主展台"],
    "小岛台": ["小岛台", "小岛"],
    "CAVE": ["cave", "CAVE", "洞穴", "沉浸厅", "沉浸空间"],
    "阿里中心": ["阿里", "阿里中心"],
}

SPECIAL_KEYWORDS = {
    "思德专场": ["思德", "思德专场"],
    "节能专场": ["节能", "节能专场", "能源"],
    "招商专场": ["招商", "招商专场", "招商引资"],
}


def extract_poi(text: str) -> Optional[str]:
    for poi_name, keywords in POI_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text.lower():
                return poi_name
    return None


def extract_special(text: str) -> Optional[str]:
    for name, keywords in SPECIAL_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return name
    return None


def extract_volume(text: str) -> Optional[int]:
    m = re.search(r'(\d+)', text)
    if m:
        v = int(m.group(1))
        return max(0, min(100, v))
    return None


# ==================== 主识别函数 ====================

async def recognize_intent(text: str) -> dict:
    """
    返回：{intent, confidence, params, raw_text}
    """
    text = text.strip()
    if not text:
        return {"intent": "unknown", "confidence": 0.0, "params": {}, "raw_text": text}

    # 1. 关键词 + 正则匹配（最快，优先）
    result = _keyword_match(text)
    if result and result["confidence"] >= 0.9:
        logger.debug(f"关键词匹配: {text} → {result['intent']}")
        return result

    # 2. Qwen语义分析（5秒超时）
    try:
        qwen_result = await asyncio.wait_for(_qwen_intent(text), timeout=QWEN_TIMEOUT)
        if qwen_result and qwen_result.get("confidence", 0) >= 0.7:
            logger.info(f"Qwen识别: {text} → {qwen_result['intent']}")
            return qwen_result
    except asyncio.TimeoutError:
        logger.warning(f"Qwen超时，回落关键词结果: {text}")
    except Exception as e:
        logger.error(f"Qwen识别异常: {e}")

    # 3. 关键词低置信度结果 or unknown
    if result:
        return result

    return {"intent": "unknown", "confidence": 0.0, "params": {}, "raw_text": text}


def _keyword_match(text: str) -> Optional[dict]:
    text_lower = text.lower()
    for intent, keywords, patterns in KEYWORD_RULES:
        # 关键词匹配
        for kw in keywords:
            if kw.lower() in text_lower:
                params = _extract_params(intent, text)
                return {"intent": intent, "confidence": 0.95, "params": params, "raw_text": text}
        # 正则匹配
        for pattern in patterns:
            if re.search(pattern, text):
                params = _extract_params(intent, text)
                return {"intent": intent, "confidence": 0.90, "params": params, "raw_text": text}

    # 展项名称匹配
    exhibit_kws = ["岛台", "大屏", "展项", "展区", "CAVE", "cave"]
    for kw in exhibit_kws:
        if kw.lower() in text_lower and ("讲" in text or "介绍" in text or "播放" in text):
            poi = extract_poi(text)
            return {"intent": "explain_exhibit",
                    "confidence": 0.85,
                    "params": {"exhibit": text, "poi": poi},
                    "raw_text": text}

    # 专场切换匹配
    if extract_special(text) and ("切换" in text or "换" in text or "播" in text):
        return {"intent": "switch_special",
                "confidence": 0.90,
                "params": {"special_name": extract_special(text)},
                "raw_text": text}

    # 导航意图匹配
    poi = extract_poi(text)
    if poi and any(kw in text for kw in ["去", "到", "走到", "导航", "带我去", "去一下"]):
        return {"intent": "goto_position",
                "confidence": 0.90,
                "params": {"poi": poi},
                "raw_text": text}

    return None


def _extract_params(intent: str, text: str) -> dict:
    params = {}
    if intent in ("goto_position", "start_tour"):
        poi = extract_poi(text)
        if poi:
            params["poi"] = poi
    if intent == "switch_special":
        sp = extract_special(text)
        if sp:
            params["special_name"] = sp
    if intent == "set_volume":
        vol = extract_volume(text)
        if vol is not None:
            params["volume"] = vol
    if intent == "explain_exhibit":
        params["exhibit_hint"] = text
    return params


async def _qwen_intent(text: str) -> Optional[dict]:
    """调用Qwen API做意图识别"""
    intent_list = "\n".join([f"- {k}: {v}" for k, v in INTENTS.items()])
    poi_list = ", ".join(POI_KEYWORDS.keys())
    special_list = ", ".join(SPECIAL_KEYWORDS.keys())

    system_prompt = f"""你是青田城市共享客厅展厅智控系统的意图识别引擎。

已知意图列表：
{intent_list}

已知POI点位：{poi_list}
已知专场：{special_list}

用户输入后，返回JSON格式：
{{"intent": "意图名称", "confidence": 0.0-1.0, "params": {{}}, "reasoning": "简要说明"}}

规则：
1. 优先匹配明确的展厅相关意图
2. 闲聊或无法识别的返回 unknown，confidence < 0.5
3. 需要提取参数的意图在params里填写：poi/special_name/volume/exhibit_name等
4. 不要返回JSON以外的内容"""

    payload = {
        "model": settings.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.QWEN_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.QWEN_API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=QWEN_TIMEOUT),
            ) as resp:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # 提取JSON
                m = re.search(r'\{.*\}', content, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    return {
                        "intent": result.get("intent", "unknown"),
                        "confidence": float(result.get("confidence", 0.5)),
                        "params": result.get("params", {}),
                        "raw_text": text,
                    }
    except Exception as e:
        logger.error(f"Qwen API错误: {e}")

    return None
