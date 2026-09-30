import threading
import time

from utils.concurrency import at_once


def test_results_come_back_in_the_order_the_calls_were_given():
    assert at_once([lambda i=i: i for i in range(6)]) == [0, 1, 2, 3, 4, 5]


def test_every_call_is_in_flight_at_the_same_time():
    inside, peak, lock = [0], [0], threading.Lock()

    def call():
        with lock:
            inside[0] += 1
            peak[0] = max(peak[0], inside[0])
        time.sleep(0.05)
        with lock:
            inside[0] -= 1

    at_once([call] * 8)

    assert peak[0] == 8, f"only {peak[0]} of 8 calls overlapped - that is not a race"


def test_no_calls_is_no_work():
    assert at_once([]) == []
