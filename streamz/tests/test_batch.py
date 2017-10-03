import pytest
import toolz

from streamz.batch import StreamingBatch, Streaming
from streamz.utils_test import inc


def test_core():
    a = StreamingBatch()
    b = a.pluck('x').map(inc)
    c = b.sum()
    L = c.stream.sink_to_list()

    a.emit([{'x': i, 'y': 0} for i in range(4)])

    assert isinstance(b, StreamingBatch)
    assert isinstance(c, Streaming)
    assert L == [1 + 2 + 3 + 4]


def test_dataframes():
    pd = pytest.importorskip('pandas')
    from streamz.dataframe import StreamingDataFrame
    data = [{'x': i, 'y': 2 * i} for i in range(10)]

    s = StreamingBatch(example=[{'x': 0, 'y': 0}])
    sdf = s.map(lambda d: toolz.assoc(d, 'z', d['x'] + d['y'])).to_dataframe()

    assert isinstance(sdf, StreamingDataFrame)

    L = sdf.stream.sink_to_list()

    for batch in toolz.partition_all(3, data):
        s.emit(batch)

    result = pd.concat(L)
    assert result.z.tolist() == [3 * i for i in range(10)]


def test_filter():
    a = StreamingBatch()
    L = a.filter(lambda x: x % 2 == 0).to_stream().sink_to_list()

    a.emit([1, 2, 3, 4])
    a.emit([5, 6])

    assert L == [2, 4, 6]
