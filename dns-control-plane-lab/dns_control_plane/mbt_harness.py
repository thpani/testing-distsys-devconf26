from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .deployer import Deployer
from .models import CleanupRequest, LoadBalancerPlanInput
from .planner import Planner
from .wormhole53 import Wormhole53Store
from .acme_cloud import app, deployers, planner, wormhole53


def create_mbt_router(
    *,
    wormhole53: Wormhole53Store,
    deployers: dict[str, Deployer],
    planner: Planner,
) -> APIRouter:
    router = APIRouter(prefix="/mbt")

    @router.post("/reset")
    def reset_system() -> dict:
        wormhole53._internal__reset()
        planner._internal__reset()
        for deployer in deployers.values():
            deployer._internal__reset()
        return {"ok": True}

    @router.post("/planner/generate")
    def generate_plan(plan: list[LoadBalancerPlanInput] | None = None) -> dict:
        return planner.generate(plan)

    @router.post("/deployers/{name}/sync")
    def sync(name: str) -> dict:
        try:
            return deployers[name].sync_dns_state()
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown deployer")

    @router.post("/deployers/{name}/deploy")
    def deploy(name: str) -> dict:
        try:
            return deployers[name].deploy_once()
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown deployer")

    @router.post("/deployers/{name}/cleanup")
    def cleanup(name: str, body: CleanupRequest) -> dict:
        try:
            return deployers[name].cleanup_once(keep_last_n=body.keep_last_n)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown deployer")

    return router


app.include_router(create_mbt_router(wormhole53=wormhole53, deployers=deployers, planner=planner))
