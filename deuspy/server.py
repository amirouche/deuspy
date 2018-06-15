import json
import logging

import daiquiri
from json.decoder import JSONDecodeError
from pathlib import Path
from aiohttp import web


from deuspy.core import Deuspy


ROOT = Path(__file__).parent.resolve()


def pk(*args):
    print(args)
    return args[-1]


async def index(request):
    deuspy = request.app['deuspy']
    data = await request.read()
    if data:
        kwargs = json.loads(data)
    else:
        kwargs = dict()
    uids = deuspy.query(**kwargs)
    everything = {uid: deuspy.read(uid) for uid in uids}
    return web.json_response(everything)


async def create(request):
    deuspy = request.app['deuspy']
    try:
        doc = await request.json()
    except JSONDecodeError:
        msg = 'Body must be a JSON encoded JSObject'
        raise web.HTTPBadRequest(reason=msg)
    uid = deuspy.create(doc)
    return web.json_response(uid)


async def read(request):
    uid = request.match_info['uid']
    try:
        uid = int(uid)
    except ValueError:
        msg = 'Parameter must be an integer'
        raise web.HTTPBadRequest(reason=msg)
    deuspy = request.app['deuspy']
    doc = deuspy.read(uid)
    if doc is None:
        raise web.HTTPNotFound()
    else:
        return web.json_response(doc)


async def update(request):
    uid = request.match_info['uid']
    try:
        uid = int(uid)
    except ValueError:
        msg = 'Parameter must be an integer'
        raise web.HTTPBadRequest(reason=msg)
    try:
        doc = await request.json()
    except JSONDecodeError:
        msg = 'Body must be a JSON encoded JSObject'
        raise web.HTTPBadRequest(reason=msg)
    if not isinstance(doc, dict):
        msg = 'Body must be a JSON encoded JSObject'
        raise web.HTTPBadRequest(reason=msg)
    deuspy = request.app['deuspy']
    deuspy.update(uid, doc)
    return web.json_response()


async def delete(request):
    uid = request.match_info['uid']
    try:
        uid = int(uid)
    except ValueError:
        msg = 'Parameter must be an integer'
        raise web.HTTPBadRequest(reason=msg)
    deuspy = request.app['deuspy']
    if deuspy.delete(uid):
        return web.json_response()
    else:
        raise web.HTTPNotFound()


def main():
    daiquiri.setup(level=logging.DEBUG)
    app = web.Application()
    cwd = str(Path('.').resolve())
    app['deuspy'] = Deuspy(cwd, create_if_missing=True)
    app.add_routes([web.get('/', index)])
    app.add_routes([web.post('/', create)])
    app.add_routes([web.get('/{uid}', read)])
    app.add_routes([web.post('/{uid}', update)])
    app.add_routes([web.delete('/{uid}', delete)])
    web.run_app(app, port=9990)


if __name__ == '__main__':
    main()
