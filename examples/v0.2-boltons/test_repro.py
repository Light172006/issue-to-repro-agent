import pickle
from boltons.dictutils import OMD

def test_omd_pickle_nonempty():
    omd = OMD({'a': 1})
    data = pickle.dumps(omd)
    omd2 = pickle.loads(data)
    assert list(omd2.iteritems()) == list(omd.iteritems()), f"{list(omd2.iteritems())} != {list(omd.iteritems())}"
