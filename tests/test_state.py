import pytest

from spirit_computer_use.state import Bounds, Snapshot, Snapshots, Window


def window(hwnd=10, pid=20, created=1.0):
    return Window(id=hwnd, pid=pid, created=created, app="test.exe", title="Test")


def test_negative_monitor_coordinates_are_supported():
    assert Bounds(-1920, -100, 0, 980).point(100, 100) == (-1820, 0)


@pytest.mark.parametrize("point", [(-1, 0), (100, 0), (0, 80), (True, 0), (1.5, 2)])
def test_out_of_bounds_or_noninteger_points_rejected(point):
    with pytest.raises(ValueError):
        Bounds(0, 0, 100, 80).point(*point)


def test_new_observation_invalidates_old_element_indices():
    states = Snapshots()
    old = states.add(Snapshot(window(), Bounds(0, 0, 100, 100)))
    states.add(Snapshot(window(), Bounds(0, 0, 100, 100)))
    with pytest.raises(ValueError, match="missing"):
        states.require(old, window(), Bounds(0, 0, 100, 100))


def test_moved_window_and_reused_handle_rejected():
    states = Snapshots()
    key = states.add(Snapshot(window(), Bounds(0, 0, 100, 100)))
    with pytest.raises(ValueError, match="moved"):
        states.require(key, window(), Bounds(1, 0, 101, 100))
    with pytest.raises(ValueError, match="different"):
        states.require(key, window(created=2.0), Bounds(0, 0, 100, 100))


def test_expired_state_rejected():
    states = Snapshots()
    key = states.add(Snapshot(window(), Bounds(0, 0, 100, 100), created=0))
    with pytest.raises(ValueError, match="expired"):
        states.require(key, window(), Bounds(0, 0, 100, 100))
