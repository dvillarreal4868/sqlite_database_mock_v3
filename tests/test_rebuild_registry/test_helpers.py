"""
tests/test_rebuild_registry/test_helpers.py

PURPOSE:
    Tests for the HDF5 attribute reading utilities in helpers.py.

    These verify that our helper functions correctly convert the various
    data types that h5py returns (bytes, numpy scalars, numpy arrays)
    into plain Python types that SQLite can handle.
"""

import json

import h5py
import numpy as np

from rebuild_registry.helpers import attr, attr_list, shape_str, all_attrs_json


class TestAttr:
    """Tests for the attr() function — reads single scalar attributes."""

    def test_reads_string(self, tmp_path):
        """A plain Python string should come back unchanged."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["name"] = "hello"
        with h5py.File(str(p), "r") as f:
            assert attr(f, "name") == "hello"

    def test_decodes_bytes(self, tmp_path):
        """HDF5 sometimes stores strings as bytes — we should decode them."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["name"] = np.bytes_("hello")  # Store as raw bytes
        with h5py.File(str(p), "r") as f:
            assert attr(f, "name") == "hello"  # Should come back as str

    def test_converts_numpy_scalar(self, tmp_path):
        """numpy.int64 should be converted to plain Python int."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["val"] = np.int64(42)
        with h5py.File(str(p), "r") as f:
            result = attr(f, "val")
            assert result == 42
            assert isinstance(result, int)  # Must be Python int, not numpy.int64

    def test_returns_default_for_missing(self, tmp_path):
        """Missing attributes should return None (or a custom default)."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            pass  # Empty file — no attributes
        with h5py.File(str(p), "r") as f:
            assert attr(f, "missing") is None           # Default is None
            assert attr(f, "missing", "fallback") == "fallback"  # Custom default


class TestAttrList:
    """Tests for attr_list() — reads list attributes and returns JSON strings."""

    def test_reads_string_array(self, tmp_path):
        """A numpy array of strings should become a JSON list of strings."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["tags"] = np.array(["a", "b"], dtype="S")
        with h5py.File(str(p), "r") as f:
            result = json.loads(attr_list(f, "tags"))
            assert result == ["a", "b"]

    def test_returns_none_for_missing(self, tmp_path):
        """Missing list attributes should return None (not an empty list)."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            pass
        with h5py.File(str(p), "r") as f:
            assert attr_list(f, "nope") is None


class TestShapeStr:
    """Tests for shape_str() — converts dataset shapes to strings."""

    def test_3d_shape(self, tmp_path):
        """A 3D dataset's shape should render like '(10, 256, 256)'."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.create_dataset("vol", shape=(10, 256, 256), dtype="int16")
        with h5py.File(str(p), "r") as f:
            assert shape_str(f["vol"]) == "(10, 256, 256)"


class TestAllAttrsJson:
    """Tests for all_attrs_json() — dumps all group attributes to JSON."""

    def test_serializes_mixed_attrs(self, tmp_path):
        """A group with float + string attributes should serialize to valid JSON."""
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            grp = f.create_group("g")
            grp.attrs["fev1"] = 2.1
            grp.attrs["test_date"] = "2026-03-12"
        with h5py.File(str(p), "r") as f:
            data = json.loads(all_attrs_json(f["g"]))
            assert abs(data["fev1"] - 2.1) < 0.01
            assert data["test_date"] == "2026-03-12"
