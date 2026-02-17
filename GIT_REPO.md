# Git 仓库信息

## 仓库地址

- **平台**: GitHub
- **仓库**: https://github.com/kukumaomao2022-dotcom/inventory-system
- **类型**: Public
- **描述**: 库存管理系统 - Inventory Management System

## 认证信息

| 类型 | 值 |
|------|-----|
| GitHub Token | `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (保存在本地 .env 或单独文件) |
| 用户名 | kukumaomao2022-dotcom |

## 代理配置

```bash
# Git HTTP/HTTPS 代理
git config --global http.proxy http://127.0.0.1:10808
git config --global https.proxy http://127.0.0.1:10808
```

## 缓冲区配置

```bash
# 推送大文件时需要更大的缓冲区
git config --global http.postBuffer 1048576000  # 1GB
```

## 常用命令

```bash
# 查看状态
git status

# 查看提交历史
git log --oneline

# 拉取最新代码
git pull origin main

# 推送代码
git push origin main

# 查看远程仓库
git remote -v
```

## 初始化时间

2026-02-17
