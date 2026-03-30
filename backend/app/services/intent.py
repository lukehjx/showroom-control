"""
意图识别服务
优先级：关键词 > LLM分类 > unknown兜底
"""
import re
import asyncio
from openai import AsyncOpenAI
from ..config import settings

# ─── 关键词意图映射 ──────────────────────────────────────────
KEYWORD_INTENTS = [
    # 文件/内容查询
    (["有哪些文件", "有哪些内容", "都有什么", "有什么内容", "文件列表", "内容列表"], "list_files"),

    # 按序号选择
    (["第一个", "第1个", "1号", "第一"], "select_item_1"),
    (["第二个", "第2个", "2号", "第二"], "select_item_2"),
    (["第三个", "第3个", "3号", "第三"], "select_item_3"),
    (["第四个", "第4个", "4号", "第四"], "select_item_4"),
    (["第五个", "第5个", "5号", "第五"], "select_item_5"),

    # 导览控制
    (["开始参观", "开始导览", "开始参观", "出发"], "start_tour"),
    (["下一个", "去下一个", "下一站", "继续参观"], "tour_next"),
    (["上一个", "回上一个", "上一站", "回去"], "tour_prev"),
    (["停止", "停下", "暂停", "别动", "停一下"], "stop"),
    (["继续", "继续导览", "接着走"], "resume"),

    # 位置控制
    (["回入口", "去入口", "回到入口", "到入口"], "go_entry"),
    (["去充电", "回充电", "充电", "充电桩"], "go_charge"),

    # 讲解控制
    (["再说一遍", "重复一遍", "再讲一遍", "再说"], "repeat"),
    (["停止讲解", "别说了", "停止播放"], "stop_narrate"),

    # 灯光设备
    (["开灯", "把灯打开", "灯打开"], "lights_on"),
    (["关灯", "把灯关上", "灯关上"], "lights_off"),
    (["全开", "设备全开", "一键开馆", "开馆"], "all_on"),
    (["全关", "设备全关", "一键关馆", "关馆"], "all_off"),

    # 帮助
    (["帮助", "你能做什么", "功能", "怎么用"], "help"),
]

# 数字中文映射
NUM_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

def match_keywords(text: str) -> tuple[str, dict]:
    """关键词匹配，返回 (intent, params)"""
    text = text.strip()

    # 先尝试"第N个"动态匹配
    m = re.search(r"第([一二三四五六七八九十\d]+)个", text)
    if m:
        num_str = m.group(1)
        if num_str.isdigit():
            n = int(num_str)
        else:
            n = NUM_MAP.get(num_str, 1)
        return "select_item", {"index": n}

    # 关键词表匹配
    for keywords, intent in KEYWORD_INTENTS:
        for kw in keywords:
            if kw in text:
                return intent, {}

    # 展项名称识别（"去XXX" / "讲一下XXX" / "XXX介绍"）
    m = re.search(r"(?:去|参观|讲一下|介绍一下|了解|看看)?(.{2,10})(?:展项|展位|展区|那里|那边|的内容|的讲解)?", text)
    if m and len(text) <= 20:
        return "navigate_to_exhibit", {"exhibit_name": m.group(1).strip()}

    # 专场切换识别
    m = re.search(r"切换(.{2,20})专场|切换到(.{2,20})|(.{2,20})专场", text)
    if m:
        name = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if name:
            return "switch_scene", {"scene_name": name}

    return "", {}


INTENT_CLASSIFY_PROMPT = """你是一个展厅语音助手意图识别器。根据用户输入，返回最匹配的意图类型。

可选意图：
- list_files: 查询当前展项有哪些文件/内容
- select_item: 选择第N个文件（附带index参数）
- start_tour: 开始自动导览
- tour_next: 去下一个展项
- tour_prev: 回上一个展项
- stop: 停止当前动作
- resume: 继续上次动作
- go_entry: 回到展厅入口
- go_charge: 机器人去充电
- repeat: 再说一遍
- stop_narrate: 停止讲解
- lights_on: 开灯
- lights_off: 关灯
- all_on: 全部设备开启
- all_off: 全部设备关闭
- navigate_to_exhibit: 去指定展项（附带exhibit_name）
- switch_scene: 切换专场（附带scene_name）
- query_status: 查询机器人/系统状态
- chitchat: 闲聊，无需执行动作
- unknown: 无法理解

只返回JSON格式：{"intent": "xxx", "params": {}, "confidence": 0.9}
不要解释，只返回JSON。"""


async def classify_with_llm(text: str) -> tuple[str, dict]:
    """用LLM做意图分类，超时返回unknown"""
    client = AsyncOpenAI(
        api_key=settings.QWEN_API_KEY,
        base_url=settings.QWEN_BASE_URL,
    )
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.QWEN_MODEL,
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFY_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                temperature=0.1,
            ),
            timeout=settings.QWEN_TIMEOUT
        )
        import json
        raw = resp.choices[0].message.content.strip()
        # 提取JSON
        m = re.search(r'\{.*\}', raw, re.S)
        if m:
            data = json.loads(m.group())
            return data.get("intent", "unknown"), data.get("params", {})
    except Exception:
        pass
    return "unknown", {}


async def recognize_intent(text: str) -> tuple[str, dict]:
    """主入口：关键词优先，fallback LLM"""
    intent, params = match_keywords(text)
    if intent:
        return intent, params
    # LLM兜底
    return await classify_with_llm(text)
