# app/utils/flash.py
from __future__ import annotations

from flask import flash


def flash_success(message: str) -> None:
    flash(message, "success")


def flash_info(message: str) -> None:
    flash(message, "info")


def flash_warning(message: str) -> None:
    flash(message, "warning")


def flash_danger(message: str) -> None:
    flash(message, "danger")