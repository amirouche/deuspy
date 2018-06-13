deuspy
======

**This is a work in progress, the README serves as ROADMAP**

Easy to Install. Easy to run. Easy to use. Database server to build
prototypes.

The name "deuspy" comes from a slang term in french which means
"quickly".

What?
-----

Create, read, update:

.. code:: python

    from deuspy.client.sync import Deuspy


    # connect to deuspy at localhost port 9090
    client = Deuspy('http://localhost:9090', 'repl-one')
    # create a new document, return it's unique identifier
    uid = client.create(dict(type='project', title='deuspy', tagline='Prototypes. For. Fun.', popularity=1))
    doc = client.read(uid)
    doc['popularity'] += 31415  # please! use it! start it! and use it again!
    # update document
    client.update(uid, doc)

You can also query and delete stuff:

.. code:: python

    # let's reuse the previous connection
    uid = next(client.query(type='project', title='hoodie'))
    client.delete(uid)  # no more hoodie!

How?
----

Magic!

Why?
----

Because I can and because I need it. I want to present @ pyconfr 2018 a
workshop around `aiohttp <https://aiohttp.readthedocs.io/en/stable/>`__.
I don't want people to feel bad at the very begining of their journey
because they need to choose a database. This. Is. For. Fun. And learn
aiohttp. I don't want myself to have in mind dozen of keywords form 3 or
4 different query languages each with their own dialect to be able to
help my fellow pythonistas achieve the asynchronous dream.

The idea is to have plain simple database server with which you can play
with from aiohttp.
