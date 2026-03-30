import logging
from openai import AsyncOpenAI
from config import get_config

logger = logging.getLogger(__name__)

QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

INTENT_KEYWORDS = {
    'lights_off': ['灯全关', '关灯', '关所有灯', '灯全部关', '关掉所有灯', '关闭所有灯', '关闭灯光', '灯关'],
    'lights_on': ['灯全开', '开灯', '开所有灯', '灯全部开', '打开所有灯', '开启灯光', '灯开'],
    'devices_on': ['设备全开', '全部开机', '开机', '启动设备', '开启所有设备'],
    'devices_off': ['设备全关', '全部关机', '关机', '关闭设备', '关闭所有设备'],
    'list_files': ['有哪些文件', '有什么文件', '有哪些内容', '有什么内容', '有什么资料', '给我看看', '这里有什么', '展示什么', '能看什么'],
    'next_exhibit': ['下一个', '继续参观', '往前走', '去下一个'],
    'prev_exhibit': ['上一个', '回上一个', '去上一个'],
    'start_tour': ['开始参观', '陪我参观', '带我参观', '参观展厅', '带我逛'],
    'go_home': ['回到入口', '回原位'],
    'go_charge': ['去充电', '回去充电'],
    'repeat': ['再说一遍', '重复一下', '再讲一遍', '没听清'],
    'stop': ['停', '停止', '好了', '不用了', '知道了', '够了'],
    'continue': ['继续', '接着说', '继续讲'],
    'select': ['第一个', '第二个', '第三个', '第四个', '第五个', '第六个', '第七个', '第八个', '第九个', '第十个', '最后一个'],
    'narrate': ['讲解一下', '介绍一下', '讲解这个', '介绍这个', '讲解', '说一说', '给我讲讲'],
    'narrate_select': ['讲解第一个', '讲解第二个', '讲解第三个', '讲解第四个', '讲解第五个',
                       '介绍第一个', '介绍第二个', '介绍第三个'],
    'scene_switch': ['切换专场', '换专场', '切换到', '换到'],
    'query_scene': ['现在什么专场', '当前专场', '有哪些专场', '专场列表', '有什么专场'],
    'query_exhibits': ['有哪些展位', '展位列表', '哪些展位', '有什么展位'],
    'query_progress': ['参观到哪了', '参观进度', '现在在哪', '到哪了'],
    'query_status': ['系统状态', '机器人状态', '状态怎么样'],
    'media_play': ['播放', '开始播放'],
    'media_pause': ['暂停', '暂停一下', '先停'],
    'media_prev': ['上一页', '上一张', '上一个画面'],
    'media_next': ['下一页', '下一张', '下一个画面'],
    'media_mute': ['静音', '关掉声音', '不要声音'],
    'media_vol_up': ['音量大', '大声点', '音量加', '声音大'],
    'media_vol_down': ['音量小', '小声点', '音量减', '声音小'],
    'device_ad': ['开广告机', '打开广告机', '广告机开', '广告屏开'],
    'help': ['帮助', '你能做什么', '有什么功能', '怎么用', '使用说明'],
}

NARRATE_INDEX_MAP = {'讲解第一个': 1, '讲解第二个': 2, '讲解第三个': 3, '讲解第四个': 4, '讲解第五个': 5,
    '介绍第一个': 1, '介绍第二个': 2, '介绍第三个': 3}

SELECT_INDEX_MAP = {
    '第一个': 1, '第二个': 2, '第三个': 3, '第四个': 4, '第五个': 5,
    '第六个': 6, '第七个': 7, '第八个': 8, '第九个': 9, '第十个': 10, '最后一个': -1
}


def keyword_match(text: str) -> tuple[str, dict]:
    """关键词匹配意图"""
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                extra = {}
                if intent == 'select':
                    idx = SELECT_INDEX_MAP.get(kw, 1)
                    extra = {"index": idx}
                elif intent == 'narrate_select':
                    idx = NARRATE_INDEX_MAP.get(kw, 1)
                    extra = {"index": idx}
                return intent, extra
    return None, {}


async def recognize_intent(text: str, context: dict = None) -> dict:
    """意图识别：先关键词，后AI"""
    # 1. 关键词快速匹配
    intent, extra = keyword_match(text)
    if intent:
        logger.info(f"Keyword matched intent: {intent} for '{text}'")
        return {"intent": intent, "text": text, "extra": extra, "method": "keyword"}

    # 2. AI意图识别
    try:
        qwen_key = await get_config("ai.qwen_key") or "sk-845c78e1c9a749ba901c5ce3d68f4a33"
        qwen_model = await get_config("ai.qwen_model") or "qwen-plus-latest"

        client = AsyncOpenAI(api_key=qwen_key, base_url=QWEN_BASE_URL)

        system_prompt = """你是展厅导览机器人的意图识别模块。
根据用户输入，识别以下意图之一：
- list_files: 查看文件/内容/资料
- next_exhibit: 去下一个展项
- prev_exhibit: 去上一个展项
- start_tour: 开始参观
- go_home: 回到入口/原位
- go_charge: 去充电
- repeat: 重复讲解
- stop: 停止/结束
- continue: 继续讲解
- select: 选择某个选项（返回index字段）
- query_exhibit: 询问某个展项（返回exhibit_name字段）
- narrate: 讲解当前展项
- narrate_select: 讲解第N个（返回index字段）
- scene_switch: 切换专场（返回scene_name字段）
- query_scene: 查询当前/所有专场
- query_exhibits: 查询展位列表
- query_progress: 查询参观进度
- query_status: 查询系统状态
- media_play/media_pause/media_prev/media_next/media_mute/media_vol_up/media_vol_down: 媒体控制
- device_ad: 开广告机
- help: 帮助菜单
- unknown: 无法识别

只返回JSON格式：{"intent": "xxx", "extra": {}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        response = await client.chat.completions.create(
            model=qwen_model,
            messages=messages,
            temperature=0.1,
            max_tokens=200
        )

        result_text = response.choices[0].message.content.strip()
        # 解析JSON
        import json
        try:
            result = json.loads(result_text)
            result["text"] = text
            result["method"] = "ai"
            logger.info(f"AI matched intent: {result.get('intent')} for '{text}'")
            return result
        except json.JSONDecodeError:
            logger.warning(f"AI returned non-JSON: {result_text}")
            return {"intent": "unknown", "text": text, "extra": {}, "method": "ai"}

    except Exception as e:
        logger.error(f"AI intent recognition failed: {e}")
        return {"intent": "unknown", "text": text, "extra": {}, "method": "error", "error": str(e)}
