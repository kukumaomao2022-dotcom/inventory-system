import asyncio
from app.db.database import async_session_factory
from sqlalchemy import select, update
from app.db.models import Store

async def fix_config():
    async with async_session_factory() as session:
        # 获取店铺
        result = await session.execute(select(Store).where(Store.store_id == "ドマ-1"))
        store = result.scalar_one_or_none()
        
        if store:
            print(f"当前配置: {store.api_config}")
            
            # 添加shopUrl
            new_config = dict(store.api_config)
            new_config['shopUrl'] = "coucou-doma.rakuten.co.jp"
            
            # 更新配置
            await session.execute(
                update(Store)
                .where(Store.store_id == "ドマ-1")
                .values(api_config=new_config)
            )
            await session.commit()
            
            print(f"更新后配置: {new_config}")
            print("✅ 配置已更新")
        else:
            print("店铺不存在")

if __name__ == "__main__":
    asyncio.run(fix_config())
