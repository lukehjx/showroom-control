"""
数据预设脚本 - 展厅智控系统初始化数据
运行：python3 seed_data.py

预设内容：
1. 导览路线（4站：入口三联屏→小岛台→大岛台→CAVE）
2. 接待套餐（3套：标准/VIP/简单）
3. 展项讲解词（从中控同步的真实数据）
4. 系统配置（企微Bot群/通知配置）
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal, init_db
from app.models import (
    TourRoute, TourStop, ReceptionPreset, ExhibitScript, ExhibitItem,
    SystemSetting, NavPosition, NotifyGroup
)
from sqlalchemy import select, delete


async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        print("开始写入预设数据...")

        # ── 1. 导览路线 ──────────────────────────────────────────────────────
        await db.execute(delete(TourStop))
        await db.execute(delete(TourRoute))
        await db.commit()

        route = TourRoute(
            name="标准导览路线",
            description="青田城市共享客厅标准接待路线：入口三联屏→小岛台→大岛台→CAVE",
            enabled=True,
            sort=0,
        )
        db.add(route)
        await db.flush()

        stops_data = [
            {
                "sort": 1,
                "poi_name": "入口三联屏",
                "display_name": "入口展示区",
                "duration_sec": 120,
                "script": "欢迎来到青田城市共享客厅！这里是全国首个区县级智能化共享展厅，由浙江思德数字科技有限公司打造。入口三联大屏展示了展厅全貌和核心功能介绍。这个展厅以极低的成本为政府、园区和企业提供高品质的展示交流服务，我们相信，中国每个区县都应该有一个这样的共享客厅。",
                "auto_explain": True,
            },
            {
                "sort": 2,
                "poi_name": "小岛台",
                "display_name": "小岛台展示区",
                "duration_sec": 180,
                "script": "AI赋能，志展万像！AI赋能展厅包括三个层级，第一是展厅的内容生产采用AIGC，让内容生产更高效；第二是用基于知识库、大模型和数字人实现智能讲解；第三是用AI实现智能策展，千人千面。现在屏幕上看到的机器人叫做"云猴"，它是城市共享客厅的IP形象，"云"代表了数字化的基因；"猴"来源于齐天大圣孙悟空，可以做七十二般变化。",
                "auto_explain": True,
            },
            {
                "sort": 3,
                "poi_name": "大岛台",
                "display_name": "大岛台核心展区",
                "duration_sec": 240,
                "script": "我们为展厅开发了一个小程序，称之为手机上的展厅，伴随参观的展前、展中和展后全过程，极大提升了访客和工作人员的用户体验。展前，提供定场、邀约、报名以及内容预览、VR漫游等在线体验；展中，提供导航导览、智能讲解、手机播控等服务，授权后的手机可以控制现场的灯光音响、屏幕和设备；展后，参观结束后会在小程序上生成相应的"参观报告"，包括访客基本信息、参观动线、感兴趣的内容和合影照片等内容。",
                "auto_explain": True,
            },
            {
                "sort": 4,
                "poi_name": "CAVE",
                "display_name": "CAVE沉浸式空间",
                "duration_sec": 300,
                "script": "欢迎进入CAVE沉浸式体验空间！这是展厅最独特的体验区域，采用360度环绕投影技术，将数字内容投影在四面墙体上，让参观者身临其境地感受数智化的未来世界。CAVE空间可以展示城市规划、智慧园区、数字孪生等宏大叙事内容，是政府领导和企业客户最喜爱的展示空间之一。",
                "auto_explain": True,
            },
        ]

        for stop_data in stops_data:
            stop = TourStop(
                route_id=route.id,
                sort=stop_data["sort"],
                poi_name=stop_data["poi_name"],
                display_name=stop_data["display_name"],
                duration_sec=stop_data["duration_sec"],
                script=stop_data["script"],
                auto_explain=stop_data["auto_explain"],
            )
            db.add(stop)

        await db.commit()
        print(f"✅ 导览路线已写入：{route.name}（{len(stops_data)}站）")

        # ── 2. 展项讲解词（对应4个点位）──────────────────────────────────────
        await db.execute(delete(ExhibitItem))
        await db.execute(delete(ExhibitScript))
        await db.commit()

        scripts_data = [
            {
                "title": "入口展示区 - 展厅概述",
                "poi_name": "入口三联屏",
                "terminal_name": "入口三联屏",
                "commentary": "欢迎各位领导莅临参观青田城市共享客厅！这是浙江思德数字科技有限公司在青田打造的、全国首个区县级的智能化共享展厅，为政府、园区和企业提供低成本、高品质的展示交流服务，政企客户可以极低的成本租用这个展厅，开展商务接待和文化交流活动，我们认为中国每个区县都应该有一个共享客厅。",
                "ai_explain": True,
                "keywords": ["展厅", "思德", "共享客厅", "青田"],
                "enabled": True,
                "sort": 1,
                "items": [
                    {"title": "展厅概述", "exhibit_type": "image", "sort": 1, "enabled": True},
                    {"title": "思德科技介绍", "exhibit_type": "video", "sort": 2, "enabled": True},
                ],
            },
            {
                "title": "小岛台 - AI赋能展区",
                "poi_name": "小岛台",
                "terminal_name": "小岛台正面",
                "commentary": "AI赋能，志展万像！AI赋能展厅包括三个层级：第一是展厅的内容生产采用AIGC，让内容生产更高效；第二是用基于知识库、大模型和数字人实现智能讲解；第三是用AI实现智能策展，千人千面。现在屏幕上看到的机器人叫做"云猴"，它是城市共享客厅的IP形象，"云"代表了数字化的基因；"猴"来源于齐天大圣孙悟空，可以做七十二般变化，"云猴"寓意着城市共享客厅以数字化的百变空间服务广大政企客户。",
                "ai_explain": True,
                "keywords": ["AI", "AIGC", "智能", "云猴", "小岛台"],
                "enabled": True,
                "sort": 2,
                "items": [
                    {"title": "小岛台正面", "exhibit_type": "image", "exhibit_id": 826, "sort": 1, "enabled": True},
                    {"title": "AI赋能展示", "exhibit_type": "video", "sort": 2, "enabled": True},
                ],
            },
            {
                "title": "大岛台 - 核心产品区",
                "poi_name": "大岛台",
                "terminal_name": "大岛台正面",
                "commentary": "我们为展厅开发了一个小程序，称之为手机上的展厅，伴随参观的展前、展中和展后全过程，极大提升了访客和工作人员的用户体验。线上版的展厅包含了丰富的功能：展前，提供定场、邀约、报名以及内容预览、VR漫游等在线体验；展中，提供导航导览、智能讲解、手机播控等服务；展后，参观结束后会在小程序上生成相应的参观报告。我现在就是用一个小手机替代了传统的pad，对展厅实现全面操控。",
                "ai_explain": True,
                "keywords": ["大岛台", "小程序", "手机播控", "导览", "展厅"],
                "enabled": True,
                "sort": 3,
                "items": [
                    {"title": "思德大岛台正面1", "exhibit_type": "image", "exhibit_id": 931, "sort": 1, "enabled": True},
                    {"title": "大岛台正面", "exhibit_type": "image", "exhibit_id": 824, "sort": 2, "enabled": True},
                    {"title": "大岛台背面", "exhibit_type": "image", "exhibit_id": 823, "sort": 3, "enabled": True},
                    {"title": "思德AI", "exhibit_type": "image", "exhibit_id": 842, "sort": 4, "enabled": True},
                ],
            },
            {
                "title": "CAVE沉浸式空间",
                "poi_name": "CAVE",
                "terminal_name": "CAVE",
                "commentary": "欢迎进入CAVE沉浸式体验空间！这是展厅最独特的体验区域，采用360度环绕投影技术。CAVE空间可以展示城市规划、智慧园区、数字孪生等宏大叙事内容。在这个空间里，参观者可以完全沉浸在数字世界中，感受未来科技的震撼视觉体验。这也是我们展厅接待高端客户和重要领导参观时必须展示的核心内容。",
                "ai_explain": True,
                "keywords": ["CAVE", "沉浸", "360度", "虚拟现实", "数字孪生"],
                "enabled": True,
                "sort": 4,
                "items": [
                    {"title": "CAVE沉浸式展示", "exhibit_type": "video", "sort": 1, "enabled": True},
                ],
            },
        ]

        for sc_data in scripts_data:
            items = sc_data.pop("items", [])
            script = ExhibitScript(
                title=sc_data["title"],
                poi_name=sc_data["poi_name"],
                terminal_name=sc_data["terminal_name"],
                commentary=sc_data["commentary"],
                ai_explain=sc_data["ai_explain"],
                keywords=",".join(sc_data["keywords"]),
                enabled=sc_data["enabled"],
                sort=sc_data["sort"],
            )
            db.add(script)
            await db.flush()
            for item_data in items:
                item = ExhibitItem(
                    script_id=script.id,
                    title=item_data["title"],
                    exhibit_type=item_data.get("exhibit_type", "image"),
                    exhibit_id=item_data.get("exhibit_id"),
                    sort=item_data["sort"],
                    enabled=item_data["enabled"],
                )
                db.add(item)

        await db.commit()
        print(f"✅ 展项讲解词已写入：{len(scripts_data)}组")

        # ── 3. 接待套餐 ──────────────────────────────────────────────────────
        await db.execute(delete(ReceptionPreset))
        await db.commit()

        presets_data = [
            {
                "name": "标准接待",
                "description": "适用于企业客户、媒体参观等常规接待场景",
                "visitor_type": "企业客户",
                "language": "zh",
                "duration_min": 30,
                "route_name": "标准导览路线",
                "open_commands": ["0_all_light_on", "0_all_com_on"],
                "close_commands": ["0_all_light_off", "0_all_com_off"],
                "welcome_text": "欢迎来到青田城市共享客厅！我是AI导览官云猴，今天由我为您全程导览。",
                "goodbye_text": "感谢您参观青田城市共享客厅！希望今天的展览给您留下了美好的印象，欢迎下次再来！",
                "enabled": True,
                "sort": 1,
                "steps_json": [
                    {"type": "command", "name": "一键开馆", "command": "0_all_com_on", "wait_sec": 2},
                    {"type": "command", "name": "灯光全开", "command": "0_all_light_on", "wait_sec": 1},
                    {"type": "speak", "name": "欢迎词", "text": "欢迎来到青田城市共享客厅！", "speed": 1.0},
                    {"type": "navigate", "name": "前往入口", "poi": "入口三联屏", "wait_arrival": True},
                    {"type": "navigate", "name": "前往小岛台", "poi": "小岛台", "wait_arrival": True},
                    {"type": "navigate", "name": "前往大岛台", "poi": "大岛台", "wait_arrival": True},
                    {"type": "navigate", "name": "前往CAVE", "poi": "CAVE", "wait_arrival": True},
                    {"type": "speak", "name": "送客", "text": "感谢参观，再见！", "speed": 1.0},
                ],
            },
            {
                "name": "VIP接待",
                "description": "适用于政府领导、重要客人等高规格接待场景",
                "visitor_type": "政府领导",
                "language": "zh",
                "duration_min": 45,
                "route_name": "标准导览路线",
                "open_commands": ["0_all_light_on", "0_all_com_on", "0_all_ggj_on"],
                "close_commands": ["0_all_light_off", "0_all_com_off"],
                "welcome_text": "尊贵的领导，欢迎莅临青田城市共享客厅！我是专属导览官云猴，非常荣幸为您提供服务。",
                "goodbye_text": "感谢领导百忙之中莅临参观！如有合作意向，欢迎随时联系我们，期待下次再见！",
                "enabled": True,
                "sort": 2,
                "steps_json": [
                    {"type": "command", "name": "全馆开启", "command": "0_all_com_on", "wait_sec": 2},
                    {"type": "command", "name": "灯光全开", "command": "0_all_light_on", "wait_sec": 1},
                    {"type": "command", "name": "广告机开", "command": "0_all_ggj_on", "wait_sec": 1},
                    {"type": "speak", "name": "VIP欢迎词", "text": "尊贵的领导，欢迎莅临！", "speed": 0.95},
                    {"type": "navigate", "name": "前往入口", "poi": "入口三联屏", "wait_arrival": True},
                    {"type": "navigate", "name": "前往大岛台", "poi": "大岛台", "wait_arrival": True},
                    {"type": "navigate", "name": "前往小岛台", "poi": "小岛台", "wait_arrival": True},
                    {"type": "navigate", "name": "前往CAVE", "poi": "CAVE", "wait_arrival": True},
                    {"type": "speak", "name": "送客", "text": "感谢莅临，期待再次合作！", "speed": 0.95},
                    {"type": "command", "name": "关馆", "command": "0_all_com_off", "wait_sec": 1},
                ],
            },
            {
                "name": "快速参观",
                "description": "适用于内部演示、临时参观等简短场景（约15分钟）",
                "visitor_type": "内部参观",
                "language": "zh",
                "duration_min": 15,
                "route_name": "标准导览路线",
                "open_commands": ["0_all_light_on", "0_all_com_on"],
                "close_commands": [],
                "welcome_text": "欢迎！快速参观模式，我们重点看几个核心展项。",
                "goodbye_text": "参观完成，感谢！",
                "enabled": True,
                "sort": 3,
                "steps_json": [
                    {"type": "command", "name": "开馆", "command": "0_all_com_on", "wait_sec": 2},
                    {"type": "speak", "name": "欢迎词", "text": "欢迎快速参观！", "speed": 1.1},
                    {"type": "navigate", "name": "前往大岛台", "poi": "大岛台", "wait_arrival": True},
                    {"type": "navigate", "name": "前往CAVE", "poi": "CAVE", "wait_arrival": True},
                    {"type": "speak", "name": "结束", "text": "参观完成，感谢！", "speed": 1.0},
                ],
            },
        ]

        for preset_data in presets_data:
            import json, time
            steps = preset_data.pop("steps_json", [])
            preset = ReceptionPreset(
                name=preset_data["name"],
                description=preset_data["description"],
                visitor_type=preset_data["visitor_type"],
                language=preset_data["language"],
                duration_min=preset_data["duration_min"],
                route_name=preset_data["route_name"],
                open_commands=json.dumps(preset_data["open_commands"], ensure_ascii=False),
                close_commands=json.dumps(preset_data["close_commands"], ensure_ascii=False),
                welcome_text=preset_data["welcome_text"],
                goodbye_text=preset_data["goodbye_text"],
                steps_json=json.dumps(steps, ensure_ascii=False),
                enabled=preset_data["enabled"],
                sort=preset_data["sort"],
                created_at=int(time.time() * 1000),
            )
            db.add(preset)

        await db.commit()
        print(f"✅ 接待套餐已写入：{len(presets_data)}套")

        # ── 4. 通知群 ──────────────────────────────────────────────────────────
        existing = (await db.execute(select(NotifyGroup).limit(1))).scalar_one_or_none()
        if not existing:
            ng = NotifyGroup(
                name="展厅主群",
                chat_id="wrsFDcBgAA5VylKPpK_-FJvuogsRgFYg",
                notify_types="tour,reception,alarm,robot_offline,system",
                enabled=True,
            )
            db.add(ng)
            await db.commit()
            print("✅ 通知群已配置")

        print("\n🎉 全部预设数据写入完成！")
        print("  - 导览路线：1条（4站）")
        print("  - 展项讲解：4组（含真实讲解词）")
        print("  - 接待套餐：3套（标准/VIP/快速）")
        print("  - 通知群：已配置")


if __name__ == "__main__":
    asyncio.run(seed())
