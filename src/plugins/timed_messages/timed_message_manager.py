import asyncio
import datetime
from typing import List, Dict
from ..config.config import global_config
from ..chat.message_sender import message_manager
from ...common.logger import get_module_logger
from ..storage.storage import MessageStorage
from ..models.utils_model import LLM_request

logger = get_module_logger("timed_messages")

class TimedMessageManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.schedules = []
        self.storage = MessageStorage()
        self.model = LLM_request(
            model=global_config.llm_normal,
            temperature=0.8,
            max_tokens=512,
            request_type="timed_message"
        )
        self._load_schedules()

    def _load_schedules(self):
        """从配置加载定时消息计划"""
        if not global_config.timed_messages_enable:
            logger.info("定时消息功能未启用")
            return

        for schedule in global_config.timed_messages_schedules:
            self.schedules.append({
                'user_id': schedule.user_id,
                'message': schedule.message,
                'hour': schedule.hour,
                'minute': schedule.minute,
                'weekdays': schedule.weekdays,
                'dynamic': schedule.get('dynamic', False),  # 是否动态生成消息
                'context_size': schedule.get('context_size', 5)  # 使用多少条历史消息作为上下文
            })
        logger.success(f"已加载 {len(self.schedules)} 个定时消息计划")

    async def _generate_dynamic_message(self, user_id: str, template_message: str, context_size: int) -> str:
        """根据历史记录动态生成消息内容
        
        Args:
            user_id: 用户ID
            template_message: 模板消息或提示词
            context_size: 上下文消息数量
        
        Returns:
            str: 生成的消息内容
        """
        try:
            # 从chat_manager获取聊天流
            from ..chat.chat_stream import chat_manager
            
            # 构建用户信息
            from ..message import UserInfo
            user_info = UserInfo(
                user_id=user_id,
                user_nickname="用户",
                platform="qq",
            )
            
            # 获取或创建私聊聊天流
            chat_stream = await chat_manager.get_or_create_stream(
                platform="qq",
                user_info=user_info,
                group_info=None
            )
            
            # 获取历史消息
            history_messages = await self.storage.get_latest_messages(
                chat_stream=chat_stream,
                limit=context_size
            )
            
            if not history_messages:
                logger.warning(f"未找到用户 {user_id} 的历史消息记录，将使用模板消息")
                return template_message
            
            # 构建上下文
            context = ""
            for msg in history_messages:
                if msg.message_info.user_info.user_id == global_config.BOT_QQ:
                    sender = global_config.BOT_NICKNAME
                else:
                    sender = "用户"
                context += f"{sender}: {msg.processed_plain_text}\n"
            
            # 构建提示词
            prompt = f"""你是一个名为{global_config.BOT_NICKNAME}的AI助手，你需要根据历史对话记录，生成一条新的消息发送给用户。
            
以下是你和用户的历史对话记录：
{context}

使用以下模板或提示生成一条新消息：
{template_message}

注意：
1. 直接输出消息内容，不要包含类似"我会说："或"回复："这样的前缀
2. 让消息听起来自然，符合之前对话的上下文
3. 展现出对用户历史消息的了解
4. 保持你的人设特性：{global_config.personality_core}

请直接输出你要发送的消息："""

            # 调用LLM生成回复
            response, reasoning = await self.model.generate_response_async(prompt)
            
            if not response or len(response.strip()) == 0:
                logger.warning("生成的动态消息为空，使用模板消息")
                return template_message
                
            logger.info(f"成功生成动态消息: {response[:30]}...")
            return response
            
        except Exception as e:
            logger.error(f"生成动态消息失败: {e}")
            return template_message

    async def check_and_send_messages(self):
        """检查并发送定时消息"""
        while True:
            now = datetime.datetime.now()
            current_weekday = now.isoweekday()  # 1-7, 1是周一
            current_hour = now.hour
            current_minute = now.minute

            for schedule in self.schedules:
                if (current_weekday in schedule['weekdays'] and
                    current_hour == schedule['hour'] and
                    current_minute == schedule['minute']):
                    try:
                        message_content = schedule['message']
                        
                        # 如果启用动态消息，则生成动态内容
                        if schedule.get('dynamic', False):
                            message_content = await self._generate_dynamic_message(
                                user_id=schedule['user_id'],
                                template_message=schedule['message'],
                                context_size=schedule.get('context_size', 5)
                            )
                        
                        await message_manager.send_private_message(
                            user_id=schedule['user_id'],
                            message=message_content
                        )
                        logger.success(f"已发送定时消息给用户 {schedule['user_id']}")
                    except Exception as e:
                        logger.error(f"发送定时消息失败: {e}")

            # 每分钟检查一次
            await asyncio.sleep(60)

    async def start(self):
        """启动定时消息检查"""
        if not global_config.timed_messages_enable:
            return

        logger.info("启动定时消息检查")
        asyncio.create_task(self.check_and_send_messages()) 