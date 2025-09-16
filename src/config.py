"""
配置管理模块
统一管理所有环境变量和配置项
"""
import os
import logging
from typing import List
from dotenv import load_dotenv
from src.token_manager import TokenManager

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""
    
    # API认证配置
    VALID_API_KEY: str = os.getenv("VALID_API_KEY", "")
    # 移除硬编码的K2THINK_TOKEN，使用token管理器
    K2THINK_API_URL: str = os.getenv("K2THINK_API_URL", "https://www.k2think.ai/api/chat/completions")
    
    # Token管理配置
    TOKEN_LIST: str = os.getenv("TOKEN_LIST", "")
    MAX_TOKEN_FAILURES: int = int(os.getenv("MAX_TOKEN_FAILURES", "3"))
    
    # Token管理器实例（延迟初始化）
    _token_manager: TokenManager = None
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))
    
    # 功能开关
    TOOL_SUPPORT: bool = os.getenv("TOOL_SUPPORT", "true").lower() == "true"
    DEBUG_LOGGING: bool = os.getenv("DEBUG_LOGGING", "false").lower() == "true"
    ENABLE_ACCESS_LOG: bool = os.getenv("ENABLE_ACCESS_LOG", "true").lower() == "true"
    
    # 性能配置
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "60"))
    MAX_KEEPALIVE_CONNECTIONS: int = int(os.getenv("MAX_KEEPALIVE_CONNECTIONS", "20"))
    MAX_CONNECTIONS: int = int(os.getenv("MAX_CONNECTIONS", "100"))
    STREAM_DELAY: float = float(os.getenv("STREAM_DELAY", "0.05"))
    STREAM_CHUNK_SIZE: int = int(os.getenv("STREAM_CHUNK_SIZE", "50"))
    MAX_STREAM_TIME: float = float(os.getenv("MAX_STREAM_TIME", "10.0"))
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # CORS配置
    CORS_ORIGINS: List[str] = (
        os.getenv("CORS_ORIGINS", "*").split(",") 
        if os.getenv("CORS_ORIGINS", "*") != "*" 
        else ["*"]
    )
    
    @classmethod
    def validate(cls) -> None:
        """验证必需的配置项"""
        if not cls.VALID_API_KEY:
            raise ValueError("错误：VALID_API_KEY 环境变量未设置。请在 .env 文件中提供一个安全的API密钥。")
        
        # 验证token列表是否存在
        if not cls.TOKEN_LIST.strip():
            raise ValueError("错误：TOKEN_LIST 环境变量未设置。请在环境变量中提供一个或多个用逗号分隔的token。")
        
        # 验证数值范围
        if cls.PORT < 1 or cls.PORT > 65535:
            raise ValueError(f"错误：PORT 值 {cls.PORT} 不在有效范围内 (1-65535)")
        
        if cls.REQUEST_TIMEOUT <= 0:
            raise ValueError(f"错误：REQUEST_TIMEOUT 必须大于0，当前值: {cls.REQUEST_TIMEOUT}")
        
        if cls.STREAM_DELAY < 0:
            raise ValueError(f"错误：STREAM_DELAY 不能为负数，当前值: {cls.STREAM_DELAY}")
    
    @classmethod
    def setup_logging(cls) -> None:
        """设置日志配置"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        
        log_level = level_map.get(cls.LOG_LEVEL, logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    @classmethod
    def get_token_manager(cls) -> TokenManager:
        """获取token管理器实例（单例模式）"""
        if cls._token_manager is None:
            cls._token_manager = TokenManager(
                token_list=cls.TOKEN_LIST,
                max_failures=cls.MAX_TOKEN_FAILURES
            )
        return cls._token_manager
    
    @classmethod
    def reload_tokens(cls) -> None:
        """重新加载token"""
        if cls._token_manager is not None:
            # 重新读取环境变量中的TOKEN_LIST
            new_token_list = os.getenv("TOKEN_LIST", "")
            cls._token_manager.reload_tokens(new_token_list)