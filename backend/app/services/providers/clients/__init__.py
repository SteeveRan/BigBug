"""Thin HTTP clients per provider domain (git / docker / helm).

Each client reuses httpx and never logs secrets or Authorization headers.
"""
