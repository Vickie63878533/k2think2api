"""
Token管理模块
负责管理K2Think的token池，实现轮询、负载均衡和失效标记
"""
import os
import json
import logging
import threading
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from src.utils import safe_str

logger = logging.getLogger(__name__)

class TokenManager:
    """Token管理器 - 支持轮询、负载均衡和失效标记"""
    
    def __init__(self, token_list: str = "", max_failures: int = 3):
        """
        初始化token管理器

        Args:
            token_list: 逗号分隔的token字符串
            max_failures: 最大失败次数，超过后标记为失效
        """
        self.token_list = token_list
        self.max_failures = max_failures
        self.tokens: List[Dict] = []
        self.current_index = 0
        self.lock = threading.Lock()

        # 加载tokens
        self.load_tokens()

        if not self.tokens:
            raise ValueError("未找到有效的token，请检查TOKEN_LIST环境变量")
    
    def load_tokens(self) -> None:
        """从环境变量加载token列表"""
        try:
            if not self.token_list.strip():
                raise ValueError("Token列表为空")

            # 分割逗号分隔的token
            token_strings = [token.strip() for token in self.token_list.split(',') if token.strip()]

            self.tokens = []
            for i, token in enumerate(token_strings):
                self.tokens.append({
                    'token': token,
                    'failures': 0,
                    'is_active': True,
                    'last_used': None,
                    'last_failure': None,
                    'index': i
                })

            logger.info(f"成功加载 {len(self.tokens)} 个token")

        except Exception as e:
            logger.error(f"解析token列表失败: {safe_str(e)}")
            raise
    
    def get_next_token(self) -> Optional[str]:
        """
        获取下一个可用的token（轮询算法）
        
        Returns:
            可用的token字符串，如果没有可用token则返回None
        """
        with self.lock:
            active_tokens = [t for t in self.tokens if t['is_active']]
            
            if not active_tokens:
                logger.warning("没有可用的token")
                return None
            
            # 轮询算法：从当前索引开始寻找下一个可用token
            attempts = 0
            while attempts < len(self.tokens):
                token_info = self.tokens[self.current_index]
                
                if token_info['is_active']:
                    # 更新使用时间
                    token_info['last_used'] = datetime.now()
                    token = token_info['token']
                    
                    # 移动到下一个索引
                    self.current_index = (self.current_index + 1) % len(self.tokens)
                    
                    logger.debug(f"分配token (索引: {token_info['index']}, 失败次数: {token_info['failures']})")
                    return token
                
                # 移动到下一个token
                self.current_index = (self.current_index + 1) % len(self.tokens)
                attempts += 1
            
            logger.warning("所有token都已失效")
            return None
    
    def mark_token_failure(self, token: str, error_message: str = "") -> bool:
        """
        标记token使用失败
        
        Args:
            token: 失败的token
            error_message: 错误信息
            
        Returns:
            如果token被标记为失效返回True，否则返回False
        """
        with self.lock:
            for token_info in self.tokens:
                if token_info['token'] == token:
                    token_info['failures'] += 1
                    token_info['last_failure'] = datetime.now()
                    
                    logger.warning(f"Token失败 (索引: {token_info['index']}, "
                                 f"失败次数: {token_info['failures']}/{self.max_failures}): {safe_str(error_message)}")
                    
                    # 检查是否达到最大失败次数
                    if token_info['failures'] >= self.max_failures:
                        token_info['is_active'] = False
                        logger.error(f"Token已失效 (索引: {token_info['index']}, "
                                   f"失败次数: {token_info['failures']})")
                        return True
                    
                    return False
            
            logger.warning("未找到匹配的token进行失败标记")
            return False
    
    def mark_token_success(self, token: str) -> None:
        """
        标记token使用成功（重置失败计数）
        
        Args:
            token: 成功的token
        """
        with self.lock:
            for token_info in self.tokens:
                if token_info['token'] == token:
                    if token_info['failures'] > 0:
                        logger.info(f"Token恢复 (索引: {token_info['index']}, "
                                  f"重置失败次数: {token_info['failures']} -> 0)")
                        token_info['failures'] = 0
                    return
    
    def get_token_stats(self) -> Dict:
        """
        获取token池统计信息
        
        Returns:
            包含统计信息的字典
        """
        with self.lock:
            total = len(self.tokens)
            active = sum(1 for t in self.tokens if t['is_active'])
            inactive = total - active
            
            failure_distribution = {}
            for token_info in self.tokens:
                failures = token_info['failures']
                failure_distribution[failures] = failure_distribution.get(failures, 0) + 1
            
            return {
                'total_tokens': total,
                'active_tokens': active,
                'inactive_tokens': inactive,
                'current_index': self.current_index,
                'failure_distribution': failure_distribution,
                'max_failures': self.max_failures
            }
    
    def reset_token(self, token_index: int) -> bool:
        """
        重置指定索引的token（清除失败计数，重新激活）
        
        Args:
            token_index: token索引
            
        Returns:
            重置成功返回True，否则返回False
        """
        with self.lock:
            if 0 <= token_index < len(self.tokens):
                token_info = self.tokens[token_index]
                old_failures = token_info['failures']
                old_active = token_info['is_active']
                
                token_info['failures'] = 0
                token_info['is_active'] = True
                token_info['last_failure'] = None
                
                logger.info(f"Token重置 (索引: {token_index}, "
                           f"失败次数: {old_failures} -> 0, "
                           f"状态: {old_active} -> True)")
                return True
            
            logger.warning(f"无效的token索引: {token_index}")
            return False
    
    def reset_all_tokens(self) -> None:
        """重置所有token（清除所有失败计数，重新激活所有token）"""
        with self.lock:
            reset_count = 0
            for token_info in self.tokens:
                if token_info['failures'] > 0 or not token_info['is_active']:
                    token_info['failures'] = 0
                    token_info['is_active'] = True
                    token_info['last_failure'] = None
                    reset_count += 1
            
            logger.info(f"重置了 {reset_count} 个token，当前活跃token数: {len(self.tokens)}")
    
    def reload_tokens(self, new_token_list: str = None) -> None:
        """重新加载token列表"""
        logger.info("重新加载token列表...")
        old_count = len(self.tokens)

        # 如果提供了新的token列表，则更新
        if new_token_list is not None:
            self.token_list = new_token_list

        self.load_tokens()
        new_count = len(self.tokens)

        logger.info(f"Token重新加载完成: {old_count} -> {new_count}")
    
    def get_token_by_index(self, index: int) -> Optional[Dict]:
        """根据索引获取token信息"""
        with self.lock:
            if 0 <= index < len(self.tokens):
                return self.tokens[index].copy()
            return None
