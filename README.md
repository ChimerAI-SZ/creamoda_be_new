myapp/
├── app/
│   ├── __init__.py
│   ├── api/                    # API路由模块
│   │   ├── __init__.py
│   │   ├── v1/                # API版本1
│   │   │   ├── __init__.py
│   │   │   ├── auth.py        # 认证相关路由
│   │   │   └── items.py       # 商品相关路由
│   │   └── deps.py            # 依赖注入
│   ├── core/                   # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py          # 配置类
│   │   └── security.py        # 安全相关
│   ├── db/                     # 数据库
│   │   ├── __init__.py
│   │   └── session.py         # 数据库会话
│   ├── models/                 # 数据库模型
│   │   ├── __init__.py
│   │   └── item.py            # 商品模型
│   └── schemas/               # Pydantic模型
│       ├── __init__.py
│       └── user.py            # 用户schema
├── tests/                     # 测试文件
├── .env                       # 环境变量
├── .gitignore
├── requirements.txt           # 项目依赖
└── main.py                    # 应用入口 