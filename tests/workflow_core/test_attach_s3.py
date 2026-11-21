from pathlib import Path
import sys
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import attach_s3  # noqa: E402
from workflow_core.attach_s3 import S3Store, require_boto3  # noqa: E402
from workflow_core.attach_store import StoreError  # noqa: E402
from workflow_core.configuration import DependencyUnavailableError  # noqa: E402

SHA = "ab" + "0" * 62
OTHER = "cd" + "1" * 62


class StubError(Exception):
    def __init__(self, code, message=""):
        super().__init__(code)
        self.response = {"Error": {"Code": code, "Message": message}}


class StubClient:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.calls = []
        self.delete_response = {}

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        if kwargs["Key"] not in self.objects:
            raise StubError("404")
        return {}

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        if kwargs["Key"] not in self.objects:
            raise StubError("NoSuchKey")
        body = self.objects[kwargs["Key"]]
        self.body = mock.Mock(read=lambda: body)
        return {"Body": self.body}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        client = self

        class Paginator:
            def paginate(self, **kwargs):
                client.calls.append(("list_objects_v2", kwargs))
                keys = [k for k in client.objects if k.startswith(kwargs.get("Prefix", ""))]
                return [{"Contents": [{"Key": k} for k in keys]}, {}]

        return Paginator()

    def delete_objects(self, **kwargs):
        self.calls.append(("delete_objects", kwargs))
        for item in kwargs["Delete"]["Objects"]:
            self.objects.pop(item["Key"], None)
        return self.delete_response


class S3StoreTests(unittest.TestCase):
    def test_put_uses_prefix_without_acl_and_skips_existing(self):
        stub = StubClient()
        store = S3Store("b", prefix="team/x", client=stub)
        self.assertEqual(store.put(SHA, b"data"), f"ab/{SHA}")
        self.assertEqual(stub.objects, {f"team/x/ab/{SHA}": b"data"})
        for _, kwargs in stub.calls:
            self.assertNotIn("ACL", kwargs)
            self.assertEqual(kwargs["Bucket"], "b")
        stub.calls.clear()
        store.put(SHA, b"data")
        self.assertEqual([name for name, _ in stub.calls], ["head_object"])

    def test_put_rejects_a_bad_sha(self):
        with self.assertRaises(StoreError):
            S3Store("b", client=StubClient()).put("nope", b"x")

    def test_other_head_error_becomes_store_error(self):
        stub = StubClient()
        stub.head_object = mock.Mock(side_effect=StubError("403", "denied"))
        with self.assertRaises(StoreError) as caught:
            S3Store("b", client=stub).put(SHA, b"x")
        self.assertIn("403", str(caught.exception))
        self.assertIn("denied", str(caught.exception))

    def test_get(self):
        stub = StubClient({f"ab/{SHA}": b"data"})
        store = S3Store("b", client=stub)
        self.assertEqual(store.get(f"ab/{SHA}"), b"data")
        stub.body.close.assert_called_once_with()
        with self.assertRaises(StoreError):
            store.get(f"cd/{OTHER}")
        with self.assertRaises(StoreError):
            store.get("../etc/passwd")

    def test_paths_strip_prefix_and_ignore_foreign_keys(self):
        stub = StubClient({f"team/x/ab/{SHA}": b"", "team/x/readme": b"", f"other/cd/{OTHER}": b""})
        self.assertEqual(S3Store("b", prefix="/team/x/", client=stub).paths(), {f"ab/{SHA}"})
        stub = StubClient({f"ab/{SHA}": b"", "junk": b""})
        self.assertEqual(S3Store("b", client=stub).paths(), {f"ab/{SHA}"})

    def test_remove_batches_of_1000(self):
        stub = StubClient()
        store = S3Store("b", client=stub)
        paths = [f"{i:02x}/{i:02x}{j:062x}" for i in range(11) for j in range(200)]
        store.remove(paths)
        deletes = [kw for name, kw in stub.calls if name == "delete_objects"]
        self.assertEqual([len(kw["Delete"]["Objects"]) for kw in deletes], [1000, 1000, 200])
        self.assertTrue(all(kw["Delete"]["Quiet"] is True for kw in deletes))

    def test_remove_raises_on_per_key_errors(self):
        stub = StubClient()
        stub.delete_response = {"Errors": [{"Key": f"p/ab/{SHA}", "Code": "AccessDenied", "Message": "denied"}]}
        with self.assertRaises(StoreError) as caught:
            S3Store("b", prefix="p", client=stub).remove([f"ab/{SHA}"])
        self.assertIn("AccessDenied", str(caught.exception))

    def test_remove_checks_all_paths_before_deleting(self):
        stub = StubClient()
        with self.assertRaises(StoreError):
            S3Store("b", client=stub).remove([f"ab/{SHA}", "bad"])
        self.assertEqual(stub.calls, [])

    def test_push_fetch_and_name(self):
        store = S3Store("b", client=StubClient())
        self.assertIsNone(store.push())
        self.assertIsNone(store.fetch())
        self.assertEqual(store.name, "s3")

    def test_require_boto3_missing(self):
        with mock.patch.dict(sys.modules, {"boto3": None}):
            with self.assertRaises(DependencyUnavailableError) as caught:
                require_boto3()
        self.assertIn("python3 -m pip install boto3", str(caught.exception))

    def test_client_is_built_from_settings(self):
        boto3 = mock.Mock()
        with mock.patch.object(attach_s3, "require_boto3", return_value=boto3):
            S3Store("b", endpoint_url="http://minio:9000", region="us-east-1")
        boto3.client.assert_called_once_with("s3", endpoint_url="http://minio:9000", region_name="us-east-1")


if __name__ == "__main__":
    unittest.main()
