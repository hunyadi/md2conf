import unittest

from md2conf.__main__ import resolve_synchronize_if
from md2conf.environment import ArgumentError
from md2conf.options import DocumentOptions
from md2conf.types import SynchronizableDocument


def mock_sync_if(props: SynchronizableDocument, options: DocumentOptions) -> bool:
    return True


not_a_callable = "string"


class TestResolveSynchronizeIf(unittest.TestCase):
    def test_resolve_valid(self) -> None:
        # Test resolving a valid callable from this module
        # Note: __name__ is 'tests.test_resolve_synchronize_if' or similar
        sync_if = resolve_synchronize_if(f"{__name__}:mock_sync_if")
        self.assertEqual(sync_if, mock_sync_if)

    def test_invalid_format(self) -> None:
        with self.assertRaises(ArgumentError) as cm:
            resolve_synchronize_if("invalid_format")
        self.assertIn("invalid synchronize-if format", str(cm.exception))

    def test_module_not_found(self) -> None:
        with self.assertRaises(ArgumentError) as cm:
            resolve_synchronize_if("non_existent_module:func")
        self.assertIn("could not import module", str(cm.exception))

    def test_attribute_not_found(self) -> None:
        with self.assertRaises(ArgumentError) as cm:
            resolve_synchronize_if(f"{__name__}:non_existent_func")
        self.assertIn("has no attribute 'non_existent_func'", str(cm.exception))

    def test_not_a_callable(self) -> None:
        with self.assertRaises(ArgumentError) as cm:
            resolve_synchronize_if(f"{__name__}:not_a_callable")
        self.assertIn("is not a callable", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
