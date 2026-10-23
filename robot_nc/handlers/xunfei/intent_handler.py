import threading

from config.config.dify_config import difyconfig
from handlers.dify.recognize_intention import chat_with_dify
import hashlib
import pymysql
from utils.pc2_requests import _send_qa_task, _send_led_color_task
from utils.tts_client import play_text_async
import json5
import random
import json
from utils.logger import logger
import requests
import paramiko
from sshtunnel import SSHTunnelForwarder
from config.config.settings import config
from strategies.vision.qwenv import process_base64_image
from strategies.action.execute_actions import ActionExecutor
from utils.logger import logger
"""
意图处理模块
"""


class IntentHandler:
    """意图处理类"""

    def __init__(self, aiui_node=None):
        self.detected_intent = None
        self.tts_text = ""
        self.cbm_semantic_processed = False  # 标记是否已处理视觉内容
        self.executor = ActionExecutor()
        # 闭嘴进入待唤醒状态
        self.aiui_node = aiui_node  # 使用传入的参数（如果没有则为 None）
        self.vision_dealing_words = [
            "我将从多个角度分析",  # 日常聊天标配，简单自然
            "我将从多维视角分析",  # 像说"我瞅瞅相关内容"，带着行动感
            "我将从不同层面分析",  # 随口的礼貌，特生活化
            "我将从多方面评估",  # 直白展现正在动脑筋
            "我将从多个维度剖析",  # 比"稍等下"正式点，又不刻意
        ]

    def set_aiui_node(self, aiui_node):
        """外部设置AIUINode实例的方法"""
        self.aiui_node = aiui_node

    def play_vision_phrase(self, type="thinking"):
        """播放语气助词"""
        phrase = random.choice(self.vision_dealing_words)
        logger.info(f"播放视觉语气助词: {phrase}")
        play_text_async(phrase, use_cache=True)

    '''
    def handle_intent_result(self, data: dict) -> None:
        logger.info(f"🔴 Intent入口: self={id(self)}")
        """
        处理意图识别结果

        Args:
            data: 意图数据
        """
        try:
            try:
                # 异步调用 _send_led_color_task
                led_thread = threading.Thread(
                    target=_send_led_color_task,
                    args=(self, "BREATH", "BLUE"),
                    daemon=True
                )
                led_thread.start()
            except Exception as e:
                logger.debug(f"[LED] LED控制失败，不影响意图处理: {e}")

            # logger.info('意图识别data', json.dumps(data, ensure_ascii=False, indent=2))
            text_value = data.get('content', {}).get(
                'result', {}).get('cbm_semantic', {}).get('text')
            if text_value:

                intent = json.loads(text_value)
                rc = intent.get('rc', -1)
                if rc == 0:
                    category = intent.get('category', "")
                    logger.info(f"技能结果: {category}")

                    # 排除默认技能
                    if category == "IFLYTEK.mapU":
                        logger.info(f"排除默认技能: {category}")
                        return
                    # 视觉意图
                    elif category.split('.')[-1] == "vision":
                        ###################
                        self.cbm_semantic_processed = True
                        # 使用dify识别视觉意图
                        logger.info(f"使用dify识别视觉意图")
                        logger.info(
                            f"difyconfig.get_vision_switch(): {difyconfig.get_vision_switch()}")
                        if difyconfig.get_vision_switch():
                            # 判断是否是视觉意图
                            iat_txt = intent.get('text', "")
                            res = chat_with_dify(
                                question=iat_txt, image_path='')
                            if res != '视觉意图':
                                return
                    elif category.split('.')[-1] == "wake_up":
                        semantics_list = intent.get("semantic", [])
                        if semantics_list:
                            semantics = semantics_list[0]
                            skill_purpose = semantics.get('intent')
                            if skill_purpose == "WAKEUP":
                                self.cbm_semantic_processed = False
                            elif skill_purpose == "RESET_WAKEUP":
                                self.cbm_semantic_processed = True
                                # ========== 新增：终止旧的TTS播放 ==========
                                logger.info("[RESET_WAKEUP] 触发唤醒重置，终止当前TTS播放")
                                # 导入stop_playback函数（确保导入在函数内，避免循环依赖）
                                from utils.tts_client import stop_playback
                                stop_playback()  # 强制终止所有正在播放的音频
                                # 清空音频缓冲区（可选，确保无残留音频）
                                from utils.tts_client import _audio_manager
                                _audio_manager.clear_buffer()
                                if self.aiui_node:
                                    play_text_async("好的 我不说了")
                                    self.aiui_node.reset_wakeup_agent() # 闭嘴 -> aiui进入待唤醒状态
                                else:
                                    logger.warning("AIUI Node未初始化，无法执行reset_wakeup_agent")
                        ###################

                    iat_txt = intent.get('text', "")
                    logger.info(f"意图识别文本: {iat_txt}")
                    answer = intent.get('answer', {}).get('text', "")
                    logger.info(f"意图识别答案: {answer}")
                    if answer:
                        self.cbm_semantic_processed = True
                        try:
                            # 异步调用 _send_qa_task
                            logger.info("发送QA接口===========> [QA]")
                            if category.split('.')[-1] != "vision":
                                qa_thread = threading.Thread(
                                    target=_send_qa_task,
                                    args=(self, {"result": answer}),
                                    daemon=True
                                )
                                qa_thread.start()
                        except Exception as e:
                            logger.error(f"QA接口请求失败: {e}")
                        try:
                            play_text_async(answer, use_cache=True)
                            logger.info(f"[意图] 答案播放请求已发送")
                        except Exception as e:
                            logger.info(f"[意图] 播放请求失败: {e}")
                            import traceback
                            traceback.print_exc()
                        if not self.cbm_semantic_processed:
                            self.cbm_semantic_processed = True
                            try:
                                play_text_async(answer, use_cache=True)
                                logger.info(f"[意图] 答案播放请求已发送")
                            except Exception as e:
                                logger.info(f"[意图] 播放请求失败: {e}")
                                import traceback
                                traceback.print_exc()

                    semantics_list = intent.get("semantic", [])
                    if semantics_list:
                        semantics = semantics_list[0]
                        skill_purpose = semantics.get('intent')


                        # 🔧 修复:对于动作类category,在执行前就标记为已处理,防止后续NLP重复播放
                        config_data = config.get_config()
                        xunfei_config = config_data.get('xunfei', {})
                        categories = xunfei_config.get('category', [])
                        if category in categories and not self.cbm_semantic_processed:
                            self.cbm_semantic_processed = True
                            logger.info(f"✅ 动作类意图 {category} 已标记为已处理,阻止后续NLP播放")

                        # 处理具体意图
                        self._handle_detected_intent(
                            category, iat_txt, skill_purpose)
                    else:
                        logger.warning("未获取到语义信息")

                        # 🔧 修复:对于动作类category,在执行前就标记为已处理
                        config_data = config.get_config()
                        xunfei_config = config_data.get('xunfei', {})
                        categories = xunfei_config.get('category', [])
                        if category in categories and not self.cbm_semantic_processed:
                            self.cbm_semantic_processed = True
                            logger.info(f"✅ 动作类意图 {category} 已标记为已处理,阻止后续NLP播放")

                        # 处理具体意图，但不传递skill_purpose
                        self._handle_detected_intent(
                            category, iat_txt, None)
            else:
                logger.warning("未获取到意图文本")

        except Exception as e:
            logger.error(f"意图处理异常: {e}")
    '''
    def handle_intent_result(self, data: dict) -> None:
        """
        处理意图识别结果

        Args:
            data: 意图数据
        """
        try:
            try:
                # 异步调用 _send_led_color_task
                led_thread = threading.Thread(
                    target=_send_led_color_task,
                    args=(self, "BREATH", "BLUE"),
                    daemon=True
                )
                led_thread.start()
            except Exception as e:
                logger.debug(f"[LED] LED控制失败，不影响意图处理: {e}")

            # logger.info('意图识别data', json.dumps(data, ensure_ascii=False, indent=2))
            text_value = data.get('content', {}).get(
                'result', {}).get('cbm_semantic', {}).get('text')
            if text_value:

                intent = json.loads(text_value)
                rc = intent.get('rc', -1)
                if rc == 0:
                    category = intent.get('category', "")
                    logger.info(f"技能结果: {category}")
                    
                    # 排除默认技能
                    if category == "IFLYTEK.mapU":
                        logger.info(f"排除默认技能: {category}")
                        self.cbm_semantic_processed = False  # ← 第1处：重置
                        return
                    # 演播PPT技能 ppt_broadcast
                    elif category.split('.')[-1] == "ppt_broadcast":
                        self.cbm_semantic_processed = True
                        logger.info(f"开始演播PPT: {category}")
                    # 视频演播技能 video_broadcast
                    elif category.split('.')[-1] == "video_broadcast":
                        self.cbm_semantic_processed = True
                        logger.info(f"开始演播视频video: {category}")
                    # 场景切换技能 scene_switch
                    elif category.split('.')[-1] == "scene_switch":
                        self.cbm_semantic_processed = True
                        logger.info(f"开始场景切换: {category}")
                    # 视觉意图
                    elif category.split('.')[-1] == "vision":
                        ###################
                        self.cbm_semantic_processed = True
                        # 使用dify识别视觉意图
                        logger.info(f"使用dify识别视觉意图")
                        logger.info(
                            f"difyconfig.get_vision_switch(): {difyconfig.get_vision_switch()}")
                        if difyconfig.get_vision_switch():
                            # 判断是否是视觉意图
                            iat_txt = intent.get('text', "")
                            res = chat_with_dify(
                                question=iat_txt, image_path='')
                            if res != '视觉意图':
                                return
                    elif category.split('.')[-1] == "wake_up":
                        semantics_list = intent.get("semantic", [])
                        if semantics_list:
                            semantics = semantics_list[0]
                            skill_purpose = semantics.get('intent')
                            if skill_purpose == "WAKEUP":
                                self.cbm_semantic_processed = False
                            elif skill_purpose == "RESET_WAKEUP":
                                self.cbm_semantic_processed = True
                        ###################

                    iat_txt = intent.get('text', "")
                    logger.info(f"意图识别文本: {iat_txt}")
                    answer = intent.get('answer', {}).get('text', "")
                    logger.info(f"意图识别答案: {answer}")
                    if answer:
                        self.cbm_semantic_processed = True
                        try:
                            # 异步调用 _send_qa_task
                            logger.info("发送QA接口===========> [QA]")
                            if category.split('.')[-1] != "vision":
                                qa_thread = threading.Thread(
                                    target=_send_qa_task,
                                    args=(self, {"result": answer}),
                                    daemon=True
                                )
                                qa_thread.start()
                        except Exception as e:
                            logger.error(f"QA接口请求失败: {e}")
                        # if not self.cbm_semantic_processed:
                        #     self.cbm_semantic_processed = True
                        #     try:
                        #         play_text_async(answer, use_cache=True)
                        #         logger.info(f"[意图] 答案播放请求已发送")
                        #     except Exception as e:
                        #         logger.info(f"[意图] 播放请求失败: {e}")
                        #         import traceback
                        #         traceback.print_exc()
                        try:
                            play_text_async(answer, use_cache=True)
                            logger.info(f"[意图] 答案播放请求已发送")
                        except Exception as e:
                            logger.info(f"[意图] 播放请求失败: {e}")
                            import traceback
                            traceback.print_exc()

                    semantics_list = intent.get("semantic", [])
                    if semantics_list:
                        semantics = semantics_list[0]
                        skill_purpose = semantics.get('intent')
                        
                        # 🔧 修复: 仅在确认为动作类意图时加锁
                        config_data = config.get_config()
                        xunfei_config = config_data.get('xunfei', {})
                        categories = xunfei_config.get('category', [])
                        is_action_category = (category in categories) or category.endswith('.ACTIONS')
                        
                        if is_action_category:
                            self.cbm_semantic_processed = True
                            logger.info(f"🔒 [Intent] 动作类意图 {category} 已加锁, 阻止后续NLP")
                        
                        # 处理具体意图
                        self._handle_detected_intent(
                            category, iat_txt, skill_purpose)
                    else:
                        logger.warning("未获取到语义信息")
                        
                        # 🔧 修复:对于动作类category,无论是否有answer,都标记为已处理
                        config_data = config.get_config()
                        xunfei_config = config_data.get('xunfei', {})
                        categories = xunfei_config.get('category', [])
                        is_action_category = (category in categories) or category.endswith('.ACTIONS')
                        
                        if is_action_category and not self.cbm_semantic_processed:
                            self.cbm_semantic_processed = True
                            logger.info(f"✅ 动作类意图 {category} 已标记为已处理,阻止后续NLP播放")
                        
                        # 处理具体意图，但不传递skill_purpose
                        self._handle_detected_intent(
                            category, iat_txt, None)
                            # ← 第2处：未命中技能，重置标记
                        self.cbm_semantic_processed = False
                        logger.info(f"🔴 未命中技能(rc={rc})，重置标记，允许 NLP 处理")
                        return  # 直接返回，不执行后续
            else:
                logger.warning("未获取到意图文本")
                self.cbm_semantic_processed = False  # ← 第3处：重置

        except Exception as e:
            logger.error(f"意图处理异常: {e}")
            self.cbm_semantic_processed = False  # ← 第4处：重置

    def _handle_detected_intent(self, intent: str, iat_txt: str, purpose) -> None:
        """
        处理检测到的意图
        Args:
            intent: 意图名称
            iat_txt: 原IAT内容
        """
        # 读取yaml配置文件
        config_data = config.get_config()
        xunfei_config = config_data.get('xunfei', {})
        categories = xunfei_config.get('category', [])

        if intent in categories:
            self.executor.execute_actions(intent, purpose)

        # 视觉调用
        elif intent.split('.')[-1] == "vision":
            # 在识别开始时播放语气助词
            logger.info(f"开始播放语气词")
            self.play_vision_phrase(type="vision")
            logger.info(f"检测到 [{intent}] 意图, 执行视觉相关")
            # 标记已处理视觉内容，避免后续NLP重复播放
            self.cbm_semantic_processed = True
            answer_text = '摄像头服务异常'
            try:
                camera_url = config._config_data.get(
                    'camera_url', 'http://127.0.0.1:34550/camera_base64'
                )
                headers = {"Content-Type": "application/json"}
                data = {}  # matches the -d '{}' from curl

                response = requests.get(camera_url, headers=headers, json=data)

                resp_data = json5.loads(response.text)
                # 处理响应
                if resp_data.get('code') == 200:
                    base64_pic = resp_data.get('data').get('base64_content')
                    answer_text = process_base64_image(
                        base64_pic, question=iat_txt)
                    logger.info(f"视觉调用结果: {answer_text}")
                    play_text_async(answer_text)
                else:
                    logger.error(f"摄像头服务异常: {str(resp_data.get('code'))}")
                try:
                    # 异步调用 _send_qa_task
                    logger.info("发送QA接口===========> [QA]")
                    qa_thread = threading.Thread(
                        target=_send_qa_task,
                        args=(self, {"result": answer_text}),
                        daemon=True
                    )
                    qa_thread.start()
                except Exception as e:
                    logger.error(f"QA接口请求失败: {e}")
            except Exception as e:
                logger.error(f"摄像头服务异常: {str(e)}")
        elif intent.split('.')[-1] == "BASE_STATION":
            try:
                match purpose:
                    case "Base_Stations":
                        sum1, sum2 = self.sql_query()
                        play_text_async(f"实时客流为{sum1}人次，累计客流为{sum2}人次")
            except requests.exceptions.RequestException as e:
                logger.error(f"区域基站客流查询API调用失败: {e}")
        elif intent.split('.')[-1] == "Game_Guess":
            try:
                match purpose:
                    case "Ready":
                        pass
                    case "Start_Game":
                        try:
                            response = requests.post(url="http://192.168.123.164:9002/game",
                                                     json={"target": "game", "cmd": "start_game", "id": "cq"})
                            result = response.json()
                            if result and result["code"] == 0:
                                play_text_async("游戏开始")
                            else:
                                play_text_async("游戏开始失败, 请稍后重试")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"猜拳游戏异常(开始): {e}")
                    case "Stop_Game":
                        try:
                            response = requests.post(url="http://192.168.123.164:9002/game",
                                                     json={"target": "game", "cmd": "stop_game", "id": "cq"})
                            result = response.json()
                            if result and result["code"] == 0:
                                play_text_async("游戏结束")
                            else:
                                play_text_async("游戏结束失败, 请稍后重试")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"猜拳游戏异常(结束): {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"猜拳游戏执行异常: {e}")
        elif intent.split('.')[-1] == "switch_model":
            if difyconfig.get_models_switch():
                # 切换模型
                model_dify_type = difyconfig.get_model_dify_type(purpose)
                if model_dify_type:
                    difyconfig.set_current_model(model_dify_type)
        else:
            logger.info(f"检测到未知意图: {intent}")

    def get_detected_intent(self) -> str:
        """获取检测到的意图"""
        return self.detected_intent or ""

    def get_tts_text(self) -> str:
        """获取TTS文本"""
        return self.tts_text or ""

    def is_cbm_semantic_processed(self) -> bool:
        """检查是否已处理cbm_semantic"""
        return self.cbm_semantic_processed

    def reset_cbm_semantic_processed(self) -> None:
        """重置cbm_semantic处理标记"""
        self.cbm_semantic_processed = False

    def generate_md5(self, userId: str, key: str, full_identifier: str) -> str:
        """MD5加密"""
        combined = f"{userId}{key}{full_identifier}"
        md5_hash = hashlib.md5(combined.encode('utf-8')).hexdigest()
        return md5_hash.upper()

    def sql_query(self):
        try:
            with SSHTunnelForwarder(
                    (config._config_data.get('ssh_host'),
                     config._config_data.get('ssh_port')),
                    ssh_username=config._config_data.get('ssh_user'),
                    ssh_password=config._config_data.get('ssh_pass'),
                    remote_bind_address=(
                        config._config_data.get('db_host'),
                        config._config_data.get('db_port')
                    )
            ) as tunnel:
                logger.info(
                    f"SSH 隧道已建立，开始更新数据库: {config._config_data.get('table')}")
                conn = pymysql.connect(
                    host=config._config_data.get('db_host'),
                    port=tunnel.local_bind_port,
                    user=config._config_data.get('db_user'),
                    password=config._config_data.get('db_pass'),
                    db=config._config_data.get('db_name'),
                    autocommit=True
                )
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1;")
                        result = cur.fetchone()
                        if result and result[0] == 1:
                            logger.info("数据库连接成功！")
                        else:
                            logger.error("数据库连接失败！")
                    select_sql = f"""
                        SELECT flow_sum1, flow_sum2 
                        FROM {config._config_data.get('table')} 
                        WHERE identity = 'Current'
                    """
                    with conn.cursor() as cur:
                        cur.execute(select_sql)
                        row = cur.fetchone()
                        if row:
                            # flow_sum1, flow_sum2 = row
                            return row
                        else:
                            logger.warning("未查询到数据！")
                finally:
                    conn.close()
                    logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"更新数据库失败: {e}")

