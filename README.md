# Creamoda Backend

基于 FastAPI 的 Creamoda 后端服务。

## 开发指南

1. 数据库模型生成
2. 运行测试

## 环境要求

- Python 3.8+
- MySQL 5.7+
- Redis 6.0+

## 配置说明

主要配置项（config.yaml）：
- API 配置
- 数据库配置
- Redis 配置
- SMTP 配置
- JWT 配置
- Google OAuth2 配置

## 部署

1. 生产环境配置
- 修改 config.yaml 中的生产环境配置
- 确保所有敏感信息使用环境变量或安全存储

2. 使用 uvicorn 运行