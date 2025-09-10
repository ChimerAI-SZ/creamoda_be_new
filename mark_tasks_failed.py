#!/usr/bin/env python3
"""
批量将卡住的图像生成任务标记为失败状态的脚本
用于解决并发限制问题
"""

import sys
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db.session import SessionLocal
from src.models.models import GenImgResult, GenImgRecord
from src.config.log_config import logger

def mark_stuck_tasks_as_failed():
    """将卡住的任务标记为失败状态"""
    db = SessionLocal()
    try:
        # 查找所有状态为 1(待生成) 或 2(生成中) 的任务
        stuck_tasks = db.query(GenImgResult).filter(
            GenImgResult.status.in_([1, 2])
        ).all()
        
        if not stuck_tasks:
            print("✅ 没有找到卡住的任务")
            return
        
        print(f"🔍 找到 {len(stuck_tasks)} 个卡住的任务:")
        
        for task in stuck_tasks:
            print(f"  - Result ID: {task.id}, Status: {task.status}, User: {task.uid}, Updated: {task.update_time}")
        
        # 询问用户确认
        confirm = input(f"\n❓ 确认将这 {len(stuck_tasks)} 个任务标记为失败? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("❌ 操作已取消")
            return
        
        # 批量更新状态
        failed_count = 0
        for task in stuck_tasks:
            try:
                task.status = 4  # 标记为失败
                task.update_time = datetime.utcnow()
                failed_count += 1
                print(f"✅ 标记任务 {task.id} 为失败状态")
            except Exception as e:
                print(f"❌ 处理任务 {task.id} 时出错: {e}")
        
        # 提交更改
        db.commit()
        print(f"\n🎉 成功标记 {failed_count} 个任务为失败状态")
        print("现在可以重新提交新的生成任务了!")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        db.rollback()
    finally:
        db.close()

def mark_specific_user_tasks_failed(user_id: int):
    """将指定用户的卡住任务标记为失败"""
    db = SessionLocal()
    try:
        stuck_tasks = db.query(GenImgResult).filter(
            GenImgResult.uid == user_id,
            GenImgResult.status.in_([1, 2])
        ).all()
        
        if not stuck_tasks:
            print(f"✅ 用户 {user_id} 没有卡住的任务")
            return
        
        print(f"🔍 用户 {user_id} 有 {len(stuck_tasks)} 个卡住的任务")
        
        for task in stuck_tasks:
            task.status = 4  # 标记为失败
            task.update_time = datetime.utcnow()
            print(f"✅ 标记任务 {task.id} 为失败状态")
        
        db.commit()
        print(f"🎉 成功标记用户 {user_id} 的 {len(stuck_tasks)} 个任务为失败状态")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        db.rollback()
    finally:
        db.close()

def show_current_status():
    """显示当前任务状态统计"""
    db = SessionLocal()
    try:
        # 统计各状态的任务数量
        status_counts = {}
        status_names = {1: "待生成", 2: "生成中", 3: "已生成", 4: "生成失败"}
        
        for status_code, status_name in status_names.items():
            count = db.query(GenImgResult).filter(GenImgResult.status == status_code).count()
            status_counts[status_name] = count
        
        print("📊 当前任务状态统计:")
        for status_name, count in status_counts.items():
            print(f"  {status_name}: {count} 个任务")
        
        # 显示最近的一些任务
        recent_tasks = db.query(GenImgResult).order_by(GenImgResult.create_time.desc()).limit(10).all()
        print(f"\n🕒 最近 10 个任务:")
        for task in recent_tasks:
            status_name = status_names.get(task.status, f"未知状态({task.status})")
            print(f"  ID: {task.id}, 用户: {task.uid}, 状态: {status_name}, 创建时间: {task.create_time}")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🛠️  图像生成任务管理工具")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            show_current_status()
        elif sys.argv[1] == "user" and len(sys.argv) > 2:
            try:
                user_id = int(sys.argv[2])
                mark_specific_user_tasks_failed(user_id)
            except ValueError:
                print("❌ 用户ID必须是数字")
        else:
            print("用法:")
            print("  python mark_tasks_failed.py                # 标记所有卡住的任务为失败")
            print("  python mark_tasks_failed.py status         # 显示当前任务状态")
            print("  python mark_tasks_failed.py user <用户ID>   # 标记指定用户的卡住任务为失败")
    else:
        mark_stuck_tasks_as_failed()
