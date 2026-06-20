#!/usr/bin/env python3
"""
测试对话记录功能
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """测试导入功能"""
    try:
        from mijiaAPI.conversations import (
            XiaoAiConversations,
            get_conversations_sync,
            get_conversations_json_sync,
            get_random_str,
            fmt_time,
        )
        print("✓ 导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False

def test_random_str():
    """测试随机字符串生成"""
    from mijiaAPI.conversations import get_random_str
    s = get_random_str(10)
    assert len(s) == 10
    assert s.isalnum()
    print("✓ 随机字符串生成成功")
    return True

def test_fmt_time():
    """测试时间格式化"""
    from mijiaAPI.conversations import fmt_time
    # 测试正常时间戳
    result = fmt_time(1624000000000)  # 2021-06-18 02:40:00 UTC
    assert result != ""
    assert "2021" in result
    print("✓ 时间格式化成功")
    return True

def test_main_import():
    """测试主模块导入"""
    try:
        from mijiaAPI import (
            mijiaAPI,
            XiaoAiConversations,
            get_conversations_sync,
            get_conversations_json_sync,
        )
        print("✓ 主模块导入成功")
        return True
    except ImportError as e:
        print(f"✗ 主模块导入失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试对话记录功能...\n")
    
    tests = [
        test_import,
        test_random_str,
        test_fmt_time,
        test_main_import,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ 测试 {test.__name__} 失败: {e}")
            results.append(False)
    
    print(f"\n测试完成: {sum(results)}/{len(results)} 通过")
    
    if all(results):
        print("所有测试通过!")
        sys.exit(0)
    else:
        print("部分测试失败!")
        sys.exit(1)
