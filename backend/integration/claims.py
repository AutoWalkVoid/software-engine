"""C（失物认领）在本仓库内不包含，这里是符合契约 7.1 的桩实现。

本仓库只保留 B 子系统（信息发布与浏览）的可运行副本；认领模块由队友负责。
B 在撤回、恢复、撤销完成时需要调用 C 的函数，桩实现保证这些流程可以独立跑通：

- ``close_pending_claims``：撤回信息时关闭待处理认领，没有 C 时无记录可关，返回 0；
- ``has_completed_claim``：撤销完成前检查是否存在已完成的认领，没有 C 时恒为 ``False``。

接入真实 C 模块时，把这里换成 ``from claims.services.claims import ...`` 即可，
调用方不需要改动。
"""

from __future__ import annotations


def close_pending_claims(post_id: str, reason: str = "") -> int:
    """关闭该信息的待处理认领申请；桩实现不做任何事。"""
    return 0


def has_completed_claim(post_id: str) -> bool:
    """该信息是否存在双方确认完成的认领记录；桩实现恒为否。"""
    return False


__all__ = ["close_pending_claims", "has_completed_claim"]
