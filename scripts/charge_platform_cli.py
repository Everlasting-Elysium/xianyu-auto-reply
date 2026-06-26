"""
xckj9 社交媒体代刷平台客户端 CLI 调试工具

用法（必须先在后台 Web 录入一个平台账号配置）：

    # 1. 登录（验证账密）
    python scripts/charge_platform_cli.py --config-id 1 login [--force]

    # 2. 查用户信息 + 余额
    python scripts/charge_platform_cli.py --config-id 1 balance

    # 3. 查商品分类
    python scripts/charge_platform_cli.py --config-id 1 classes

    # 4. 查商品列表（可关键字搜索）
    python scripts/charge_platform_cli.py --config-id 1 goods [--keyword 点赞] [--page 1]

    # 5. 查商品详情（含 ParamsTemplate 下单参数模板）
    python scripts/charge_platform_cli.py --config-id 1 goods-detail --goods-id 128311

    # 6. 测试下单（注意会真实扣费！）
    # --params 用 key=value 形式，多个用 | 分隔，key 必须是商品 ParamsTemplate 里的 key
    python scripts/charge_platform_cli.py --config-id 1 order \\
        --goods-id 128311 --quantity 5 --params "作品链接=https://www.douyin.com/video/xxx"

    # 7. 查平台订单列表
    python scripts/charge_platform_cli.py --config-id 1 orders
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend-web"))


def _pretty(data: object) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(data)


async def _cmd_login(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import get_client_by_config_id

    client = await get_client_by_config_id(args.config_id)
    try:
        token = await client.ensure_token(force_relogin=args.force)
        print(f"[OK] 登录成功，token 长度={len(token)}")
        print(f"  token preview: {token[:20]}...{token[-10:]}")
    finally:
        await client.close()


async def _cmd_balance(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import get_client_by_config_id

    client = await get_client_by_config_id(args.config_id)
    try:
        info = await client.get_user_info()
        print("[OK] 用户信息：")
        print(_pretty(info))
        balance = await client.get_balance()
        print(f"\n[OK] 当前余额: {balance}")
    finally:
        await client.close()


async def _cmd_goods(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import get_client_by_config_id

    client = await get_client_by_config_id(args.config_id)
    try:
        items = await client.list_goods(
            page=args.page,
            page_count=args.page_count,
            keyword=args.keyword or "",
            class_id=args.class_id,
        )
        print(f"[OK] 商品列表（第 {args.page} 页，共 {len(items)} 条）:")
        for item in items:
            print(
                f"  [Id={item.get('Id')}] {item.get('GoodsName', '')[:50]} | "
                f"分类={item.get('ClassName1')}/{item.get('ClassName2')} | "
                f"单价={item.get('GoodsPrice')} | 数量={item.get('MinOrderNum')}~{item.get('MaxOrderNum')}"
            )
    finally:
        await client.close()


async def _cmd_goods_detail(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import get_client_by_config_id

    client = await get_client_by_config_id(args.config_id)
    try:
        result = await client.get_goods_detail(args.goods_id)
        print(f"[OK] 商品 {args.goods_id} 详情:")
        print(_pretty(result))
    finally:
        await client.close()


async def _cmd_classes(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import get_client_by_config_id

    client = await get_client_by_config_id(args.config_id)
    try:
        result = await client.get_goods_class_list()
        print(f"[OK] 商品分类（共 {len(result)} 个一级分类）:")
        for cls in result:
            print(f"  [{cls.get('Id')}] {cls.get('Name')} (parent={cls.get('ParentId')}, level={cls.get('Level')})")
            children = cls.get("Childern") or []
            for child in children:
                print(f"    └─ [{child.get('Id')}] {child.get('Name')}")
    finally:
        await client.close()


async def _cmd_order(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import ChargePlatformClient, get_client_by_config_id

    params_dict: dict[str, str] = {}
    for pair in args.params.split("|"):
        if "=" not in pair:
            print(f"参数格式错误（应为 key=value）: {pair}")
            return
        k, v = pair.split("=", 1)
        params_dict[k.strip()] = v.strip()

    print(f"⚠️  即将下单：goods_id={args.goods_id}, quantity={args.quantity}")
    print(f"           参数: {params_dict}")

    client = await get_client_by_config_id(args.config_id)
    try:
        detail = await client.get_goods_detail(args.goods_id)
        print(f"\n商品: {detail.get('GoodsName')}")
        print(f"  单价: {detail.get('GoodsPrice')} | 数量范围: {detail.get('MinOrderNum')} ~ {detail.get('MaxOrderNum')}")
        template_raw = detail.get("ParamsTemplate", "")
        order_params = ChargePlatformClient.build_order_params(template_raw, params_dict)
        print(f"  即将提交的 OrderParams: {_pretty(order_params)}")

        confirm = input("\n确认下单（会真实扣费）？输入 yes 继续：").strip().lower()
        if confirm != "yes":
            print("已取消")
            return

        result = await client.create_order(
            goods_id=args.goods_id,
            quantity=args.quantity,
            params=order_params,
            cf_count=args.cf_count,
        )
        print("[OK] 下单成功:")
        print(_pretty(result))
    finally:
        await client.close()


async def _cmd_orders(args: argparse.Namespace) -> None:
    from common.services.charge_platform_client import get_client_by_config_id

    client = await get_client_by_config_id(args.config_id)
    try:
        result = await client.list_orders(page=args.page, page_count=args.page_count)
        print(f"[OK] 平台订单列表（第 {args.page} 页）:")
        print(_pretty(result))
    finally:
        await client.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="charge platform CLI")
    parser.add_argument("--config-id", type=int, required=True, help="charge_platform_configs.id")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login").add_argument("--force", action="store_true", help="强制重新登录")
    sub.add_parser("balance")
    sub.add_parser("classes")

    goods = sub.add_parser("goods")
    goods.add_argument("--page", type=int, default=1)
    goods.add_argument("--page-count", type=int, default=20)
    goods.add_argument("--keyword", default="")
    goods.add_argument("--class-id", type=int, default=None)

    goods_detail = sub.add_parser("goods-detail")
    goods_detail.add_argument("--goods-id", required=True)

    order = sub.add_parser("order")
    order.add_argument("--goods-id", required=True)
    order.add_argument("--quantity", type=int, required=True)
    order.add_argument("--params", required=True, help="key=value, 多个用 | 分隔")
    order.add_argument("--cf-count", type=int, default=0)

    orders = sub.add_parser("orders")
    orders.add_argument("--page", type=int, default=1)
    orders.add_argument("--page-count", type=int, default=20)

    return parser


def _resolve_cmd_args() -> argparse.Namespace:
    argv = sys.argv[1:]
    cmd_keywords = {"login", "balance", "classes", "goods", "goods-detail", "order", "orders"}
    cmd_idx = next((i for i, a in enumerate(argv) if a in cmd_keywords), None)
    if cmd_idx is None:
        _build_parser().parse_args(argv)
        sys.exit(1)

    head = argv[:cmd_idx]
    tail = argv[cmd_idx:]
    return _build_parser().parse_args(head + tail)


async def main() -> None:
    args = _resolve_cmd_args()
    handlers = {
        "login": _cmd_login,
        "balance": _cmd_balance,
        "classes": _cmd_classes,
        "goods": _cmd_goods,
        "goods-detail": _cmd_goods_detail,
        "order": _cmd_order,
        "orders": _cmd_orders,
    }
    await handlers[args.cmd](args)


if __name__ == "__main__":
    asyncio.run(main())
