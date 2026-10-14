"""The barbers chosen by their faces - the picture the owner gave, or the first letter on a colour of
its own - with the name under it; and what the page says, floating over the foot of the screen and
fading after a moment, without leaving the page."""

import pytest
from playwright.sync_api import expect

from obj.barber.courses import PNG_1X1, Courses
from utils.local_time import local_day


def give_photo(barbers, barber_id):
    url = (
        barbers.client.request(
            "PUT", f"{barbers.path}/{barber_id}/photo", persona="owner", json=Courses.encode(PNG_1X1)
        )
        .assert_ok(200)
        .as_dict["photo_url"]
    )
    return url


@pytest.fixture
def two_barbers(barbers):
    with_photo, without = barbers.create_fake_barber(), barbers.create_fake_barber()
    return {**with_photo, "photo_url": give_photo(barbers, with_photo["id"])}, without


def test_a_barber_with_a_picture_shows_it_and_one_without_shows_the_first_letter(two_barbers, signed_in):
    with_photo, without = two_barbers
    signed_in.reload()

    pictured, lettered = signed_in.barber_pill(with_photo["id"]), signed_in.barber_pill(without["id"])

    expect(pictured.locator(".face img")).to_have_attribute("src", with_photo["photo_url"])
    expect(lettered.locator(".face img")).to_have_count(0)
    expect(lettered.locator(".face")).to_have_attribute("data-initial", without["display_name"][0])
    expect(pictured.locator(".face")).to_have_attribute("aria-hidden", "true")


def test_the_face_is_decoration_and_the_name_is_what_is_read_out(two_barbers, signed_in):
    with_photo, without = two_barbers
    signed_in.reload()

    for barber in (with_photo, without):
        pill = signed_in.barber_pill(barber["id"])
        expect(pill).to_have_role("radio")
        expect(pill).to_have_accessible_name(barber["display_name"])
        assert signed_in.text(pill) == barber["display_name"], "the letter is drawn, not written"


def test_the_chosen_barber_is_ringed(two_barbers, signed_in):
    with_photo, without = two_barbers
    signed_in.reload()

    signed_in.choose_barber(without["id"])

    ringed = (
        signed_in.barber_pill(without["id"]).locator(".face").evaluate("e => getComputedStyle(e).boxShadow")
    )
    plain = (
        signed_in.barber_pill(with_photo["id"])
        .locator(".face")
        .evaluate("e => getComputedStyle(e).boxShadow")
    )
    assert ringed != plain and "5px" in ringed


def test_the_owner_gives_a_barber_a_picture_and_takes_it_away(barbers, owner_screen):
    barber = barbers.create_fake_barber()
    owner = owner_screen().select_barber(barber["id"])
    expect(owner.by("remove-barber-photo")).to_be_hidden()

    owner.by("barber-photo-file").set_input_files(
        files=[{"name": "b.png", "mimeType": "image/png", "buffer": PNG_1X1}]
    )
    owner.settled()

    stored = next(b for b in barbers.find(persona="owner").assert_ok(200).content if b["id"] == barber["id"])
    assert stored["photo_url"] is not None
    expect(owner.by("barber-photo").locator("img")).to_have_attribute("src", stored["photo_url"])
    expect(owner.barber_pill(barber["id"]).locator(".face img")).to_have_count(1)
    owner.by("remove-barber-photo").click()
    owner.settled()
    stored = next(b for b in barbers.find(persona="owner").assert_ok(200).content if b["id"] == barber["id"])
    assert stored["photo_url"] is None
    expect(owner.by("barber-photo").locator("img")).to_have_count(0)


def test_a_file_that_is_not_a_picture_is_refused_in_words(barbers, owner_screen):
    barber = barbers.create_fake_barber()
    owner = owner_screen().select_barber(barber["id"])

    owner.by("barber-photo-file").set_input_files(
        files=[{"name": "b.png", "mimeType": "image/png", "buffer": b"<script>"}]
    )
    owner.settled()

    assert "JPEG" in owner.text(owner.message())


def test_what_the_page_says_floats_over_the_foot_of_the_screen_and_fades_but_stays(
    signed_in, ui_barber, ui_haircut, shop_tz
):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 4)).pick("12:00").book()

    signed_in.cancel("12:00")

    message = signed_in.message()
    assert message.evaluate("e => getComputedStyle(e).position") == "fixed"
    assert message.evaluate("e => getComputedStyle(e).opacity") == "1"
    expect(message).to_have_class("faded", timeout=6000)
    assert message.evaluate("e => getComputedStyle(e).opacity") == "0"
    assert "בוטל" in signed_in.text(message), "faded, not removed: the words are still in the page"


def test_the_empty_message_is_still_there_for_a_screen_reader(signed_in):
    shop = signed_in
    expect(shop.message()).to_have_text("")

    expect(shop.page.get_by_role("status")).to_have_count(1)
    assert shop.message().evaluate("e => getComputedStyle(e).display") != "none"
