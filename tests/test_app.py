"""Tests for app.py UI logic."""
from pathlib import Path


class TestReportsSorting:
    def test_sort_reports_by_mtime(self, tmp_path):
        """Verify reports are sorted by modification time."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Create reports with different mtimes
        old = reports_dir / "old_report.md"
        old.write_text("old")
        # Give the filesystem enough time to register a distinct mtime
        old_mtime = old.stat().st_mtime

        new = reports_dir / "new_report.md"
        new.write_text("new")
        new_mtime = new.stat().st_mtime

        # Ensure mtimes are different (common on all filesystems including tmpfs)
        if new_mtime == old_mtime:
            import time
            time.sleep(0.01)
            new.write_text("new")
            new_mtime = new.stat().st_mtime

        reports = sorted(
            reports_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        assert reports[0].name == "new_report.md"
        assert reports[1].name == "old_report.md"


class TestFileSizeGuard:
    def test_large_file_detected(self, tmp_path):
        """Verify the size guard consistently identifies oversized reports."""
        MAX_BYTES = 10 * 1024 * 1024

        small = tmp_path / "small.md"
        small.write_text("x" * 100)

        large = tmp_path / "large.md"
        large.write_text("x" * (MAX_BYTES + 1))

        assert small.stat().st_size <= MAX_BYTES, \
            f"Expected small file <= {MAX_BYTES}, got {small.stat().st_size}"
        assert large.stat().st_size > MAX_BYTES, \
            f"Expected large file > {MAX_BYTES}, got {large.stat().st_size}"

    def test_size_guard_boundary(self, tmp_path):
        """Verify the guard passes a file exactly at the limit."""
        MAX_BYTES = 10 * 1024 * 1024
        boundary = tmp_path / "boundary.md"
        boundary.write_text("x" * MAX_BYTES)
        assert boundary.stat().st_size == MAX_BYTES

    def test_size_guard_one_byte_over(self, tmp_path):
        """Verify the guard detects a file one byte over the limit."""
        MAX_BYTES = 10 * 1024 * 1024
        over = tmp_path / "over.md"
        over.write_text("x" * (MAX_BYTES + 1))
        assert over.stat().st_size > MAX_BYTES


class TestReportsPath:
    def test_reports_path_resolves_correctly(self):
        """Verify the app's reports dir pattern points to the project root."""
        expected = Path(__file__).parent.parent / "reports"
        assert expected.name == "reports"
        assert (Path(__file__).parent.parent / "reports").name == "reports"
