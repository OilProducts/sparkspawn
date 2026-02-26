import threading

from attractor.engine.context import Context


class TestContextLocking:
    def test_get_can_proceed_while_another_reader_holds_lock(self):
        context = Context(values={"key": "value"})
        read_completed = threading.Event()

        with context.lock.read_lock():
            thread = threading.Thread(
                target=lambda: (context.get("key"), read_completed.set()),
                daemon=True,
            )
            thread.start()
            assert read_completed.wait(timeout=1.0)

        thread.join(timeout=1.0)
        assert not thread.is_alive()

    def test_set_waits_until_reader_releases_lock(self):
        context = Context(values={"key": "value"})
        write_completed = threading.Event()

        with context.lock.read_lock():
            thread = threading.Thread(
                target=lambda: (context.set("key", "updated"), write_completed.set()),
                daemon=True,
            )
            thread.start()
            assert not write_completed.wait(timeout=0.1)

        assert write_completed.wait(timeout=1.0)
        thread.join(timeout=1.0)
        assert context.get("key") == "updated"

    def test_get_waits_until_writer_releases_lock(self):
        context = Context(values={"key": "value"})
        read_completed = threading.Event()

        with context.lock.write_lock():
            thread = threading.Thread(
                target=lambda: (context.get("key"), read_completed.set()),
                daemon=True,
            )
            thread.start()
            assert not read_completed.wait(timeout=0.1)

        assert read_completed.wait(timeout=1.0)
        thread.join(timeout=1.0)


class TestContextHelpers:
    def test_set_get_and_get_string(self):
        context = Context()
        context.set("name", "sparkspawn")
        context.set("attempts", 3)
        context.set("empty", None)

        assert context.get("name") == "sparkspawn"
        assert context.get("missing") is None
        assert context.get("missing", "fallback") == "fallback"
        assert context.get_string("name") == "sparkspawn"
        assert context.get_string("attempts") == "3"
        assert context.get_string("empty", "none") == "none"
        assert context.get_string("missing", "fallback") == "fallback"

    def test_append_log_and_clone_isolation(self):
        context = Context(values={"status": "ready"})
        context.append_log("first")

        cloned = context.clone()
        cloned.set("status", "running")
        cloned.append_log("second")

        assert context.get("status") == "ready"
        assert context.logs == ["first"]
        assert cloned.logs == ["first", "second"]

    def test_snapshot_returns_copy(self):
        context = Context(values={"a": 1})

        snapshot = context.snapshot()
        snapshot["a"] = 2
        snapshot["b"] = 3

        assert context.get("a") == 1
        assert context.get("b", None) is None

    def test_apply_updates_merges_values(self):
        context = Context(values={"a": 1})

        context.apply_updates({"a": 2, "b": "three"})

        assert context.get("a") == 2
        assert context.get("b") == "three"
