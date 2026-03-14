"""Tests for rebuild_registry.helpers — HDF5 attribute reading utilities."""

import json

import h5py
import numpy as np

from rebuild_registry.helpers import attr, attr_list, shape_str, all_attrs_json


class TestAttr:
    def test_reads_string(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["name"] = "hello"
        with h5py.File(str(p), "r") as f:
            assert attr(f, "name") == "hello"

    def test_decodes_bytes(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["name"] = np.bytes_("hello")
        with h5py.File(str(p), "r") as f:
            assert attr(f, "name") == "hello"

    def test_converts_numpy_scalar(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["val"] = np.int64(42)
        with h5py.File(str(p), "r") as f:
            result = attr(f, "val")
            assert result == 42
            assert isinstance(result, int)

    def test_returns_default_for_missing(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            pass
        with h5py.File(str(p), "r") as f:
            assert attr(f, "missing") is None
            assert attr(f, "missing", "fallback") == "fallback"


class TestAttrList:
    def test_reads_string_array(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.attrs["tags"] = np.array(["a", "b"], dtype="S")
        with h5py.File(str(p), "r") as f:
            result = json.loads(attr_list(f, "tags"))
            assert result == ["a", "b"]

    def test_returns_none_for_missing(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            pass
        with h5py.File(str(p), "r") as f:
            assert attr_list(f, "nope") is None


class TestShapeStr:
    def test_3d_shape(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            f.create_dataset("vol", shape=(10, 256, 256), dtype="int16")
        with h5py.File(str(p), "r") as f:
            assert shape_str(f["vol"]) == "(10, 256, 256)"


class TestAllAttrsJson:
    def test_serializes_mixed_attrs(self, tmp_path):
        p = tmp_path / "t.h5"
        with h5py.File(str(p), "w") as f:
            grp = f.create_group("g")
            grp.attrs["fev1"] = 2.1
            grp.attrs["test_date"] = "2026-03-12"
        with h5py.File(str(p), "r") as f:
            data = json.loads(all_attrs_json(f["g"]))
            assert abs(data["fev1"] - 2.1) < 0.01
            assert data["test_date"] == "2026-03-12"
