import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def fix_and_test():
    # 1. 从环境变量读取配置
    user = os.getenv("DB_USER", "rsmarking")
    password = os.getenv("DB_PASS", "password")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")

    print("=" * 40)
    print("      PostgreSQL 认证排查工具")
    print("=" * 40)
    print(f"[*] 正在尝试用户: {user}")
    print(f"[*] 目标地址: {host}:{port}")
    print(f"[*] 目标数据库: {db_name}")

    # 构造 asyncpg 连接串
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    engine = create_async_engine(url)

    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT current_user, now();"))
            row = res.fetchone()
            print(f"\n[√] 连接成功！")
            print(f"[i] 当前用户: {row[0]}")
            print(f"[i] 服务器时间: {row[1]}")
    except Exception as e:
        print(f"\n[×] 连接失败: {type(e).__name__}")
        print(f"[-] 错误信息: {str(e)}")

        print("\n" + "!" * 40)
        print("建议解决方案：")
        print("!" * 40)

        if "InvalidPasswordError" in str(e) or "password authentication failed" in str(e):
            print(f"1. 确认 .env 文件中 DB_PASS 是否为 '{password}'。")
            print(f"2. 你的容器可能使用了旧的持久化数据，导致环境变量里的密码没生效。")
            print(f"3. 请在终端执行以下命令强制重置容器内密码：")
            print(
                f"\n   docker exec -it <容器名> psql -U {user} -d {db_name} -c \"ALTER USER {user} WITH PASSWORD '{password}';\"")
            print(f"\n   (执行完上述命令后，再次运行此脚本测试)")
        elif "ConnectionRefusedError" in str(e) or "Cannot connect to host" in str(e):
            print(f"1. 检查 DB_HOST 是否正确。如果在 Docker 外部运行，请用 localhost。")
            print(f"2. 如果在 Docker 内部运行，请用服务名（如 rsmarking-postgres）。")
            print(f"3. 检查 5432 端口是否已映射到宿主机。")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix_and_test())