import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")


@pytest.fixture
def catalogue(items):
    return [items.create_fake_item(name=f"Widget {i}", price=10.0 + i) for i in range(7)]


def test_total_counts_every_match_not_just_the_page(items, catalogue):
    page = items.find(params={"limit": 3}).assert_ok(200).as_dict

    assert page["total"] == 7, "total must describe the result set, not the page"
    assert len(page["content"]) == 3


def test_paging_walks_the_whole_set_without_gaps_or_repeats(items, catalogue):
    seen = []
    for offset in (0, 3, 6):
        seen += [
            row["id"] for row in items.find(params={"limit": 3, "offset": offset}).assert_ok(200).content
        ]

    assert len(seen) == 7
    assert len(set(seen)) == 7, "a row appeared on two pages"
    assert set(seen) == {item["id"] for item in catalogue}


def test_an_offset_past_the_end_is_empty_not_an_error(items, catalogue):
    page = items.find(params={"offset": 999}).assert_ok(200).as_dict

    assert page["content"] == []
    assert page["total"] == 7, "total must not depend on the offset"


@pytest.mark.parametrize("limit, expected", [(1, 1), (7, 7), (200, 7)], ids=["one", "exact", "over"])
def test_limit_is_respected_up_to_the_size_of_the_set(items, catalogue, limit, expected):
    assert len(items.find(params={"limit": limit}).assert_ok(200).content) == expected


def test_filters_combine_rather_than_replace_each_other(items, catalogue):
    items.create_fake_item(name="Widget hidden", active=False)

    both = items.find(params={"name": "widget", "active": True}).assert_ok(200).as_dict
    assert both["total"] == 7, "the inactive Widget must not match an active-only filter"

    inactive = items.find(params={"active": False}).assert_ok(200).as_dict
    assert inactive["total"] == 1


def test_a_filter_matching_nothing_returns_an_empty_page(items, catalogue):
    page = items.find(params={"name": "no-such-product"}).assert_ok(200).as_dict

    assert page == {"total": 0, "content": []}


def test_the_name_filter_ignores_case(items, catalogue):
    for query in ("widget", "WIDGET", "WiDgEt"):
        assert items.find(params={"name": query}).assert_ok(200).as_dict["total"] == 7
