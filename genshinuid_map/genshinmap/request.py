from __future__ import annotations

from typing import Any, List

from httpx import Response, AsyncClient

from .exc import StatusError
from .models import Spot, Tree, MapID, Point, MapInfo, SpotKinds

CLIENT = AsyncClient(
    base_url="https://api-static.mihoyo.com/common/blackboard/ys_obc/v1/map"
)
Spots = dict[int, List[Spot]]


async def _request(endpoint: str) -> dict[str, Any]:
    resp = await CLIENT.get(endpoint)
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    if data["retcode"] != 0:
        raise StatusError(data["retcode"], data["message"])
    return data["data"]


async def get_labels(map_id: MapID) -> List[Tree]:
    """
    获取米游社资源列表

    参数：
        map_id: `MapID`
            地图 ID

    返回：
        `List[Tree]`
    """
    data = await _request(f"/label/tree?map_id={map_id}&app_sn=ys_obc")
    return [Tree.parse_obj(i) for i in data["tree"]]


async def get_points(map_id: MapID) -> List[Point]:
    """
    获取米游社坐标列表

    参数：
        map_id: `MapID`
            地图 ID

    返回：
        `List[Point]`
    """
    data = await _request(f"/point/list?map_id={map_id}&app_sn=ys_obc")
    return [Point.parse_obj(i) for i in data["point_list"]]


async def get_maps(map_id: MapID) -> MapInfo:
    """
    获取米游社地图

    参数：
        map_id: `MapID`
            地图 ID

    返回：
        `MapInfo`
    """
    data = await _request(f"/info?map_id={map_id}&app_sn=ys_obc&lang=zh-cn")
    return MapInfo.parse_obj(data["info"])


async def get_spot_from_game(
    map_id: MapID, cookie: str
) -> tuple[Spots, SpotKinds]:
    """
    获取游戏内标点

    注意：每十分钟只能获取一次，否则会 -2000 错误

    参数：
        map_id: `MapID`
            地图 ID

        cookie: `str`
            米游社 Cookie

    返回：
        `tuple[Spots, SpotKinds]`
    """

    def _raise_for_retcode(resp: Response) -> dict[str, Any]:
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if data["retcode"] != 0:
            raise StatusError(data["retcode"], data["message"])
        return data["data"]

    async with AsyncClient(
        base_url="https://api-takumi.mihoyo.com/common/map_user/ys_obc/v1/map",
        headers={"Cookie": cookie},
    ) as client:
        # 1. 申请刷新
        resp = await client.post(
            "/spot_kind/sync_game_spot",
            json={
                "map_id": str(map_id.value),
                "app_sn": "ys_obc",
                "lang": "zh-cn",
            },
            headers={"Cookie": cookie},
        )
        _raise_for_retcode(resp)

        # 2. 获取类别
        resp = await client.get(
            "/spot_kind/get_spot_kinds?map_id=2&app_sn=ys_obc&lang=zh-cn",
            headers={"Cookie": cookie},
        )
        data = _raise_for_retcode(resp)
        spot_kinds_data = SpotKinds.parse_obj(data)
        ids = [kind.id for kind in spot_kinds_data.list]

        # 3.获取坐标
        resp = await client.post(
            "/spot/get_map_spots_by_kinds",
            json={
                "map_id": str(map_id.value),
                "app_sn": "ys_obc",
                "lang": "zh-cn",
                "kind_ids": ids,
            },
        )
        data = _raise_for_retcode(resp)
        spots: Spots = {}
        for k, v in data["spots"].items():
            spots[int(k)] = [Spot.parse_obj(i) for i in v["list"]]
        return spots, spot_kinds_data
