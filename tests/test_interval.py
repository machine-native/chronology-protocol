from ctp.interval import Interval,consensus,order

def test_byzantine_outlier():
    xs=[Interval(90,110),Interval(92,112),Interval(89,109),Interval(5000,5010)]
    r=consensus(xs,1)
    assert r["verdict"]=="CONSENSUS"
    assert r["q"]==3
    assert r["interval"]==Interval(92,109)

def test_order():
    assert order(Interval(0,10),Interval(11,20))=="A_BEFORE_B"
    assert order(Interval(0,10),Interval(10,20))=="ORDER_INDETERMINATE"

def test_exact_integer_regions():
    xs=[Interval(0,5),Interval(3,8),Interval(4,6),Interval(100,110)]
    r=consensus(xs,1)
    assert r["verdict"]=="CONSENSUS"
    assert r["interval"]==Interval(4,5)

def test_disconnected_quorum_is_conflict():
    # q=3: one quorum around 0 and a different quorum around 100.
    xs=[Interval(0,1),Interval(0,1),Interval(0,1),Interval(100,101),Interval(100,101),Interval(100,101),Interval(-1000,1000)]
    # f=2 -> N=7, q=5, so this does not reach quorum anywhere.
    r=consensus(xs,2)
    assert r["verdict"]=="TIME_CONFLICT"
