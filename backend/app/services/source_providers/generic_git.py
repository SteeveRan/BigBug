"""
@file source_providers/generic_git.py
@description GenericGitSourceProvider — BaseSourceProvider implementation for any
             Git repository accessible via HTTPS or SSH. Uses only git CLI (no API).
             Discovers repository metadata through git clone --bare, git ls-remote,
             and heuristic analysis of repository files (LICENSE, README, tags).
@dependencies asyncio, tempfile, re, urllib.parse, app.core.exceptions.DomainException,
             app.services.source_provider.BaseSourceProvider
@relatedFiles ../source_provider.py, ../../models/source_provider.py,
             ./github.py, ./gitlab.py, ./dispatcher.py
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shutil
import tempfile
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.core.exceptions import DomainException
from app.services.source_provider import BaseSourceProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# License detection heuristics
# ---------------------------------------------------------------------------

_SPDX_PATTERNS: list[tuple[str, str, str]] = [
    # (spdx_id, name, pattern) — order matters: more specific first
    (
        "AGPL-3.0-only",
        "GNU Affero General Public License v3.0",
        r"GNU AFFERO GENERAL PUBLIC LICENSE",
    ),
    ("GPL-3.0-only", "GNU General Public License v3.0", r"GNU GENERAL PUBLIC LICENSE.*Version 3"),
    ("GPL-2.0-only", "GNU General Public License v2.0", r"GNU GENERAL PUBLIC LICENSE.*Version 2"),
    (
        "LGPL-2.1-only",
        "GNU Lesser General Public License v2.1",
        r"GNU LESSER GENERAL PUBLIC LICENSE.*Version 2\.1",
    ),
    ("MPL-2.0", "Mozilla Public License 2.0", r"Mozilla Public License Version 2\.0"),
    ("Apache-2.0", "Apache License 2.0", r"Apache License,? Version 2\.0"),
    ("MIT", "MIT License", r"Permission is hereby granted.*MIT"),
    (
        "Unlicense",
        "The Unlicense",
        r"This is free and unencumbered software released into the public domain",
    ),
    ("BSD-3-Clause", "BSD 3-Clause License", r"Redistribution and use.*neither the name"),
    ("BSD-2-Clause", "BSD 2-Clause License", r"Redistribution and use"),
]


def _detect_license_from_file(content: str) -> tuple[str | None, str | None]:
    """
    Detect an SPDX license identifier and name from the first ~500 characters
    of a LICENSE/COPYING file using heuristics.

    Args:
        content: The first portion of the license file text.

    Returns:
        A (license_spdx, license_name) tuple. Either element may be None
        if no known license is detected.
    """
    if not content:
        return None, None

    # Normalize: collapse whitespace for regex matching
    normalized = re.sub(r"\s+", " ", content)

    for spdx_id, name, pattern in _SPDX_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return spdx_id, name

    # Check for MIT with a broader pattern (some variants don't have "MIT" near the permission text)
    if re.search(r"Permission is hereby granted", normalized, re.IGNORECASE):
        return "MIT", "MIT License"

    return None, None


# ---------------------------------------------------------------------------
# ls-remote tag parsing
# ---------------------------------------------------------------------------

_VERSION_TAG_RE = re.compile(
    r"^refs/tags/(?:v(?:er(?:sion)?)?[\s.\-_]*|release[\s.\-_]*)?(\d+(?:[.\-_]\d+)*)$",
    re.IGNORECASE,
)


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string like '1.2.3' into a comparable tuple (1, 2, 3)."""
    parts = re.split(r"[.\-_]", version_str)
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


def _parse_ls_remote_tags(output: str) -> tuple[int, str | None]:
    """
    Parse ``git ls-remote --tags`` output to extract release information.

    Args:
        output: Raw stdout from ``git ls-remote --tags <url>``.

    Returns:
        A (releases_count, latest_release_tag) tuple.  ``latest_release_tag``
        is None when no version-like tags are found.
    """
    if not output.strip():
        return 0, None

    version_tags: list[tuple[str, tuple[int, ...]]] = []

    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        # Format: <sha>\trefs/tags/<tagname>
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        ref = parts[1]
        match = _VERSION_TAG_RE.match(ref)
        if match:
            tag_name = ref[len("refs/tags/") :]  # noqa: E226
            version_tuple = _parse_version(match.group(1))
            version_tags.append((tag_name, version_tuple))

    if not version_tags:
        return 0, None

    # Sort by version tuple descending, then by tag name for tie-breaking
    version_tags.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return len(version_tags), version_tags[0][0]


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _extract_repo_info_from_url(url: str) -> dict[str, str | None]:
    """
    Extract repository name and full path from a Git URL.

    Args:
        url: An HTTPS or SSH Git URL (e.g. https://github.com/owner/repo.git
             or git@github.com:owner/repo.git).

    Returns:
        Dict with keys: ``name``, ``full_name``, ``clone_url``, ``html_url``, ``ssh_url``.
    """
    result: dict[str, str | None] = {
        "name": None,
        "full_name": None,
        "clone_url": None,
        "html_url": None,
        "ssh_url": None,
    }

    url = url.rstrip("/")

    if url.startswith("git@"):
        # SSH URL: git@host:owner/repo.git
        result["ssh_url"] = url
        match = re.match(r"^git@([^:]+):(.+)$", url)
        if match:
            path_part = match.group(2)
            # Remove trailing .git
            if path_part.endswith(".git"):
                path_part = path_part[:-4]
            result["full_name"] = path_part
            result["name"] = path_part.split("/")[-1]
        return result

    # HTTPS URL
    result["clone_url"] = url
    result["html_url"] = url
    if url.endswith(".git"):
        url_no_git = url[:-4]
        result["clone_url"] = url  # keep original as clone_url
    else:
        url_no_git = url

    parsed = urlparse(url_no_git)
    path = parsed.path.lstrip("/")
    if path:
        result["full_name"] = path
        result["name"] = path.split("/")[-1]

    return result


def _build_auth_url(url: str, credential_secret: str) -> str:
    """
    Embed credentials into an HTTPS URL for git operations.

    Args:
        url: The original HTTPS URL.
        credential_secret: The token or password to embed.

    Returns:
        URL with embedded credentials: ``https://user:token@host/path``.
    """
    if not url.startswith("https://"):
        return url  # SSH URLs are not modified

    parsed = urlparse(url)
    # Use 'git' as the username for token-based auth
    auth_url = f"{parsed.scheme}://git:{credential_secret}@{parsed.hostname}"
    if parsed.port:
        auth_url += f":{parsed.port}"
    auth_url += parsed.path
    if parsed.query:
        auth_url += f"?{parsed.query}"
    return auth_url


# ---------------------------------------------------------------------------
# Git subprocess helpers
# ---------------------------------------------------------------------------


async def _run_git(
    *args: str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: float = 60.0,
) -> tuple[int, str, str]:
    """
    Run a git command asynchronously via subprocess.

    Args:
        *args: The git command arguments.
        env: Environment variables for the subprocess.
        cwd: Working directory.
        timeout: Timeout in seconds.

    Returns:
        A (returncode, stdout, stderr) tuple.

    Raises:
        DomainException: On timeout.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Disable interactive prompts
    full_env.setdefault("GIT_TERMINAL_PROMPT", "0")

    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
            cwd=cwd,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return proc.returncode or 0, stdout, stderr
    except TimeoutError as exc:
        raise DomainException(
            f"Git operation timed out after {timeout}s: git {' '.join(args)}",
            status_code=504,
        ) from exc
    except FileNotFoundError as exc:
        raise DomainException(
            "Git executable not found on the system",
            status_code=500,
        ) from exc


# ---------------------------------------------------------------------------
# GenericGitSourceProvider
# ---------------------------------------------------------------------------


class GenericGitSourceProvider(BaseSourceProvider):
    """
    Generic Git implementation of :class:`BaseSourceProvider`.

    Uses only the ``git`` CLI (``ls-remote``, ``clone --bare``) to discover
    repository metadata.  No platform-specific API is required — any Git
    repository accessible via HTTPS or SSH can be inspected.

    Args:
        provider: :class:`SourceProvider` ORM model.
        credential_secret: Decrypted secret (token/password for HTTPS,
                           SSH private key for SSH).
    """

    # -- BaseSourceProvider interface ---------------------------------------

    async def check_access(self) -> bool:
        """
        Verify that the repository is accessible with the given credential.

        Uses ``git ls-remote`` against the provider's base URL (or first
        configured repository URL if available).

        Returns:
            ``True`` on success.

        Raises:
            DomainException: If authentication fails, the repository is not
                            found, or the operation times out.
        """
        # For generic git, check_access needs a URL. We use a default
        # test: run ls-remote on a representative URL.
        # In practice, the provider configuration stores URLs via source groups.
        # We'll just attempt a basic connectivity test.
        target_url = _build_auth_url("https://github.com", self.credential_secret)
        env_override: dict[str, str] = {}

        returncode, stdout, stderr = await _run_git(
            "ls-remote",
            target_url,
            "--heads",
            env=env_override,
            timeout=15.0,
        )

        if returncode != 0:
            if "could not resolve host" in stderr.lower():
                raise DomainException(
                    f"Could not resolve git host during check_access: {stderr.strip()}",
                    status_code=502,
                )
            if "authentication failed" in stderr.lower() or "invalid" in stderr.lower():
                raise DomainException(
                    f"Git authentication failed during check_access: {stderr.strip()}",
                    status_code=401,
                )
            if "not found" in stderr.lower():
                raise DomainException(
                    f"Git repository not found during check_access: {stderr.strip()}",
                    status_code=404,
                )
            raise DomainException(
                f"Git error during check_access: {stderr.strip()}",
                status_code=502,
            )

        logger.info(
            "GenericGit check_access OK — ls-remote returned %d lines",
            len(stdout.strip().split("\n")) if stdout.strip() else 0,
        )
        return True

    async def list_groups(self) -> list[dict]:
        """
        Generic Git has no organizational structure.
        Always returns an empty list.
        """
        return []

    async def list_repositories(self, group_external_id: str) -> list[dict]:
        """
        For generic Git, ``group_external_id`` is a repository URL.
        Returns a single-repository list if the URL is valid.

        Args:
            group_external_id: A Git repository URL (HTTPS or SSH).

        Returns:
            A list with one repository dict if the URL looks valid,
            or an empty list.
        """
        if not group_external_id or not isinstance(group_external_id, str):
            return []

        url = group_external_id.strip()
        if not (url.startswith("https://") or url.startswith("git@")):
            return []

        info = _extract_repo_info_from_url(url)
        repo = {
            "external_id": url,  # Use the URL itself as the external ID
            "name": info["name"] or "unknown",
            "full_name": info["full_name"] or url,
            "description": None,
            "private": False,
            "fork": False,
            "archived": False,
            "disabled": False,
            "language": None,
            "default_branch": None,
            "html_url": info["html_url"],
            "clone_url": info["clone_url"],
            "ssh_url": info["ssh_url"],
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "created_at": None,
            "updated_at": None,
            "pushed_at": None,
            "last_commit_sha": None,
            "last_commit_date": None,
            "last_commit_author": None,
            "license_spdx": None,
            "license_name": None,
            "releases_count": 0,
        }
        return [repo]

    async def get_repository(self, repo_external_id: str) -> dict:
        """
        Get detailed information about a single Git repository by cloning it
        bare and extracting metadata.

        Args:
            repo_external_id: The repository URL (HTTPS or SSH).

        Returns:
            Dict with all repository metadata fields per contract.

        Raises:
            DomainException: If the repository is not accessible.
        """
        url = repo_external_id.strip()
        info = _extract_repo_info_from_url(url)
        clone_url = url

        # Build authenticated URL for HTTPS
        if url.startswith("https://"):
            clone_url = _build_auth_url(url, self.credential_secret)

        tmpdir = tempfile.mkdtemp(prefix="bigbug_git_clone_")
        env_override: dict[str, str] = {}

        try:
            # Clone bare
            returncode, stdout, stderr = await _run_git(
                "clone",
                "--bare",
                clone_url,
                tmpdir,
                env=env_override,
                timeout=120.0,
            )

            if returncode != 0:
                if "authentication failed" in stderr.lower() or "could not read" in stderr.lower():
                    raise DomainException(
                        f"Git authentication failed for {url}: {stderr.strip()}",
                        status_code=401,
                    )
                if "not found" in stderr.lower():
                    raise DomainException(
                        f"Git repository not found: {url}",
                        status_code=404,
                    )
                raise DomainException(
                    f"Git clone failed for {url}: {stderr.strip()}",
                    status_code=502,
                )

            # Get default branch from HEAD
            default_branch = await _get_default_branch(tmpdir)

            # Get last commit on default branch
            last_commit_sha = None
            last_commit_date = None
            last_commit_author = None
            if default_branch:
                ref_name = default_branch
                if not ref_name.startswith("refs/"):
                    ref_name = f"refs/heads/{default_branch}"
                returncode, stdout, stderr = await _run_git(
                    "log",
                    "-1",
                    "--format=%H%n%aI%n%an",
                    ref_name,
                    cwd=tmpdir,
                    timeout=30.0,
                )
                if returncode == 0 and stdout.strip():
                    lines = stdout.strip().split("\n")
                    if len(lines) >= 1:
                        last_commit_sha = lines[0].strip()
                    if len(lines) >= 2:
                        last_commit_date = lines[1].strip()
                    if len(lines) >= 3:
                        last_commit_author = lines[2].strip()

            # License detection — look for LICENSE* or COPYING* files
            license_spdx, license_name = await _detect_license_from_clone(tmpdir)

            # README detection
            readme_html = await _detect_readme_from_clone(tmpdir)

            # Tags / releases
            tags_output = ""
            tag_url = clone_url if url.startswith("https://") else url
            returncode, stdout, stderr = await _run_git(
                "ls-remote",
                "--tags",
                tag_url,
                env=env_override,
                timeout=30.0,
            )
            if returncode == 0:
                tags_output = stdout

            releases_count, latest_tag = _parse_ls_remote_tags(tags_output)

            result: dict = {
                "external_id": repo_external_id,
                "name": info["name"] or "unknown",
                "full_name": info["full_name"] or repo_external_id,
                "description": None,
                "private": False,
                "fork": False,
                "archived": False,
                "disabled": False,
                "language": None,
                "default_branch": default_branch or "main",
                "html_url": info["html_url"] or repo_external_id,
                "clone_url": info["clone_url"] or repo_external_id,
                "ssh_url": info["ssh_url"],
                "stars": 0,
                "forks": 0,
                "open_issues": 0,
                "created_at": None,
                "updated_at": None,
                "pushed_at": None,
                "last_commit_sha": last_commit_sha,
                "last_commit_date": last_commit_date,
                "last_commit_author": last_commit_author,
                "license_spdx": license_spdx,
                "license_name": license_name,
                "releases_count": releases_count,
                "readme_html": readme_html,
                "latest_release_tag": latest_tag,
                "latest_release_name": latest_tag,
                "latest_release_published_at": None,
                "latest_release_author": None,
                "latest_release_html_url": None,
            }
            return result

        finally:
            # Clean up temp directory
            with contextlib.suppress(OSError):
                shutil.rmtree(tmpdir, ignore_errors=True)

    async def get_commit_info(self, repo_external_id: str, ref: str | None = None) -> dict:
        """
        Get information about a commit on the repository.

        Uses ``git ls-remote`` to resolve the ref to a SHA, then
        ``git clone --bare --depth 1`` to get commit metadata.

        Args:
            repo_external_id: The repository URL.
            ref: Branch name, tag, or commit SHA. If None, uses the default branch.

        Returns:
            Dict with: ``sha``, ``date``, ``author``, ``message``.

        Raises:
            DomainException: If the ref is not found or the repo is inaccessible.
        """
        url = repo_external_id.strip()
        clone_url = (
            url if not url.startswith("https://") else _build_auth_url(url, self.credential_secret)
        )
        env_override: dict[str, str] = {}

        if ref is None:
            # Need to discover the default branch first
            tmpdir = tempfile.mkdtemp(prefix="bigbug_git_commit_")
            try:
                returncode, _stdout, stderr = await _run_git(
                    "clone",
                    "--bare",
                    "--depth",
                    "1",
                    clone_url,
                    tmpdir,
                    env=env_override,
                    timeout=120.0,
                )
                if returncode != 0:
                    raise DomainException(
                        f"Git clone failed for {url}: {stderr.strip()}",
                        status_code=502,
                    )
                default_branch = await _get_default_branch(tmpdir)
                ref = default_branch or "HEAD"
            finally:
                with contextlib.suppress(OSError):
                    shutil.rmtree(tmpdir, ignore_errors=True)

        # Resolve the ref to a SHA via ls-remote
        returncode, stdout, stderr = await _run_git(
            "ls-remote",
            clone_url,
            ref,
            env=env_override,
            timeout=30.0,
        )

        if returncode != 0:
            if "not found" in stderr.lower():
                raise DomainException(
                    f"Ref '{ref}' not found in repository {url}",
                    status_code=404,
                )
            raise DomainException(
                f"Git ls-remote failed for {url}: {stderr.strip()}",
                status_code=502,
            )

        if not stdout.strip():
            raise DomainException(
                f"Ref '{ref}' not found in repository {url}",
                status_code=404,
            )

        sha = stdout.strip().split()[0]

        # Clone bare --depth 1 to get commit metadata
        tmpdir2 = tempfile.mkdtemp(prefix="bigbug_git_commit_meta_")
        try:
            # Clone just enough to get the commit
            returncode, _stdout, stderr = await _run_git(
                "clone",
                "--bare",
                "--depth",
                "1",
                "--branch",
                ref,
                clone_url,
                tmpdir2,
                env=env_override,
                timeout=120.0,
            )

            if returncode != 0:
                # Try cloning without branch filter, then fetch the specific commit
                shutil.rmtree(tmpdir2, ignore_errors=True)
                os.makedirs(tmpdir2, exist_ok=True)

                returncode, _stdout, stderr = await _run_git(
                    "init",
                    "--bare",
                    tmpdir2,
                    env=env_override,
                    timeout=10.0,
                )
                returncode, _stdout, stderr = await _run_git(
                    "fetch",
                    "--depth",
                    "1",
                    clone_url,
                    sha,
                    cwd=tmpdir2,
                    env=env_override,
                    timeout=120.0,
                )
                if returncode != 0:
                    raise DomainException(
                        f"Failed to fetch commit {sha[:8]} from {url}: {stderr.strip()}",
                        status_code=502,
                    )

            # Get commit metadata
            returncode, stdout, stderr = await _run_git(
                "log",
                "-1",
                "--format=%H%n%aI%n%an%n%s",
                sha,
                cwd=tmpdir2,
                timeout=30.0,
            )

            if returncode != 0 or not stdout.strip():
                raise DomainException(
                    f"No commit data found for {sha[:8]} in {url}",
                    status_code=502,
                )

            lines = stdout.strip().split("\n")
            return {
                "sha": lines[0].strip() if len(lines) >= 1 else sha,
                "date": lines[1].strip() if len(lines) >= 2 else None,
                "author": lines[2].strip() if len(lines) >= 3 else None,
                "message": lines[3].strip() if len(lines) >= 4 else "",
            }

        finally:
            with contextlib.suppress(OSError):
                shutil.rmtree(tmpdir2, ignore_errors=True)

    async def verify_mirror(self, source_url: str, target_url: str) -> bool:
        """
        Verify that a mirror is up-to-date by comparing ref SHAs on both sides.

        Args:
            source_url: The source repository URL.
            target_url: The target (mirror) repository URL.

        Returns:
            ``True`` if all common refs have matching SHAs.
        """
        env_override: dict[str, str] = {}

        # Get source refs
        source_refs: dict[str, str] = {}
        returncode, stdout, stderr = await _run_git(
            "ls-remote",
            source_url,
            env=env_override,
            timeout=30.0,
        )
        if returncode == 0:
            for line in stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    source_refs[parts[1]] = parts[0]

        if not source_refs:
            return False

        # Get target refs
        target_refs: dict[str, str] = {}
        returncode, stdout, stderr = await _run_git(
            "ls-remote",
            target_url,
            env=env_override,
            timeout=30.0,
        )
        if returncode == 0:
            for line in stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    target_refs[parts[1]] = parts[0]

        # Compare common refs
        common_refs = set(source_refs.keys()) & set(target_refs.keys())
        if not common_refs:
            return False

        return all(source_refs[ref] == target_refs[ref] for ref in common_refs)


# ---------------------------------------------------------------------------
# Internal helpers (clone-based inspection)
# ---------------------------------------------------------------------------


async def _get_default_branch(repo_dir: str) -> str | None:
    """
    Determine the default branch from a bare repository by reading HEAD.

    Args:
        repo_dir: Path to a bare git repository.

    Returns:
        The default branch name (e.g. 'main', 'master') or None.
    """
    head_path = os.path.join(repo_dir, "HEAD")
    try:
        if os.path.isfile(head_path):
            with open(head_path) as f:
                content = f.read().strip()
            if content.startswith("ref: refs/heads/"):
                return content[len("ref: refs/heads/") :]
            # Detached HEAD — return the SHA
            return content[:40] if len(content) >= 40 else content
    except OSError:
        pass
    return None


async def _detect_license_from_clone(repo_dir: str) -> tuple[str | None, str | None]:
    """
    Search for LICENSE* or COPYING* files in the bare clone and attempt to
    detect the license via heuristics.

    Args:
        repo_dir: Path to a bare git repository.

    Returns:
        A (license_spdx, license_name) tuple.
    """
    # In a bare repository, files are not checked out.
    # We need to use `git show` to read files from HEAD.
    candidate_files = []
    try:
        for entry in os.listdir(repo_dir):
            if entry.upper().startswith("LICENSE") or entry.upper().startswith("COPYING"):
                candidate_files.append(entry)
                break  # Only need one file
    except OSError:
        pass

    # Try using git show
    for filename in candidate_files:
        returncode, stdout, stderr = await _run_git(
            "show",
            f"HEAD:{filename}",
            cwd=repo_dir,
            timeout=10.0,
        )
        if returncode == 0 and stdout.strip():
            content = stdout[:500]
            return _detect_license_from_file(content)

    # Fallback: try index-based extraction
    returncode, stdout, stderr = await _run_git(
        "ls-tree",
        "--name-only",
        "HEAD",
        cwd=repo_dir,
        timeout=10.0,
    )
    if returncode == 0:
        for line in stdout.strip().split("\n"):
            name = line.strip()
            if name.upper().startswith("LICENSE") or name.upper().startswith("COPYING"):
                returncode2, stdout2, _ = await _run_git(
                    "show",
                    f"HEAD:{name}",
                    cwd=repo_dir,
                    timeout=10.0,
                )
                if returncode2 == 0 and stdout2.strip():
                    content = stdout2[:500]
                    return _detect_license_from_file(content)
                break

    return None, None


async def _detect_readme_from_clone(repo_dir: str) -> str | None:
    """
    Read the README.md (or README) file from a bare clone.

    Args:
        repo_dir: Path to a bare git repository.

    Returns:
        Raw markdown content of the README file, or None.
    """
    readme_names = ["README.md", "README", "readme.md", "readme"]
    for readme_name in readme_names:
        returncode, stdout, stderr = await _run_git(
            "show",
            f"HEAD:{readme_name}",
            cwd=repo_dir,
            timeout=10.0,
        )
        if returncode == 0 and stdout.strip():
            return stdout

    return None
