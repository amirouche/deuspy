from urllib.parse import urlencode

import aiohttp

from deuspy.base import DeuspyBase
from deuspy.base import DeuspyException


async def response_to_exception(response):
    reason = await response.text()
    msg = '{} ({})'.format(reason, response.status)
    raise DeuspyException(msg)


class Deuspy(DeuspyBase):

    def __init__(self, session, host, port):
        self._session = session
        self._domain = host + ':' + str(port)

    async def create(self, doc):
        async with self._session.post(self._domain) as response:
            if response.status == 200:
                return await response.json()
            else:
                await response_to_exception(response)

    async def read(self, uid):
        url = self._domain + '/' + str(uid)
        async with self._session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                await response_to_exception(response)

    async def update(self, uid, doc):
        url = self._domain + '/' + str(uid)
        async with self._session.post(url, json=doc) as response:
            if response.status != 200:
                await response_to_exception(response)

    async def delete(self, uid):
        url = self._domain + '/' + str(uid)
        async with self._session.delete(url) as response:
            if response.status != 200:
                await response_to_exception(response)

    async def query(self, **kwargs):
        url = self._domain + '/' + urlencode(kwargs)
        async with self._session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                await response_to_exception(response)

    async def close(self):
        await self.session.close()


async def connect(host='http://localhost', port=9990):
    session = aiohttp.ClientSession()
    deuspy = Deuspy(session)
    return deuspy
