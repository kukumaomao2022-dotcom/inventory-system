"""环境变量验证模块"""
import logging
import sys

from app.core.config import settings

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """环境变量验证失败异常"""
    pass


def validate_environment() -> None:
    """验证所有必需的环境变量

    Raises:
        ValidationError: 如果任何必需的环境变量缺失或格式不正确
    """
    errors = []

    # ===== 数据库配置 =====
    database_url = settings.DATABASE_URL
    if not database_url or database_url.startswith("postgresql+asyncpg://user:password@localhost:5432"):
        errors.append({
            "var": "DATABASE_URL",
            "reason": "数据库连接 URL 未设置",
            "example": "postgresql+asyncpg://user:password@localhost:5432/inventory_db 或 sqlite+aiosqlite:///inventory.db",
            "format": "postgresql+asyncpg://[user]:[password]@[host]:[port]/[database] 或 sqlite+aiosqlite:///path/to/database"
        })

    # ===== Redis 配置 =====
    redis_url = settings.REDIS_URL
    if not redis_url.startswith("redis"):
        errors.append({
            "var": "REDIS_URL",
            "reason": "Redis URL 格式不正确",
            "current": redis_url,
            "expected": "redis://[host]:[port]/[db]"
        })

    # ===== 乐天 API 配置 (可选，但建议设置) =====
    service_secret = settings.RAKUTEN_DEFAULT_SERVICE_SECRET
    license_key = settings.RAKUTEN_DEFAULT_LICENSE_KEY

    if not service_secret or not license_key:
        logger.warning(
            "乐天 API 凭证未完整设置 (RAKUTEN_DEFAULT_SERVICE_SECRET 或 "
            "RAKUTEN_DEFAULT_LICENSE_KEY 缺失)，API 功能将不可用"
        )
    else:
        # 验证凭证格式
        if len(service_secret) < 10:
            errors.append({
                "var": "RAKUTEN_DEFAULT_SERVICE_SECRET",
                "reason": "Service Secret 格式不正确（太短）",
                "current": f"{service_secret[:5]}...{service_secret[-3:]}",
                "expected": "通常以 'SP' 开头，后跟数字"
            })

        if len(license_key) < 10:
            errors.append({
                "var": "RAKUTEN_DEFAULT_LICENSE_KEY",
                "reason": "License Key 格式不正确（太短）",
                "current": f"{license_key[:5]}...{license_key[-3:]}",
                "expected": "通常以 'SL' 开头，后跟数字"
            })

    # ===== 代理配置 (可选) =====
    proxy_url = settings.RAKUTEN_PROXY
    if proxy_url:
        if not (proxy_url.startswith("http://") or proxy_url.startswith("https://")):
            errors.append({
                "var": "RAKUTEN_PROXY",
                "reason": "代理 URL 格式不正确",
                "current": proxy_url,
                "format": "http://[host]:[port] 或 https://[host]:[port]",
                "example": "http://127.0.0.1:10808"
            })

    # ===== 环境类型 =====
    environment = settings.ENVIRONMENT
    if environment not in ["prod", "test", "dev"]:
        errors.append({
            "var": "ENVIRONMENT",
            "reason": "环境类型不正确",
            "current": environment,
            "allowed": "prod, test, dev"
        })

    # ===== 汇总错误 =====
    if errors:
        print("\n" + "="*70)
        print("❌ 环境变量验证失败！")
        print("="*70)
        print("\n缺少或格式不正确的环境变量：\n")

        for i, error in enumerate(errors, 1):
            print(f"{i}. {error['var']}")
            print(f"   原因: {error['reason']}")
            if 'current' in error:
                print(f"   当前值: {error['current']}")
            if 'example' in error:
                print(f"   示例: {error['example']}")
            if 'format' in error:
                print(f"   格式: {error['format']}")
            if 'allowed' in error:
                print(f"   允许值: {error['allowed']}")
            print()

        print("="*70)
        print("💡 请检查 .env 文件或设置环境变量")
        print("="*70 + "\n")

        # 抛出异常，阻止应用启动
        raise ValidationError(f"环境变量验证失败：{len(errors)} 个错误")

    logger.info("✅ 环境变量验证通过")


def print_env_info() -> None:
    """打印当前环境配置（不包含敏感信息）"""
    print("\n" + "="*70)
    print("📋 当前环境配置")
    print("="*70)
    print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
    print(f"  DATABASE_URL: {settings.DATABASE_URL[:30]}...")
    print(f"  REDIS_URL: {settings.REDIS_URL}")
    print(f"  RAKUTEN_PROXY: {settings.RAKUTEN_PROXY or '未使用代理'}")
    print(f"  API_HOST: {settings.API_HOST}")
    print(f"  API_PORT: {settings.API_PORT}")
    print(f"  RAKUTEN_DEFAULT_SERVICE_SECRET: {'已设置' if settings.RAKUTEN_DEFAULT_SERVICE_SECRET else '未设置'}")
    print(f"  RAKUTEN_DEFAULT_LICENSE_KEY: {'已设置' if settings.RAKUTEN_DEFAULT_LICENSE_KEY else '未设置'}")
    print("="*70 + "\n")


if __name__ == "__main__":
    """测试环境变量验证"""
    try:
        validate_environment()
        print_env_info()
        print("✅ 所有检查通过！")
    except ValidationError as e:
        print(f"❌ {e}")
        sys.exit(1)
