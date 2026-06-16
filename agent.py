import os
import json
import subprocess
from datetime import datetime, timezone

import boto3

# ----------------------------
# ENV VARS FROM ECS
# ----------------------------
SESSION_ID = os.environ["SESSION_ID"]
REPO = os.environ["REPO"]  # accepts "owner/repo" or "https://github.com/owner/repo"
PROMPT = os.environ["PROMPT"]
S3_BUCKET = os.environ["S3_BUCKET"]

CODEX_AUTH_JSON = os.environ.get("CODEX_AUTH_JSON")
GITHUB_USER_TOKEN = os.environ["GITHUB_USER_TOKEN"]

# ----------------------------
# AWS CLIENTS
# ----------------------------
s3 = boto3.client("s3")


# ----------------------------
# CODEx AUTH.JSON HANDOFF
# ----------------------------
def ensure_codex_auth_file():
    if not CODEX_AUTH_JSON:
        raise RuntimeError(
            "CODEX_AUTH_JSON was not provided. Add the Codex auth.json secret to ECS."
        )

    codex_dir = os.path.join(os.path.expanduser("~"), ".codex")
    os.makedirs(codex_dir, mode=0o700, exist_ok=True)

    try:
        os.chmod(codex_dir, 0o700)
    except PermissionError:
        pass

    auth_path = os.path.join(codex_dir, "auth.json")
    with open(auth_path, "w", encoding="utf-8") as f:
        f.write(CODEX_AUTH_JSON)

    try:
        os.chmod(auth_path, 0o600)
    except PermissionError:
        pass


# ----------------------------
# GITHUB HELPERS
# ----------------------------
def normalize_repo(repo: str) -> str:
    repo = repo.strip()

    if repo.startswith("https://github.com/"):
        repo = repo[len("https://github.com/") :]
    elif repo.startswith("http://github.com/"):
        repo = repo[len("http://github.com/") :]

    repo = repo.removesuffix(".git")
    return repo.lstrip("/")


def build_repo_url(repo: str) -> str:
    repo_path = normalize_repo(repo)
    return f"https://x-access-token:{GITHUB_USER_TOKEN}@github.com/{repo_path}.git"


# ----------------------------
# STEP 1: CLONE REPO
# ----------------------------
def clone_repo():
    repo_url = build_repo_url(REPO)
    path = "/tmp/repo"

    subprocess.run(["git", "clone", repo_url, path], check=True)

    return path


# ----------------------------
# STEP 2: RUN CODEX CLI
# ----------------------------
def run_codex(prompt, repo_path):
    ensure_codex_auth_file()

    result = subprocess.run(
        [
          "codex",
          "exec",
          "--skip-git-repo-check",
          "--dangerously-bypass-approvals-and-sandbox",
          prompt
        ],
        cwd=repo_path,
        check=True,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result


# ----------------------------
# STEP 3: COMMIT + PUSH
# ----------------------------
def commit_changes(repo_path):
    branch = f"agent/{SESSION_ID}"
    repo_url = build_repo_url(REPO)

    subprocess.run(
        ["git", "config", "--global", "user.email", "codex-bot@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "config", "--global", "user.name", "Codex Bot"],
        check=True,
    )

    subprocess.run(["git", "checkout", "-b", branch], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Codex changes for session {SESSION_ID}"],
        cwd=repo_path,
        check=True,
    )

    # Ensure origin uses the authenticated GitHub user token
    subprocess.run(
        ["git", "remote", "set-url", "origin", repo_url],
        cwd=repo_path,
        check=True,
    )

    subprocess.run(["git", "push", "origin", branch], cwd=repo_path, check=True)

    return branch


# ----------------------------
# STEP 4: WRITE RESULT TO S3
# ----------------------------
def write_result(branch):
    result = {
        "sessionId": SESSION_ID,
        "repo": REPO,
        "branch": branch,
        "status": "COMPLETED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{SESSION_ID}/result.json",
        Body=json.dumps(result).encode("utf-8"),
        ContentType="application/json",
    )


# ----------------------------
# MAIN EXECUTION
# ----------------------------
def main():
    print("Starting agent...")
    print("Session:", SESSION_ID)
    print("Repo:", REPO)
    print("Prompt:", PROMPT)

    repo_path = clone_repo()
    run_codex(PROMPT, repo_path)
    branch = commit_changes(repo_path)
    write_result(branch)

    print("Agent completed successfully.")


if __name__ == "__main__":
    main()