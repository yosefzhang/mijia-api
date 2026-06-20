#!/usr/bin/env python3
"""
小爱音箱对话记录获取模块

提供获取小爱音箱对话记录的功能，包括：
- 获取micoapi token
- 获取设备列表
- 获取对话记录

依赖：
- miservice: 用于获取micoapi token和设备列表
- aiohttp: 用于异步HTTP请求
"""

import asyncio
import json
import sys
import time
from typing import Optional, List, Dict, Any

try:
    from aiohttp import ClientSession
except ImportError:
    ClientSession = None

try:
    from miservice import MiAccount, MiNAService
except ImportError:
    MiAccount = None
    MiNAService = None


def require_miservice():
    """检查miservice依赖是否已安装"""
    if MiAccount is None or MiNAService is None:
        raise ImportError(
            "缺少运行依赖 miservice。请先安装: pip install miservice"
        )
    return MiAccount, MiNAService


def get_random_str(length: int) -> str:
    """生成随机字符串"""
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def fmt_time(ts_ms: int) -> str:
    """格式化时间戳（毫秒）为可读时间字符串"""
    if not ts_ms:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_ms / 1000))


async def build_micoapi_account(session: ClientSession, auth: dict):
    """
    用 auth.json 中的 passToken 获取 micoapi serviceToken
    
    Args:
        session: aiohttp ClientSession
        auth: 认证数据字典，包含 deviceId, userId, passToken
        
    Returns:
        MiAccount 对象
        
    Raises:
        RuntimeError: 当登录失败时
    """
    MiAccount, _ = require_miservice()
    
    token = {
        "deviceId": auth["deviceId"],
        "userId": str(auth["userId"]),
        "passToken": auth["passToken"],
    }
    
    account = MiAccount(session, None, None, None)
    account.token = token
    
    ok = await account.login("micoapi")
    if not ok:
        raise RuntimeError(
            "micoapi 登录失败，passToken 可能已过期。\n"
            "请重新登录获取新的认证数据。"
        )
    return account


async def get_devices(account) -> List[Dict[str, Any]]:
    """
    获取 MINA 设备列表
    
    Args:
        account: MiAccount 对象
        
    Returns:
        设备列表
    """
    _, MiNAService = require_miservice()
    mina = MiNAService(account)
    devices = await mina.device_list()
    return devices or []


async def get_conversations(
    session: ClientSession,
    account,
    mina_device_id: str,
    hardware: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    向 userprofile.mina.mi.com 请求对话记录
    
    Args:
        session: aiohttp ClientSession
        account: MiAccount 对象
        mina_device_id: MINA 设备ID（非 miotDID）
        hardware: 设备硬件型号
        limit: 返回记录条数
        
    Returns:
        对话记录字典
    """
    timestamp_ms = int(time.time() * 1000)
    request_id = "app_ios_" + get_random_str(30)
    
    url = (
        "https://userprofile.mina.mi.com/device_profile/v2/conversation"
        f"?source=dialogu"
        f"&hardware={hardware}"
        f"&timestamp={timestamp_ms}"
        f"&limit={limit}"
        f"&requestId={request_id}"
    )
    
    headers = {
        "User-Agent": (
            "MiHome/6.0.103 (com.xiaomi.mihome; build:6.0.103.1; "
            "iOS 14.4.0) Alamofire/6.0.103 MICO/iOSApp/appStore/6.0.103"
        )
    }
    
    cookies = {
        "userId": str(account.token["userId"]),
        "serviceToken": account.token["micoapi"][1],
        "deviceId": mina_device_id,
    }
    
    async with session.get(url, cookies=cookies, headers=headers) as r:
        return await r.json(content_type=None)


def parse_conversations(raw_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    解析对话记录响应
    
    Args:
        raw_response: API 原始响应
        
    Returns:
        解析后的对话记录列表
    """
    data_payload = raw_response.get("data") if isinstance(raw_response, dict) else None
    
    if isinstance(data_payload, str):
        try:
            data_payload = json.loads(data_payload)
        except json.JSONDecodeError:
            data_payload = {}
    
    records = data_payload.get("records", []) if isinstance(data_payload, dict) else []
    
    conversations = []
    for rec in records:
        query = rec.get("query") or rec.get("request", "")
        answers = rec.get("answers", [])
        answer_text = ""
        
        if isinstance(answers, list) and answers:
            a = answers[0]
            answer_text = (
                (a.get("tts") or {}).get("text")
                or (a.get("llm") or {}).get("text")
                or a.get("text")
                or ""
            )
        
        ts_ms = rec.get("time", 0)
        conversations.append({
            "timestamp_ms": ts_ms,
            "time": fmt_time(ts_ms),
            "query": query,
            "answer": answer_text,
        })
    
    return conversations


class XiaoAiConversations:
    """
    小爱音箱对话记录获取类
    
    提供获取小爱音箱对话记录的功能。
    
    使用示例:
        ```python
        from mijiaAPI.conversations import XiaoAiConversations
        
        # 使用认证数据初始化
        conversations = XiaoAiConversations(auth_data)
        
        # 获取对话记录
        records = await conversations.get_conversations(speaker_name="小爱音箱", limit=10)
        ```
    """
    
    def __init__(self, auth_data: dict):
        """
        初始化对话记录获取类
        
        Args:
            auth_data: 认证数据字典，包含 deviceId, userId, passToken
        """
        self.auth_data = auth_data
        self._account = None
        self._devices = None
    
    async def _ensure_account(self, session: ClientSession):
        """确保已获取micoapi account"""
        if self._account is None:
            self._account = await build_micoapi_account(session, self.auth_data)
        return self._account
    
    async def get_devices_list(self) -> List[Dict[str, Any]]:
        """
        获取所有可用的小爱音箱设备列表
        
        Returns:
            设备列表，每个设备包含 deviceID, miotDID, name, hardware 等字段
        """
        if self._devices is not None:
            return self._devices
        
        async with ClientSession() as session:
            account = await self._ensure_account(session)
            self._devices = await get_devices(account)
            return self._devices
    
    async def find_device(self, speaker_name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称查找小爱音箱设备
        
        Args:
            speaker_name: 音箱名称
            
        Returns:
            找到的设备信息，未找到返回 None
        """
        devices = await self.get_devices_list()
        
        # 精确匹配
        for dev in devices:
            if dev.get("name") == speaker_name:
                return dev
        
        # 模糊匹配
        for dev in devices:
            if speaker_name and speaker_name in dev.get("name", ""):
                return dev
        
        return None
    
    async def get_conversations(
        self,
        speaker_name: Optional[str] = None,
        device_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取小爱音箱对话记录
        
        Args:
            speaker_name: 音箱名称（与 device_id 二选一）
            device_id: 设备ID（与 speaker_name 二选一）
            limit: 返回记录条数，默认 10
            
        Returns:
            对话记录列表
            
        Raises:
            ValueError: 当参数无效时
            RuntimeError: 当设备未找到时
        """
        if not speaker_name and not device_id:
            raise ValueError("必须提供 speaker_name 或 device_id 参数")
        
        async with ClientSession() as session:
            account = await self._ensure_account(session)
            
            # 查找目标设备
            target = None
            if device_id:
                devices = await self.get_devices_list()
                for dev in devices:
                    if dev.get("deviceID") == device_id or dev.get("miotDID") == device_id:
                        target = dev
                        break
            elif speaker_name:
                target = await self.find_device(speaker_name)
            
            if target is None:
                available = await self.get_devices_list()
                available_names = [d.get("name") for d in available]
                raise RuntimeError(
                    f"未找到设备: {speaker_name or device_id}\n"
                    f"可用设备: {available_names}"
                )
            
            hardware = target.get("hardware", "")
            mina_device_id = target.get("deviceID", "")
            
            # 获取对话记录
            raw = await get_conversations(session, account, mina_device_id, hardware, limit)
            
            # 解析对话记录
            return parse_conversations(raw)
    
    async def get_conversations_json(
        self,
        speaker_name: Optional[str] = None,
        device_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        获取小爱音箱对话记录（JSON格式）
        
        Args:
            speaker_name: 音箱名称（与 device_id 二选一）
            device_id: 设备ID（与 speaker_name 二选一）
            limit: 返回记录条数，默认 10
            
        Returns:
            包含状态和对话记录的字典
        """
        try:
            conversations = await self.get_conversations(speaker_name, device_id, limit)
            return {
                "status": "ok",
                "conversations": conversations,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "conversations": [],
            }


def get_conversations_sync(
    auth_data: dict,
    speaker_name: Optional[str] = None,
    device_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    同步方式获取小爱音箱对话记录
    
    Args:
        auth_data: 认证数据字典
        speaker_name: 音箱名称（与 device_id 二选一）
        device_id: 设备ID（与 speaker_name 二选一）
        limit: 返回记录条数，默认 10
        
    Returns:
        对话记录列表
    """
    async def _get():
        conv = XiaoAiConversations(auth_data)
        return await conv.get_conversations(speaker_name, device_id, limit)
    
    return asyncio.run(_get())


def get_conversations_json_sync(
    auth_data: dict,
    speaker_name: Optional[str] = None,
    device_id: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    同步方式获取小爱音箱对话记录（JSON格式）
    
    Args:
        auth_data: 认证数据字典
        speaker_name: 音箱名称（与 device_id 二选一）
        device_id: 设备ID（与 speaker_name 二选一）
        limit: 返回记录条数，默认 10
        
    Returns:
        包含状态和对话记录的字典
    """
    async def _get():
        conv = XiaoAiConversations(auth_data)
        return await conv.get_conversations_json(speaker_name, device_id, limit)
    
    return asyncio.run(_get())
