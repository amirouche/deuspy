import json
import sys
from random import randint

from deuspy.packing import pack
from deuspy.packing import unpack

from plyvel import DB


def random():
    return randint(0, sys.maxsize)


class Deuspy:

    def __init__(self, *args, **kwargs):
        self._db = DB(*args, **kwargs)
        self._docs = self._db.prefixed_db(b'docs:')
        self._index = self._db.prefixed_db(b'index:')

    def _save(self, doc, uid):
        # store the doc as json
        key = pack((uid,))
        value = json.dumps(doc).encode('utf-8')
        self._docs.put(key, value)
        # index it
        for key, value in doc.items():
            index = pack((key, value, uid))
            self._index.put(index, b'')
        # done!

    def create(self, doc):
        """Store `doc` and return it's unique identifier"""
        # make a unique random identifier
        while True:
            uid = random()
            if self.read(uid) is None:
                break

        self._save(doc, uid)

        return uid

    def read(self, uid):
        """Retrieve the doc associated with `uid`"""
        key = pack((uid,))
        value = self._docs.get(key)
        if value is None:
            return None
        else:
            value = value.decode('utf-8')
            doc = json.loads(value)
            return doc

    def delete(self, uid):
        """Delete the document associated with `uid`"""
        doc = self.read(uid)
        if doc is None:
            return  # XXX: maybe raise something
        # delete from the index first...
        for key, value in doc.items():
            index = pack((key, value, uid))
            self._index.delete(index)
        # ... and delete completly
        key = pack((uid,))
        self._docs.delete(key)

    def update(self, uid, doc):
        self.delete(uid)
        self._save(doc, uid)

    def query(self, **kwargs):
        if kwargs:
            items = list(kwargs.items())
            key, value = items[0]
            rest = items[1:]

            start = pack((key, value, 0))
            stop = pack((key, value, sys.maxsize))

            iterator = self._index.iterator(start=start, stop=stop, include_value=False)

            for index in iterator:
                _, _, uid = unpack(index)
                for key, value in rest:
                    index = pack((key, value, uid))
                    if self._index.get(index) is None:
                        break  # skip it
                else:
                    # all the kwargs match
                    yield uid
        else:
            for key in self._docs.iterator(include_value=False):
                uid = unpack(key)[0]
                yield uid
