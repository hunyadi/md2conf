import sys

if sys.version_info >= (3, 9):

    def removeprefix(string: str, prefix: str) -> str:
        "If the string starts with the prefix, return the string without the prefix; otherwise, return the original string."

        return string.removeprefix(prefix)

else:

    def removeprefix(string: str, prefix: str) -> str:
        "If the string starts with the prefix, return the string without the prefix; otherwise, return the original string."

        if string.startswith(prefix):
            prefix_len = len(prefix)
            return string[prefix_len:]
        else:
            return string
