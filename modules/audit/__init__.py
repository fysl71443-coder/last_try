# -*- coding: utf-8 -*-
"""
محرك التدقيق المحاسبي — كل شيء ينتهي إلى Journal Entries.
المدقق لا يثق بأحد: يعمل بغض النظر عن واجهة المستخدم أو مصدر البيانات.
"""
from .engine import run_audit

__all__ = ["run_audit"]
