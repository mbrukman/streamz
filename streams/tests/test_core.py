from operator import add
from time import time

import pytest

from distributed.utils_test import inc, double, gen_test
from distributed.utils import tmpfile
from tornado import gen
from tornado.queues import Queue

from ..core import *
from ..sources import *


def test_basic():
    source = Stream()
    b1 = map(inc, source)
    b2 = map(double, source)

    c = scan(add, b1, start=0)

    Lc = list()
    sink_c = Sink(c, Lc.append)

    Lb = list()
    sink_b = Sink(b2, Lb.append)

    for i in range(4):
        source.emit(i)

    assert Lc == [1, 3, 6, 10]
    assert Lb == [0, 2, 4, 6]


def test_filter():
    source = Stream()
    a = filter(lambda x: x % 2 == 0, source)

    L = sink_to_list(a)

    for i in range(10):
        source.emit(i)

    assert L == [0, 2, 4, 6, 8]


def test_partition():
    source = Stream()
    a = partition(2, source)

    L = []
    sink = Sink(a, L.append)

    for i in range(10):
        source.emit(i)

    assert L == [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]


def test_sliding_window():
    source = Stream()
    a = sliding_window(2, source)

    L = []
    sink = Sink(a, L.append)

    for i in range(10):
        source.emit(i)

    assert L == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5),
                 (5, 6), (6, 7), (7, 8), (8, 9)]


@gen_test()
def test_backpressure():
    loop = IOLoop.current()
    source = Stream()
    a = map(inc, source)
    c = scan(add, a, start=0)

    q = Queue(maxsize=2)

    @gen.coroutine
    def read_from_q():
        while True:
            result = yield q.get()
            yield gen.sleep(0.1)

    loop.add_callback(read_from_q)

    sink = Sink(c, q.put)

    start = time()
    for i in range(5):
        yield source.emit(i)
    end = time()

    assert end - start >= 0.2


@gen_test()
def test_timed_window():
    source = Stream()
    a = timed_window(0.01, source)

    L = sink_to_list(a)

    for i in range(10):
        yield source.emit(i)
        yield gen.sleep(0.004)

    yield gen.sleep(a.interval)
    assert L
    assert sum(L, []) == list(range(10))
    assert all(len(x) <= 3 for x in L)
    assert any(len(x) >= 2 for x in L)

    yield gen.sleep(0.1)
    assert not L[-1]


@gen_test()
def test_timed_window_backpressure():
    loop = IOLoop.current()
    source = Stream()
    a = timed_window(0.01, source)

    q = Queue(maxsize=1)
    sink = Sink(a, q.put)

    @gen.coroutine
    def read_from_q():
        while True:
            result = yield q.get()
            yield gen.sleep(0.1)

    loop.add_callback(read_from_q)

    start = time()
    for i in range(5):
        yield source.emit(i)
        yield gen.sleep(0.01)
    stop = time()

    assert stop - start > 0.2


def test_sink_to_file():
    with tmpfile() as fn:
        source = Stream()
        with sink_to_file(fn, source) as f:
            source.emit('a')
            source.emit('b')

        with open(fn) as f:
            data = f.read()

        assert data == 'a\nb\n'

@gen_test()
def test_counter():
    source = Counter(interval=0.01)
    L = sink_to_list(source)
    yield gen.sleep(0.1)

    assert L


@gen_test()
def test_rate_limit():
    source = Stream()
    a = rate_limit(0.05, source)
    L = sink_to_list(a)

    start = time()
    for i in range(5):
        yield source.emit(i)
    stop = time()
    assert stop - start > 0.1
    assert len(L) == 5


@gen_test()
def test_delay():
    source = Stream()
    a = delay(0.02, source)
    L = sink_to_list(a)

    for i in range(5):
        yield source.emit(i)

    assert not L

    yield gen.sleep(0.04)

    assert len(L) < 5

    yield gen.sleep(0.1)

    assert len(L) == 5


@gen_test()
def test_buffer():
    source = Stream()
    a = map(inc, source)
    b = buffer(10, a)
    c = map(inc, b)
    d = rate_limit(0.05, c)

    L = sink_to_list(d)

    start = time()
    for i in range(10):
        yield source.emit(i)
    stop = time()

    assert stop - start < 0.01
    assert not L

    start = time()
    for i in range(5):
        yield source.emit(i)
    stop = time()

    assert L
    assert stop - start > 0.04
