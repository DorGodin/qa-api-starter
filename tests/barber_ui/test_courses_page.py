"""The courses tab: a card each, a picture over its words, a button that opens WhatsApp. And the
owner's panel that keeps them, the picture included."""

import json
import secrets

import pytest
from playwright.sync_api import expect

from obj.barber.courses import PNG_1X1

WHATSAPP = "https://wa.me/972500000000?text=%D7%A9%D7%9C%D7%95%D7%9D"


def with_whatsapp(page):
    def patch(route):
        response = route.fetch()
        body = response.json()
        for course in body["content"]:
            course["whatsapp_url"] = WHATSAPP
        route.fulfill(response=response, body=json.dumps(body))

    page.route("**/courses", patch)


@pytest.fixture
def title():
    return f"קורס {secrets.token_hex(3)}"


def test_a_customer_sees_a_course_as_a_card_with_its_line(courses, signed_in, title):
    courses.create_fake_course(title=title, subtitle="8 מפגשים", starts_on="2027-11-02", price_minor=320000)
    signed_in.reload()

    card = signed_in.course_card(title)

    expect(card).to_have_count(1)
    line = signed_in.text(card.get_by_test_id("course-line"))
    assert "8 מפגשים" in line and "מתחיל ב" in line and "3,200" in line and ".00" not in line, line


def test_a_course_with_no_date_or_price_says_only_what_it_has(courses, signed_in, title):
    courses.create_fake_course(title=title, subtitle="סדנה", starts_on=None, price_minor=None)
    signed_in.reload()

    line = signed_in.text(signed_in.course_card(title).get_by_test_id("course-line"))

    assert line == "סדנה"


def test_a_free_course_says_free(courses, signed_in, title):
    courses.create_fake_course(title=title, subtitle="", starts_on=None, price_minor=0)
    signed_in.reload()

    assert "חינם" in signed_in.text(signed_in.course_card(title).get_by_test_id("course-line"))


def test_the_picture_is_over_the_words(courses, signed_in, title):
    course = courses.create_fake_course(title=title)
    courses.set_image(course["id"], PNG_1X1).assert_ok(200)
    signed_in.reload()

    image = signed_in.course_card(title).locator("img")

    expect(image).to_have_attribute("src", course_image_url(courses, course))


def course_image_url(courses, course):
    return next(c for c in courses.listing("owner") if c["id"] == course["id"])["image_url"]


def test_the_button_opens_the_shops_whatsapp_in_a_new_tab(courses, signed_in, title):
    courses.create_fake_course(title=title)
    with_whatsapp(signed_in.page)
    signed_in.reload()

    button = signed_in.course_card(title).get_by_test_id("course-whatsapp")

    expect(button).to_have_text("לפרטים")
    expect(button).to_have_attribute("href", WHATSAPP)
    expect(button).to_have_attribute("target", "_blank")
    assert "noopener" in button.get_attribute("rel")


def test_a_withdrawn_course_is_not_shown(courses, signed_in, title):
    course = courses.create_fake_course(title=title)
    courses.withdraw(course["id"])
    signed_in.reload()

    expect(signed_in.course_card(title)).to_have_count(0)


def test_a_title_that_looks_like_a_tag_is_written_as_text(courses, signed_in):
    hostile = '<img src=x onerror="document.title=1">'
    courses.create_fake_course(title=hostile)
    signed_in.reload()

    expect(signed_in.course_card(hostile)).to_have_count(1)
    assert signed_in.page.title() != "1"


def test_with_no_courses_the_tab_says_so(signed_in):
    signed_in.page.route(
        "**/courses",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"total":0,"content":[]}'
        ),
    )
    signed_in.reload()
    signed_in.show_tab("courses")

    expect(signed_in.by("no-courses")).to_be_visible()
    expect(signed_in.by("course")).to_have_count(0)


def test_the_owner_has_no_customers_courses_panel_but_a_panel_of_his_own(owner_screen):
    owner = owner_screen()

    expect(owner.by("courses-panel")).to_be_hidden()
    expect(owner.by("courses-admin-panel")).to_be_visible()


def test_the_owner_adds_a_course_from_the_panel(owner_screen, courses, new_customer, title):
    owner = owner_screen()

    owner.add_course(title, "8 מפגשים", "2027-11-02", "3200")

    assert "נוסף" in owner.text(owner.message())
    made = next(c for c in courses.listing("owner") if c["title"] == title)
    courses.withdraw(made["id"])
    assert (made["subtitle"], made["starts_on"], made["price_minor"]) == ("8 מפגשים", "2027-11-02", 320000)


def test_a_new_course_needs_a_name(owner_screen, courses):
    owner = owner_screen()
    before = len(courses.listing("owner"))

    owner.add_course("", "x")

    assert "שם" in owner.text(owner.message())
    assert len(courses.listing("owner")) == before


def test_a_price_that_is_not_a_number_is_explained_and_nothing_is_made(owner_screen, courses, title):
    owner = owner_screen()
    before = len(courses.listing("owner"))

    owner.add_course(title, "", "", "abc")

    assert "מחיר" in owner.text(owner.message())
    assert len(courses.listing("owner")) == before


def test_the_owner_edits_and_withdraws_a_course(courses, owner_screen, new_customer, title):
    course = courses.create_fake_course(title=title, price_minor=100000)
    owner = owner_screen()
    editor = owner.course_editor(course["id"])

    editor.get_by_test_id("course-edit-price").fill("450")
    editor.get_by_test_id("course-edit-active").uncheck()
    owner.save_course(course["id"])

    saved = next(c for c in courses.listing("owner") if c["id"] == course["id"])
    assert (saved["price_minor"], saved["active"]) == (45000, False)
    assert course["id"] not in [c["id"] for c in courses.listing(new_customer())]


def test_the_owner_uploads_and_removes_a_picture(courses, owner_screen, title):
    course = courses.create_fake_course(title=title)
    owner = owner_screen()
    editor = owner.course_editor(course["id"])

    editor.get_by_test_id("course-image").set_input_files(
        files=[{"name": "c.png", "mimeType": "image/png", "buffer": PNG_1X1}]
    )
    owner.settled()

    assert course_image_url(courses, course) is not None
    expect(owner.course_editor(course["id"]).locator("img")).to_have_count(1)
    owner.course_editor(course["id"]).get_by_test_id("remove-course-image").click()
    owner.settled()
    assert course_image_url(courses, course) is None


def test_a_file_that_is_not_a_picture_is_refused_in_words(courses, owner_screen, title):
    course = courses.create_fake_course(title=title)
    owner = owner_screen()

    owner.course_editor(course["id"]).get_by_test_id("course-image").set_input_files(
        files=[{"name": "c.png", "mimeType": "image/png", "buffer": b"<script>1</script>"}]
    )
    owner.settled()

    assert "JPEG" in owner.text(owner.message())
    assert course_image_url(courses, course) is None
