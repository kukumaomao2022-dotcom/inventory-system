import asyncio
from app.db.database import async_session_factory
from sqlalchemy import select
from app.db.models import Store

async def check_config():
    async with async_session_factory() as session:
        result = await session.execute(select(Store))
        stores = result.scalars().all()
        
        for store in stores:
            print(f"\n店铺: {store.store_name} ({store.store_id})")
            print(f"平台类型: {store.platform_type}")
            print(f"状态: {store.status}")
            print("API配置:")
            for key, value in store.api_config.items():
                print(f"  {key}: {'*' * len(str(value)) if 'secret' in key.lower() or 'key' in key.lower() else value}")
            
            # 检查必要字段
            required = ['serviceSecret', 'licenseKey', 'shopUrl']
            missing = [field for field in required if field not in store.api_config]
            if missing:
                print(f"⚠️  缺少必要字段: {missing}")
            else:
                print("✅ 配置完整")

if __name__ == "__main__":
    asyncio.run(check_config())
