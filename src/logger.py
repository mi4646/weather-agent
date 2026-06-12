"""
logger.py — 日志配置模块

日志分两路：
1. 文件日志（logs/agent.log）→ 详细的执行流程，供开发者学习
2. 终端输出        → 只显示最终答案，不干扰用户
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "agent") -> logging.Logger:
    """配置并返回 logger 实例"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 日志目录
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "agent.log"

    # ── 文件 handler：记录所有级别 ──────────────────────
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(file_handler)

    # ── 终端 handler：默认只显示 WARNING 以上 ──────────
    # main.py 里可以动态调级别来控制终端输出
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "agent") -> logging.Logger:
    """获取已配置的 logger（首次调用自动初始化）"""
    return setup_logger(name)
