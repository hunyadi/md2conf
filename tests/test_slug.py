"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from collections.abc import Callable

from md2conf.slug import title_to_ascii_slug, title_to_common_slug, title_to_identifier, title_to_slug
from tests.utility import TypedTestCase

currency_symbols = [
    "$",  # Dollar
    "¢",  # Cent
    "£",  # Pound
    "¤",  # Generic currency sign
    "¥",  # Yen / Yuan
    "֏",  # Armenian dram
    "؋",  # Afghani
    "৲",  # Bengali rupee mark
    "৳",  # Bengali taka
    "૱",  # Gujarati rupee sign
    "௹",  # Tamil rupee sign
    "฿",  # Thai baht
    "៛",  # Khmer riel
    "₠",  # Euro-currency sign
    "₡",  # Colon
    "₢",  # Cruzeiro
    "₣",  # French franc
    "₤",  # Lira
    "₥",  # Mill
    "₦",  # Naira
    "₧",  # Peseta
    "₨",  # Rupee
    "₩",  # Won
    "₪",  # New shekel
    "₫",  # Dong
    "€",  # Euro
    "₭",  # Kip
    "₮",  # Tugrik
    "₯",  # Drachma
    "₰",  # German penny
    "₱",  # Peso
    "₲",  # Guarani
    "₳",  # Austral
    "₴",  # Hryvnia
    "₵",  # Cedi
    "₶",  # Livre tournois
    "₷",  # Spesmilo
    "₸",  # Tenge
    "₹",  # Indian rupee
    "₺",  # Turkish lira
    "₻",  # Nordic mark
    "₼",  # Azerbaijani manat
    "₽",  # Russian ruble
    "₾",  # Georgian lari
    "₿",  # Bitcoin
    "꠸",  # Syloti rupee
    "﷼",  # Rial
]


class TestSlug(TypedTestCase):
    def test_title_to_identifier(self) -> None:
        self.assertEqual(title_to_identifier("This is  a Heading  "), "this-is-a-heading")
        self.assertEqual(title_to_identifier("What's New in v2.0?"), "whats-new-in-v20")
        self.assertEqual(title_to_identifier("C++ & C# Comparison"), "c-c-comparison")
        self.assertEqual(title_to_identifier("Hello -- World!!"), "hello----world")
        self.assertEqual(title_to_identifier("árvíztűrő tükörfúrógép"), "rvztr-tkrfrgp")  # spellchecker:disable-line

    def test_title_to_ascii_slug(self) -> None:
        self.assertEqual(title_to_ascii_slug("  This is  a Heading  "), "this-is-a-heading")
        self.assertEqual(title_to_ascii_slug("What's New in v2.0?"), "whats-new-in-v20")
        self.assertEqual(title_to_ascii_slug("C++ & C# Comparison"), "c-c-comparison")
        self.assertEqual(title_to_ascii_slug("Hello -- World!!"), "hello----world")
        # spellchecker: disable
        self.assertEqual(title_to_ascii_slug("paramètres"), "parametres")
        self.assertEqual(title_to_ascii_slug("árvíztűrő tükörfúrógép"), "arvizturo-tukorfurogep")
        self.assertEqual(title_to_ascii_slug("ÁRVÍZTŰRŐ TÜKÖRFÚRÓGÉP"), "arvizturo-tukorfurogep")
        # spellchecker: enable

    def verify_transformer(self, transformer: Callable[[str], str]) -> None:
        self.assertEqual(transformer("1989.10.23,(_):[_];"), "19891023__")
        self.assertEqual(transformer("a :thumbsup: shortcode"), "a-thumbsup-shortcode")  # spellchecker: disable-line

        # spellchecker: disable
        self.assertEqual(transformer("paramètres"), "paramètres")
        self.assertEqual(transformer("árvíztűrő tükörfúrógép"), "árvíztűrő-tükörfúrógép")
        self.assertEqual(transformer("ÁRVÍZTŰRŐ TÜKÖRFÚRÓGÉP"), "árvíztűrő-tükörfúrógép")
        # spellchecker: enable

        self.assertEqual(transformer("Cyrillic: Кириллица"), "cyrillic-кириллица")  # spellchecker: disable-line
        self.assertEqual(transformer("Hebrew: עברית"), "hebrew-עברית")  # spellchecker: disable-line
        self.assertEqual(transformer("Japanese: 日本語"), "japanese-日本語")
        self.assertEqual(transformer("Korean: 한글"), "korean-한글")

        self.assertEqual(transformer("Hiragana: ひらがな"), "hiragana-ひらがな")
        self.assertEqual(transformer("Katakana: カタカナ"), "katakana-カタカナ")
        self.assertEqual(transformer("Kanji: 漢字"), "kanji-漢字")

        self.assertEqual(transformer("Emoji: 😄_😄"), "emoji-_")

        self.assertEqual(
            transformer(" ".join("ÀÁÂÃÄÅĀĂĄÈÉÊËĒĘÌÍÎÏĪĮÒÓÔÕÖØŐŌÙÚÛÜŰŪŲÝŸÇĆČĎÐĢĞĶĻĹĽŁÑŃŅŇŘŔŚŞŠȘŤŢÞȚŹŻŽÆŒẞ")),  # spellchecker: disable-line
            "-".join("àáâãäåāăąèéêëēęìíîïīįòóôõöøőōùúûüűūųýÿçćčďðģğķļĺľłñńņňřŕśşšșťţþțźżžæœß"),  # spellchecker: disable-line
        )

    def test_title_to_classic_slug(self) -> None:
        self.assertEqual(title_to_common_slug("  This is  a Heading  "), "this-is-a-heading")
        self.assertEqual(title_to_common_slug("What's New in v2.0?"), "whats-new-in-v20")
        self.assertEqual(title_to_common_slug("C++ & C# Comparison"), "c-c-comparison")
        self.assertEqual(title_to_common_slug("Hello -- World!!"), "hello----world")
        self.assertEqual(title_to_common_slug("multiple  spaces and --- hyphens_and_underscores"), "multiple-spaces-and-----hyphens_and_underscores")
        self.assertEqual(title_to_common_slug("I ♥ Unicode"), "i-unicode")
        self.verify_transformer(title_to_common_slug)

    def test_title_to_slug(self) -> None:
        self.assertEqual(title_to_slug("  This is  a Heading  "), "this-is--a-heading")
        self.assertEqual(title_to_slug("What's New in v2.0?"), "whats-new-in-v20")
        self.assertEqual(title_to_slug("C++ & C# Comparison"), "c--c-comparison")
        self.assertEqual(title_to_slug("Hello -- World!!"), "hello----world")
        self.assertEqual(title_to_slug("multiple  spaces and --- hyphens_and_underscores"), "multiple--spaces-and-----hyphens_and_underscores")
        self.assertEqual(title_to_slug("I ♥ Unicode"), "i--unicode")
        self.verify_transformer(title_to_slug)

        # currency symbols are removed, each space in between is replaced with a hyphen
        self.assertEqual(title_to_slug(" ".join(currency_symbols)), "-" * (len(currency_symbols) - 1))


if __name__ == "__main__":
    unittest.main()
