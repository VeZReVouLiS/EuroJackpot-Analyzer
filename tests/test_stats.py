from app import stats


def D(date, main, euro):
    return {"date": date, "main": main, "euro": euro, "source": "t"}


HIST = [
    D("2012-03-23", [1, 2, 3, 4, 5], [1, 2]),
    D("2012-03-30", [1, 2, 3, 4, 6], [1, 3]),
    D("2012-04-06", [7, 8, 9, 10, 11], [8, 2]),
    D("2012-04-13", [1, 8, 20, 30, 40], [3, 4]),
]


def test_counts_and_gaps_main():
    s = stats.compute(HIST)
    m = {x["n"]: x for x in s["main"]}
    assert s["n_draws"] == 4
    assert m[1]["count"] == 3 and m[1]["gap"] == 0 and m[1]["max_gap"] == 1
    assert m[2]["count"] == 2 and m[2]["gap"] == 2
    assert m[50]["count"] == 0 and m[50]["gap"] == 4       # never seen: gap = all draws
    assert m[8]["count"] == 2 and m[8]["gap"] == 0 and m[8]["last_seen"] == "2012-04-13"


def test_euro_eligibility_by_era():
    # 11 and 12 did not exist in 2012 -> not "overdue", not counted as eligible
    s = stats.compute(HIST)
    e = {x["n"]: x for x in s["euro"]}
    assert e[11]["eligible"] == 0 and e[11]["gap"] is None
    assert e[9]["gap"] is None                       # 9 only exists from 2014-10
    assert e[8]["eligible"] == 4 and e[8]["count"] == 1


def test_euro_number_introduced_later_counts_gap_from_introduction():
    hist = HIST + [
        D("2014-10-10", [1, 2, 3, 4, 5], [1, 2]),
        D("2014-10-17", [1, 2, 3, 4, 5], [1, 2]),
    ]
    s = stats.compute(hist)
    e = {x["n"]: x for x in s["euro"]}
    assert e[9]["eligible"] == 2 and e[9]["gap"] == 2    # only draws since it exists
    assert e[10]["gap"] == 2


def test_window_filters_counts_but_not_gap():
    s = stats.compute(HIST, since="2012-04-06")
    m = {x["n"]: x for x in s["main"]}
    assert s["n_draws"] == 2 and m[1]["count"] == 1
    assert m[2]["gap"] == 2                         # gap still from full history


def test_distributions_and_pairs():
    s = stats.compute(HIST)
    assert sum(x["count"] for x in s["odd_even"]) == 4
    assert sum(x["count"] for x in s["low_high"]) == 4
    assert s["top_pairs"][0]["count"] >= 2
    assert s["last_draw"]["date"] == "2012-04-13"


def test_ranking_lists():
    s = stats.compute(HIST)
    assert s["ranking"]["main"]["hot"][0] == 1
    assert 50 in s["ranking"]["main"]["overdue"][:10]
    assert s["ranking"]["euro"]["overdue"], "euro ranking should only contain active numbers"
