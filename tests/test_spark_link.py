"""Spark deep-link encoding."""

from __future__ import annotations

from urllib.parse import unquote

from email_digest.spark_link import spark_deeplink


def test_spark_deeplink_encodes_angle_brackets() -> None:
    mid = "<digest-1@mail.gmail.com>"
    url = spark_deeplink(mid)
    assert url.startswith("readdle-spark://openmessage?messageId=")
    assert unquote(url.split("messageId=", 1)[1]) == mid


def test_spark_deeplink_empty() -> None:
    assert spark_deeplink("") == ""
    assert spark_deeplink("   ") == ""


def test_spark_deeplink_encodes_ampersand_and_space() -> None:
    mid = "list+tag & more@example.com"
    url = spark_deeplink(mid)
    assert url.startswith("readdle-spark://openmessage?messageId=")
    assert unquote(url.split("messageId=", 1)[1]) == mid
