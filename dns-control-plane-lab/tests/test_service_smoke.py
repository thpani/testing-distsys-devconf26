import importlib

import httpx2 as httpx
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_service_smoke_with_background_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("DNS_LAB_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("DNS_LAB_DISABLE_BACKGROUND", "1")

    import dns_control_plane.mbt_harness as service
    service = importlib.reload(service)

    transport = httpx.ASGITransport(app=service.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.get("/health")).json()["ok"] is False
        frontend = (await client.get("/")).text
        assert "ACME CloudDB DNS Control Plane" in frontend
        assert "Resolver tree from root" in frontend
        assert (await client.post("/mbt/reset")).json() == {"ok": True}
        plan = (await client.post("/mbt/planner/generate")).json()
        assert plan["version"] == 1
        assert (await client.post("/mbt/deployers/deployer-a/sync")).json()["ok"] is True
        assert (await client.post("/mbt/deployers/deployer-a/deploy")).json()["ok"] is True
        resolved = (await client.get("/wormhole53/resolve/clouddb.us-east-1.api.acme")).json()
        assert resolved["ips"] == ["192.0.1.1"]
        assert (await client.get("/health")).json() == {
            "ok": True,
            "name": "clouddb.us-east-1.api.acme",
            "ips": ["192.0.1.1"],
        }
        assert (await client.post("/mbt/deployers/deployer-a/cleanup")).status_code == 422
        cleanup = await client.post("/mbt/deployers/deployer-a/cleanup", json={"keep_last_n": 1})
        assert cleanup.json()["ok"] is True
        assert (await client.post("/mbt/deployers/missing/cleanup", json={"keep_last_n": 1})).status_code == 404
