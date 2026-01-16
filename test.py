import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
import ssl

async def test():
    sslcontext = ssl.create_default_context()
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE  # ОТКЛЮЧАЕМ проверку сертификатов

    connector = ProxyConnector.from_url("socks5://0Y6Ht1:aQb3hs@212.102.144.176:9237", ssl=sslcontext)

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get("https://api.telegram.org") as resp:
            print(resp.status)
            text = await resp.text()
            print(text[:200])  # первые 200 символов ответа

asyncio.run(test())
