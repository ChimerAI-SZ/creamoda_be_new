#!/usr/bin/env python3
"""
批量创建测试账号脚本
创建从 creamoda.test4@gmail.com 到 creamoda.test20@gmail.com 的17个测试账号
密码统一为: Creamoda2025!
支持不同环境：test, prod, createprod
"""

import sys
import os
import argparse
from datetime import datetime
from sqlalchemy.orm import Session

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db.session import get_db
from src.models.models import UserInfo, Credit
from src.utils.password import generate_salt, hash_password
from src.utils.uid import generate_uid
from src.config.log_config import logger

def create_test_accounts(environment="test"):
    """创建17个测试账号"""
    
    # 设置环境变量
    os.environ['APP_ENV'] = environment
    
    # 清除配置缓存，强制重新加载
    import importlib
    import src.config.config
    importlib.reload(src.config.config)
    from src.config.config import get_settings
    get_settings.cache_clear()
    
    # 测试账号配置
    test_accounts = []
    for i in range(4, 21):  # 4到20，共17个账号
        email = f"creamoda.test{i}@gmail.com"
        username = f"test_user_{i}"
        password = "Creamoda2025!"
        
        test_accounts.append({
            'email': email,
            'username': username,
            'password': password
        })
    
    # 获取数据库连接
    db = next(get_db())
    
    try:
        created_count = 0
        skipped_count = 0
        
        for account in test_accounts:
            try:
                # 检查账号是否已存在
                existing_user = db.query(UserInfo).filter(UserInfo.email == account['email']).first()
                if existing_user:
                    # 检查是否有积分记录，如果没有则添加
                    existing_credit = db.query(Credit).filter(Credit.uid == existing_user.id).first()
                    if not existing_credit:
                        credit_record = Credit(
                            uid=existing_user.id,
                            credit=100,
                            lock_credit=0,
                            create_time=datetime.utcnow(),
                            update_time=datetime.utcnow()
                        )
                        db.add(credit_record)
                        db.commit()
                        print(f"账号 {account['email']} 已存在，但添加了积分记录")
                    else:
                        print(f"账号 {account['email']} 已存在，跳过创建")
                    skipped_count += 1
                    continue
                
                # 生成盐值和密码哈希
                salt = generate_salt()
                hashed_password = hash_password(account['password'], salt)
                
                # 生成用户ID
                uid = generate_uid()
                
                # 创建用户
                new_user = UserInfo(
                    email=account['email'],
                    pwd=hashed_password,
                    salt=salt,
                    uid=uid,
                    username=account['username'],
                    status=1,  # 正常状态
                    email_verified=1,  # 直接设置为已验证，跳过邮箱验证
                    create_time=datetime.utcnow(),
                    update_time=datetime.utcnow()
                )
                
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                
                # 为新用户创建积分记录
                credit_record = Credit(
                    uid=new_user.id,  # 使用 user.id 而不是 uid
                    credit=100,  # 给每个测试账号100积分
                    lock_credit=0,
                    create_time=datetime.utcnow(),
                    update_time=datetime.utcnow()
                )
                
                db.add(credit_record)
                db.commit()
                
                print(f"✅ 成功创建账号: {account['email']} (用户名: {account['username']}, UID: {uid})")
                created_count += 1
                
            except Exception as e:
                print(f"❌ 创建账号 {account['email']} 失败: {str(e)}")
                db.rollback()
                continue
        
        print(f"\n📊 创建结果统计:")
        print(f"   成功创建: {created_count} 个账号")
        print(f"   跳过已存在: {skipped_count} 个账号")
        print(f"   总计处理: {len(test_accounts)} 个账号")
        
        # 验证创建的账号
        print(f"\n🔍 验证创建的账号:")
        for account in test_accounts:
            user = db.query(UserInfo).filter(UserInfo.email == account['email']).first()
            if user:
                credit = db.query(Credit).filter(Credit.uid == user.uid).first()
                print(f"   {account['email']} - 状态: 正常, 积分: {credit.credit if credit else 0}")
            else:
                print(f"   {account['email']} - 状态: 未找到")
                
    except Exception as e:
        print(f"❌ 脚本执行失败: {str(e)}")
        logger.error(f"Create test accounts failed: {str(e)}")
        db.rollback()
    finally:
        db.close()

def list_test_accounts(environment="test"):
    """列出所有测试账号"""
    # 设置环境变量
    os.environ['APP_ENV'] = environment
    
    # 清除配置缓存，强制重新加载
    from src.config.config import get_settings
    get_settings.cache_clear()
    db = next(get_db())
    
    try:
        print("📋 当前测试账号列表:")
        print("-" * 80)
        
        # 查询所有测试账号
        test_users = db.query(UserInfo).filter(
            UserInfo.email.like('creamoda.test%@gmail.com')
        ).order_by(UserInfo.email).all()
        
        if not test_users:
            print("   没有找到测试账号")
            return
        
        for user in test_users:
            credit = db.query(Credit).filter(Credit.uid == user.uid).first()
            print(f"   邮箱: {user.email}")
            print(f"   用户名: {user.username}")
            print(f"   UID: {user.uid}")
            print(f"   状态: {'正常' if user.status == 1 else '禁用'}")
            print(f"   邮箱验证: {'已验证' if user.email_verified == 1 else '未验证'}")
            print(f"   积分: {credit.credit if credit else 0}")
            print(f"   创建时间: {user.create_time}")
            print("-" * 80)
            
    except Exception as e:
        print(f"❌ 查询失败: {str(e)}")
    finally:
        db.close()

def delete_test_accounts(environment="test"):
    """删除所有测试账号"""
    # 设置环境变量
    os.environ['APP_ENV'] = environment
    
    # 清除配置缓存，强制重新加载
    from src.config.config import get_settings
    get_settings.cache_clear()
    db = next(get_db())
    
    try:
        # 查询所有测试账号
        test_users = db.query(UserInfo).filter(
            UserInfo.email.like('creamoda.test%@gmail.com')
        ).all()
        
        if not test_users:
            print("   没有找到测试账号")
            return
        
        deleted_count = 0
        for user in test_users:
            # 删除积分记录
            db.query(Credit).filter(Credit.uid == user.uid).delete()
            # 删除用户
            db.delete(user)
            deleted_count += 1
        
        db.commit()
        print(f"✅ 成功删除 {deleted_count} 个测试账号")
        
    except Exception as e:
        print(f"❌ 删除失败: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试账号管理工具")
    parser.add_argument("action", choices=["create", "list", "delete"], 
                       help="操作类型: create(创建), list(列出), delete(删除)")
    parser.add_argument("--env", choices=["test", "prod", "createprod"], 
                       default="test", help="环境选择: test(测试), prod(生产), createprod(创建生产)")
    
    args = parser.parse_args()
    
    print(f"🌍 当前环境: {args.env.upper()}")
    
    if args.action == "create":
        print("🚀 开始创建测试账号...")
        create_test_accounts(args.env)
    elif args.action == "list":
        list_test_accounts(args.env)
    elif args.action == "delete":
        confirm = input(f"⚠️  确定要在 {args.env.upper()} 环境中删除所有测试账号吗？(yes/no): ")
        if confirm.lower() == 'yes':
            delete_test_accounts(args.env)
        else:
            print("操作已取消")
