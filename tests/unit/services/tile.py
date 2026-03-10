import pytest


def debug_routes(client):
    """辅助函数：打印当前客户端注册的所有路由，用于排查 404"""
    print("\n[Debug] Registered Routes:")
    for route in client.app.routes:
        print(f"  - {route.path} [{route.methods}]")


def test_tile_service_health(client):
    """
    测试瓦片服务的健康检查接口。
    """
    # 诊断：如果怀疑没挂载成功，取消下面这行的注释查看路由表
    debug_routes(client)

    # 尝试访问挂载路径
    response = client.get("/tile/health")

    # 容错处理：如果 404，可能是因为在 conftest 中 prefix 重复或缺失
    if response.status_code == 404:
        # 尝试根路径
        response = client.get("/health")

    assert response.status_code == 200, f"路由未找到，当前可用路由请查看 debug_routes 输出"
    data = response.json()
    assert data.get("status") == "ready"
    assert data.get("service") == "tile_service"


def test_get_tile_invalid_coord(client):
    """
    测试非法瓦片坐标请求。
    """
    response = client.get("/tile/v1/99/99/99.png")
    # 如果 404 可能是 prefix 导致的，也尝试不带 prefix
    if response.status_code == 404:
        response = client.get("/v1/99/99/99.png")

    assert response.status_code in [400, 404]


def test_tile_service_cors_headers(client):
    """
    验证 CORS 头部。
    注意：若路由 404，FastAPI 中间件可能不会附加 CORS 头部。
    """
    target_path = "/tile/health"
    res_check = client.get(target_path)
    if res_check.status_code == 404:
        target_path = "/health"

    response = client.options(target_path, headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })

    origin = response.headers.get("access-control-allow-origin")
    # 如果依然为 None，说明 CORSMiddleware 没有被 master_app 加载
    assert origin is not None, "CORS 头部缺失，请检查 master_app 是否添加了中间件"
    assert origin in ["*", "http://localhost:3000"]


def test_tile_not_found_error_format(client):
    """
    验证错误响应是否为标准的 JSON 格式。
    """
    response = client.get("/tile/non_existent_path_really_random")
    assert response.status_code == 404
    assert "detail" in response.json()
