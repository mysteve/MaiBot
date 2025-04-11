from typing import Union, List, Optional

from ...common.database import db
from ..chat.message import MessageSending, MessageRecv, Message
from ..chat.chat_stream import ChatStream
from src.common.logger import get_module_logger

logger = get_module_logger("message_storage")


class MessageStorage:
    async def store_message(self, message: Union[MessageSending, MessageRecv], chat_stream: ChatStream) -> None:
        """存储消息到数据库"""
        try:
            message_data = {
                "message_id": message.message_info.message_id,
                "time": message.message_info.time,
                "chat_id": chat_stream.stream_id,
                "chat_info": chat_stream.to_dict(),
                "user_info": message.message_info.user_info.to_dict(),
                "processed_plain_text": message.processed_plain_text,
                "detailed_plain_text": message.detailed_plain_text,
                "memorized_times": message.memorized_times,
            }
            db.messages.insert_one(message_data)
        except Exception:
            logger.exception("存储消息失败")

    async def get_latest_messages(self, chat_stream: ChatStream, limit: int = 10) -> List[Message]:
        """获取最近的消息历史
        
        Args:
            chat_stream: 聊天流
            limit: 消息数量限制
            
        Returns:
            List[Message]: 消息列表，按时间正序排列
        """
        try:
            messages = []
            # 查询数据库获取最近消息
            records = list(
                db.messages.find(
                    {"chat_id": chat_stream.stream_id}
                )
                .sort("time", -1)  # 倒序，最新的在前
                .limit(limit)
            )
            
            # 转换记录为消息对象
            for record in records:
                try:
                    from ..message import UserInfo
                    # 创建消息对象
                    user_info = UserInfo.from_dict(record.get("user_info", {}))
                    message = Message(
                        message_id=record.get("message_id", ""),
                        chat_stream=chat_stream,
                        time=record.get("time", 0),
                        user_info=user_info,
                        processed_plain_text=record.get("processed_plain_text", ""),
                        detailed_plain_text=record.get("detailed_plain_text", ""),
                    )
                    messages.append(message)
                except Exception as e:
                    logger.warning(f"转换消息记录失败: {e}")
                    continue
                    
            # 反转列表，使消息按时间正序排列（旧消息在前，新消息在后）
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            return []

    async def store_recalled_message(self, message_id: str, time: str, chat_stream: ChatStream) -> None:
        """存储撤回消息到数据库"""
        if "recalled_messages" not in db.list_collection_names():
            db.create_collection("recalled_messages")
        else:
            try:
                message_data = {
                    "message_id": message_id,
                    "time": time,
                    "stream_id": chat_stream.stream_id,
                }
                db.recalled_messages.insert_one(message_data)
            except Exception:
                logger.exception("存储撤回消息失败")

    async def remove_recalled_message(self, time: str) -> None:
        """删除撤回消息"""
        try:
            db.recalled_messages.delete_many({"time": {"$lt": time - 300}})
        except Exception:
            logger.exception("删除撤回消息失败")


# 如果需要其他存储相关的函数，可以在这里添加
