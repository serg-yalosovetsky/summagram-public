import asyncio
import httpx


async def main():
    try:
        transport = httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get("http://localhost/v1.43/containers/json")
            print(f"Status: {resp.status_code}")
            containers = resp.json()
            names = [c["Names"][0] for c in containers]
            print(f"Containers: {names}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
