# coding=utf-8
"""
模块基类定义

定义所有业务模块的统一接口，实现鲁棒性设计：
- 模块隔离执行
- 超时控制
- 错误恢复
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class ModuleStatus(Enum):
    """模块执行状态"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 运行中
    SUCCESS = "success"     # 成功
    FAILED = "failed"       # 失败
    TIMEOUT = "timeout"     # 超时
    DISABLED = "disabled"   # 已禁用


@dataclass
class ProcessResult:
    """模块执行结果"""
    success: bool                           # 是否成功
    module: str                             # 模块名称
    status: ModuleStatus                    # 执行状态
    message: str                            # 执行消息
    stats: Dict[str, Any] = field(default_factory=dict)  # 统计信息
    error: Optional[str] = None             # 错误信息
    started_at: Optional[datetime] = None   # 开始时间
    finished_at: Optional[datetime] = None  # 结束时间
    
    @property
    def duration_seconds(self) -> float:
        """执行耗时（秒）"""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "module": self.module,
            "status": self.status.value,
            "message": self.message,
            "stats": self.stats,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }


class ModuleProcessor(ABC):
    """
    业务模块基类
    
    所有业务模块（podcast, investment, community, wechat）必须实现此接口。
    基类提供统一的执行框架和错误处理机制。
    """
    
    @classmethod
    @abstractmethod
    def from_config(cls, system_config: Dict, module_config: Dict) -> "ModuleProcessor":
        """
        从配置创建实例
        
        Args:
            system_config: 系统配置（来自 config/system.yaml）
            module_config: 模块业务配置
        
        Returns:
            模块实例
        """
        pass
    
    @abstractmethod
    def run(self) -> ProcessResult:
        """
        执行模块主流程
        
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        检查模块依赖的服务是否可用（如 AI 服务、数据库等）
        
        Returns:
            健康检查结果，格式：
            {
                "status": "ok" | "warning" | "error",
                "checks": {
                    "check_name": {"status": "ok", "message": "..."},
                    ...
                }
            }
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        获取模块当前状态
        
        Returns:
            模块状态，格式：
            {
                "enabled": bool,
                "last_run": datetime | None,
                "last_status": ModuleStatus,
                "next_run": datetime | None,
                "stats": {...}
            }
        """
        pass
    
    @property
    @abstractmethod
    def module_name(self) -> str:
        """模块名称标识（小写，如 'podcast', 'investment'）"""
        pass
    
    @property
    def display_name(self) -> str:
        """模块显示名称（可覆盖）"""
        return self.module_name.title()
    
    def safe_run(self) -> ProcessResult:
        """
        安全执行模块（带错误捕获）
        
        不要直接调用 run()，而是调用此方法以确保错误被正确捕获。
        
        Returns:
            执行结果（即使出错也会返回结果对象）
        """
        started_at = datetime.now()
        
        try:
            result = self.run()
            result.started_at = started_at
            result.finished_at = datetime.now()
            return result
            
        except Exception as e:
            import traceback
            return ProcessResult(
                success=False,
                module=self.module_name,
                status=ModuleStatus.FAILED,
                message=f"模块执行异常: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )


@dataclass
class ModuleInfo:
    """模块信息（用于注册和发现）"""
    name: str                               # 模块名称
    display_name: str                       # 显示名称
    description: str                        # 模块描述
    processor_class: type                   # Processor 类
    config_section: str                     # 配置文件中的配置段名称
    db_path_key: str                        # 数据库路径配置键


class ModuleRegistry:
    """
    模块注册表
    
    管理所有业务模块的注册和发现
    """
    
    _modules: Dict[str, ModuleInfo] = {}
    
    @classmethod
    def register(cls, info: ModuleInfo) -> None:
        """注册模块"""
        cls._modules[info.name] = info
    
    @classmethod
    def get(cls, name: str) -> Optional[ModuleInfo]:
        """获取模块信息"""
        return cls._modules.get(name)
    
    @classmethod
    def get_all(cls) -> List[ModuleInfo]:
        """获取所有已注册模块"""
        return list(cls._modules.values())
    
    @classmethod
    def get_names(cls) -> List[str]:
        """获取所有模块名称"""
        return list(cls._modules.keys())
