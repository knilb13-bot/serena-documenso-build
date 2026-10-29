"""Proposta de executor CI público. Sem argumento, imprime plano e não constrói."""
from pathlib import Path, PurePosixPath
import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
BASE = "documenso/documenso@sha256:04ac1003006e1086404e5b3aa9d748e84d8c0fd4cc5ee28938d6face9eb799ec"
COMMIT = "8707e33c124e4b1a68dde92d5e05178c9aabd0be"
LOCK = "92767f6b48c0710364669c0270015a3d3f4e4b8ebbc00ac931d97041fe4b1fce"
DERIVED = "9c2d29755f01aa0d002145521c66d55656309c49d5c2bb29daee3363aabdf775"
REPOSITORY = "knilb13-bot/serena-documenso-build"
CAP = 10 * 1024**3
DEADLINE = 24 * 60
MAX_RELEASE_ASSET = 2 * 1024**3
RUNTIME_CMD = ["sh", "-c", 'export NEXT_PRIVATE_DIRECT_DATABASE_URL="${NEXT_PRIVATE_DIRECT_DATABASE_URL:-$NEXT_PRIVATE_DATABASE_URL}"; HOSTNAME=0.0.0.0 exec node build/server/main.js']


def expected_runtime_dockerfile():
    return ("FROM " + BASE + "\n"
            "# Empacotamento COPY-only; sem RUN, dependencias ou dados de producao.\n"
            "COPY --chown=1001:1001 output/build /app/apps/remix/build\n"
            "COPY --chown=1001:1001 output/public /app/apps/remix/public\n"
            "# Startup direto: preserva fallback de URL e HOSTNAME; nao executa migrations.\n"
            "CMD " + json.dumps(RUNTIME_CMD, separators=(",", ":")) + "\n").encode()


def remaining_budget(start, clock=time.monotonic):
    remaining = int(DEADLINE - (clock() - start))
    need(remaining > 0, "PACKAGING_DEADLINE_EXCEEDED")
    return remaining


def file_proof(path, limit=MAX_RELEASE_ASSET, budget=None):
    need(path.is_file() and not path.is_symlink(), "ASSET_REGULAR_FILE_REQUIRED")
    size, digest = 0, hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            if budget:
                budget()
            size += len(chunk)
            need(size < limit, "RELEASE_ASSET_SIZE_LIMIT")
            digest.update(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def runtime_image_plan(context, image_tag, iidfile):
    need(re.fullmatch(r"serena-documenso-build:run-[0-9]+-[0-9]+", image_tag), "IMAGE_TAG_INVALID")
    return ["docker", "build", "--network=none", "--pull=false", "--tag", image_tag,
            "--iidfile", str(iidfile), "--file", str(context / "Dockerfile"), str(context)]


def verify_runtime_image(base, image):
    need(base.get("Os") == image.get("Os") == "linux" and base.get("Architecture") == image.get("Architecture") == "amd64", "IMAGE_PLATFORM_MISMATCH")
    need(re.fullmatch(r"sha256:[0-9a-f]{64}", base.get("Id", "")) and re.fullmatch(r"sha256:[0-9a-f]{64}", image.get("Id", "")), "IMAGE_ID_INVALID")
    need(BASE in base.get("RepoDigests", []), "PINNED_BASE_DIGEST_MISSING")
    before, after = base.get("Config", {}), image.get("Config", {})
    need(not before.get("OnBuild"), "BASE_ONBUILD_FORBIDDEN")
    need(before.get("Entrypoint") in (["docker-entrypoint.sh"], ["/usr/local/bin/docker-entrypoint.sh"]), "BASE_ENTRYPOINT_UNREVIEWED")
    need(after.get("Entrypoint") == before.get("Entrypoint"), "IMAGE_ENTRYPOINT_CHANGED")
    need(before.get("WorkingDir") == after.get("WorkingDir") == "/app/apps/remix", "IMAGE_WORKDIR_MISMATCH")
    need(before.get("User") == "nodejs" and after.get("User") == before.get("User"), "IMAGE_USER_MISMATCH")
    need(after.get("Cmd") == RUNTIME_CMD, "IMAGE_RUNTIME_CMD_MISMATCH")
    need(after.get("Env") == before.get("Env"), "IMAGE_ENV_CHANGED")
    base_layers, image_layers = base.get("RootFS", {}).get("Layers", []), image.get("RootFS", {}).get("Layers", [])
    need(base_layers and image_layers[:len(base_layers)] == base_layers, "IMAGE_BASE_LAYERS_MISMATCH")
    need(type(image.get("Size")) is int and image["Size"] > 0, "IMAGE_SIZE_INVALID")
    return {"image_id": image["Id"], "base_image": BASE, "base_image_id": base["Id"],
            "image_size_bytes": image["Size"], "runtime_cmd": RUNTIME_CMD,
            "entrypoint": after["Entrypoint"], "user": after["User"], "workdir": after["WorkingDir"],
            "base_layers_preserved": True, "migration_command_in_startup": False}


def package_runtime_image(area, bundle, files, start, runner=None, disk_free=None, clock=time.monotonic):
    runner = runner or command
    budget = lambda: remaining_budget(start, clock)
    free = disk_free or (lambda: shutil.disk_usage(area).free)
    dockerfile = ROOT / "Dockerfile.output"
    need(dockerfile.read_bytes() == expected_runtime_dockerfile(), "RUNTIME_DOCKERFILE_CHANGED")
    base = json.loads(runner(["docker", "image", "inspect", BASE, "--format", "{{json .}}"], timeout=budget()))
    need(not base.get("Config", {}).get("OnBuild") and BASE in base.get("RepoDigests", []), "BASE_NOT_READY_FOR_COPY_ONLY")
    need(type(base.get("Size")) is int and base["Size"] > 0, "BASE_SIZE_INVALID")
    context_bytes = sum((area / "out" / name).stat().st_size for name in (p.removeprefix("output/") for p in files))
    need(free() >= base["Size"] + context_bytes + MAX_RELEASE_ASSET + 1024**3, "IMAGE_PACKAGING_DISK_RESERVE_UNPROVEN")
    context = area / "runtime-context"
    context.mkdir()
    (context / "output").mkdir()
    for name in ("build", "public"):
        budget()
        shutil.copytree(area / "out" / name, context / "output" / name)
    shutil.copyfile(dockerfile, context / "Dockerfile")
    expected = dict(files)
    expected["Dockerfile"] = sha(dockerfile.read_bytes())
    need(tree(context) == expected, "IMAGE_CONTEXT_HASHES_MISMATCH")
    image_tag = "serena-documenso-build:run-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    iidfile = area / "runtime-image.id"
    runner(runtime_image_plan(context, image_tag, iidfile), timeout=budget())
    image = json.loads(runner(["docker", "image", "inspect", image_tag, "--format", "{{json .}}"], timeout=budget()))
    proof = verify_runtime_image(base, image)
    need(iidfile.read_text().strip() == proof["image_id"], "BUILT_IMAGE_ID_MISMATCH")
    need(free() >= proof["image_size_bytes"] + MAX_RELEASE_ASSET + 1024**3, "IMAGE_EXPORT_DISK_RESERVE_UNPROVEN")
    raw = area / "runtime-image.docker-save.tar"
    runner(["docker", "image", "save", "--output", str(raw), proof["image_id"]], timeout=budget())
    need(raw.is_file() and not raw.is_symlink() and raw.stat().st_size > 0, "DOCKER_SAVE_OUTPUT_INVALID")
    artifact = bundle / "documenso-runtime-image.tar.gz"
    with raw.open("rb") as source, artifact.open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0, compresslevel=1) as compressed:
            while chunk := source.read(1024 * 1024):
                budget()
                need(free() >= 1024**3, "IMAGE_EXPORT_DISK_RESERVE_LOST")
                compressed.write(chunk)
                need(target.tell() < MAX_RELEASE_ASSET, "RELEASE_ASSET_SIZE_LIMIT")
    proof.update({"archive": artifact.name, **file_proof(artifact, budget=budget),
                  "archive_format": "gzip-compressed docker image save archive, loadable by docker image load",
                  "dockerfile_sha256": sha(dockerfile.read_bytes()), "context_files": expected,
                  "load_command": ["docker", "image", "load", "--input", artifact.name],
                  "packaging_network_option": "none", "pull_option": False, "copy_only": True,
                  "vps_build_required": False, "deployment_executed": False, "runtime_tested": False})
    save(bundle / "runtime-image-manifest.json", proof)
    print(json.dumps({"runtime_image_packaged": True, "image_id": proof["image_id"], "sha256": proof["sha256"], "bytes": proof["bytes"], "runtime_tested": False}), flush=True)
    return proof


def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def safe(relative):
    p = PurePosixPath(relative)
    need(relative and not p.is_absolute() and not re.search(r"[\\:\x00-\x1f]", relative), "PATH_INVALID")
    need(all(x not in ("", ".", "..") for x in relative.split("/")), "PATH_INVALID")
    return relative


def tree(folder):
    result = {}
    for path in sorted(folder.rglob("*")):
        need(not path.is_symlink(), "SYMLINK_FORBIDDEN")
        if path.is_file():
            result[safe(path.relative_to(folder).as_posix())] = sha(path.read_bytes())
    return result


def command(args, timeout=120):
    return subprocess.run(args, check=True, timeout=timeout, text=True, stdout=subprocess.PIPE).stdout.strip()


class AllowedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        need(urllib.parse.urlparse(newurl).hostname in ("codeload.github.com", "registry.npmjs.org"), "DOWNLOAD_REDIRECT_ORIGIN_FORBIDDEN")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, target, expected=None, integrity=None):
    parsed = urllib.parse.urlparse(url)
    need(parsed.scheme == "https" and parsed.hostname in ("codeload.github.com", "registry.npmjs.org") and parsed.username is None, "DOWNLOAD_ORIGIN_FORBIDDEN")
    need(not target.exists(), "DOWNLOAD_TARGET_EXISTS_NO_RETRY")
    digest = hashlib.sha256()
    sri = None
    if integrity:
        candidates = integrity.split()
        algorithm = next(a for a in ("sha512", "sha384", "sha256") if any(s.startswith(a + "-") for s in candidates))
        sri = hashlib.new(algorithm)
    size = 0
    with urllib.request.build_opener(AllowedRedirects()).open(url, timeout=30) as response, target.open("xb") as out:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            need(size <= 256 * 1024**2, "DOWNLOAD_SIZE_LIMIT")
            digest.update(chunk)
            if sri:
                sri.update(chunk)
            out.write(chunk)
    need(expected is None or digest.hexdigest() == expected, "DOWNLOAD_SHA_MISMATCH")
    need(sri is None or sri.name + "-" + base64.b64encode(sri.digest()).decode() in integrity.split(), "DOWNLOAD_SRI_MISMATCH")
    return {"bytes": size, "sha256": digest.hexdigest()}


def extract(archive, target):
    prefix = "documenso-" + COMMIT + "/"
    seen = set()
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            if member.name.rstrip("/") == prefix.rstrip("/"):
                continue
            need(member.name.startswith(prefix), "ARCHIVE_ROOT_MISMATCH")
            relative = safe(member.name[len(prefix):].rstrip("/"))
            need(relative.casefold() not in seen, "ARCHIVE_COLLISION")
            seen.add(relative.casefold())
            dest = target / relative
            need(member.isdir() or member.isfile(), "ARCHIVE_LINK_OR_SPECIAL_FILE")
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                need(member.size <= 64 * 1024**2, "ARCHIVE_MEMBER_TOO_LARGE")
                dest.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as inp, dest.open("xb") as out:
                    shutil.copyfileobj(inp, out, 1024 * 1024)
                dest.chmod(0o755 if member.mode & 0o111 else 0o644)


def available_memory():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MEMORY_METADATA_UNAVAILABLE")


def run_container(stage, area, start):
    need(available_memory() >= CAP + 2 * 1024**3, "RUNNER_MEMORY_RESERVE_UNPROVEN")
    name = "serena-public-build-" + stage + "-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    args = ["docker", "container", "create", "--pull=never", "--name", name, "--cpus=2", "--memory=" + str(CAP), "--memory-swap=" + str(CAP), "--pids-limit=512", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--user=1001:1001", "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456,uid=1001,gid=1001"]
    for source, dest, readonly in ((ROOT, "/builder", True), (area / "source", "/src", True), (area / "cache", "/cache", True), (area / "work", "/work", False), (area / "out", "/out", False)):
        args += ["--mount", "type=bind,source=" + str(source) + ",target=" + dest + (",readonly" if readonly else "")]
    cid = command(args + ["--entrypoint", "node", BASE, "/builder/container-build.mjs", stage])
    need(re.fullmatch("[0-9a-f]{64}", cid), "CONTAINER_ID_INVALID")
    result = {"stage": stage, "container_id": cid, "success": False}
    try:
        command(["docker", "start", cid])
        while True:
            state = json.loads(command(["docker", "inspect", "--format", "{{json .State}}", cid]))
            if not state["Running"]:
                result.update(exit_code=state["ExitCode"], oom_killed=state["OOMKilled"])
                break
            need(time.monotonic() - start < DEADLINE, "BUILD_DEADLINE_EXCEEDED")
            need(available_memory() >= 2 * 1024**3, "RUNNER_MEMORY_RESERVE_LOST")
            time.sleep(2)
        need(result["exit_code"] == 0 and result["oom_killed"] is False, "STAGE_FAILED_NO_RETRY")
        result["success"] = True
    finally:
        command(["docker", "stop", "--time=5", cid], timeout=20)
        log = subprocess.run(["docker", "logs", cid], check=False, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
        (area / "out" / (stage + ".log")).write_bytes(log)
        command(["docker", "rm", cid])
        result["removed_and_absent"] = command(["docker", "ps", "-a", "--no-trunc", "--filter", "id=" + cid, "--format", "{{.ID}}"] ) == ""
        save(area / "out" / (stage + "-result.json"), result)
        print(json.dumps(result), flush=True)
        if result["success"] is False:
            print(log[-262144:].decode("utf-8", errors="replace"), flush=True)
            builder_log = area / "out/builder.log"
            if builder_log.is_file():
                with builder_log.open("rb") as stream:
                    stream.seek(max(0, builder_log.stat().st_size - 262144))
                    print(stream.read(262144).decode("utf-8", errors="replace"), flush=True)
    need(result["removed_and_absent"], "CONTAINER_CLEANUP_UNCONFIRMED")


def build():
    need(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "ONLY_SEPARATE_PUBLIC_CI_EXECUTOR")
    need(not os.environ.get("GITHUB_TOKEN") and not os.environ.get("GH_TOKEN"), "TOKEN_MUST_NOT_ENTER_BUILD_STEP")
    manifest = read_json(ROOT / "patch-manifest.json")
    need(sha((ROOT / manifest["patch"]["path"]).read_bytes()) == manifest["patch"]["sha256"], "PATCH_CHANGED")
    need(sha((ROOT / manifest["logo"]["path"]).read_bytes()) == manifest["logo"]["sha256"], "LOGO_CHANGED")
    area = Path(os.environ["RUNNER_TEMP"]) / ("serena-build-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"])
    need(not area.exists() and shutil.disk_usage(area.parent).free >= 12 * 1024**3, "FRESH_RUNNER_OR_DISK_RESERVE_REQUIRED")
    area.mkdir()
    for name in ("source", "cache", "work", "out"):
        (area / name).mkdir()
    command(["sudo", "chown", "1001:" + str(os.getgid()), str(area / "work"), str(area / "out")])
    command(["sudo", "chmod", "0770", str(area / "work"), str(area / "out")])
    archive = area / "official.tar.gz"
    download(manifest["upstream"]["archive_url"], archive, manifest["upstream"]["archive_sha256"])
    extract(archive, area / "source")
    for row in manifest["files"]:
        path = area / "source" / safe(row["path"])
        need((sha(path.read_bytes()) if path.exists() else None) == row["original_sha256"], "ORIGINAL_SOURCE_MISMATCH")
    git_apply = ["git", "-c", "core.autocrlf=false", "-c", "core.whitespace=cr-at-eol", "apply"]
    subprocess.run(git_apply + ["--check", str(ROOT / "patches/signing-ui.patch")], cwd=area / "source", check=True, timeout=30)
    subprocess.run(git_apply + [str(ROOT / "patches/signing-ui.patch")], cwd=area / "source", check=True, timeout=30)
    for row in manifest["files"]:
        need(sha((area / "source" / row["path"]).read_bytes()) == row["patched_sha256"], "PATCHED_SOURCE_MISMATCH")
    need(sha((area / "source/package-lock.json").read_bytes()) == LOCK, "ORIGINAL_LOCK_CHANGED")
    save(area / "work/source-index.json", {"files": tree(area / "source")})
    original = read_json(area / "source/package-lock.json")
    bootstrap = []
    for name in ("turbo", "@turbo/linux-64"):
        item = original["packages"]["node_modules/" + name]
        need(item["version"] == "2.10.5", "BOOTSTRAP_VERSION_MISMATCH")
        filename = sha(item["resolved"].encode()) + ".tgz"
        proof = download(item["resolved"], area / "cache" / filename, integrity=item["integrity"])
        bootstrap.append({"name": name, "version": item["version"], "file": filename, **proof})
    save(area / "work/bootstrap-index.json", {"entries": bootstrap})
    command(["docker", "pull", BASE], timeout=300)
    start = time.monotonic()
    run_container("prune", area, start)
    derived_bytes = (area / "out/pruned-package-lock.json").read_bytes()
    need(sha(derived_bytes) == DERIVED, "DERIVED_LOCK_CHANGED")
    derived = json.loads(derived_bytes)
    downloads = {}
    for key, value in derived["packages"].items():
        need(key in original["packages"], "DERIVED_NEW_LOCK_ENTRY")
        before = original["packages"][key]
        if "node_modules/" in key and not value.get("link"):
            need(all(value.get(k) == before.get(k) for k in ("version", "resolved", "integrity")), "DERIVED_DEPENDENCY_CHANGED")
            need(value.get("resolved") and value.get("integrity"), "LOCK_ENTRY_WITHOUT_URL_SRI")
            downloads[value["resolved"]] = value["integrity"]
    entries = []
    for url, integrity in sorted(downloads.items()):
        filename = sha(url.encode()) + ".tgz"
        path = area / "cache" / filename
        proof = download(url, path, integrity=integrity) if not path.exists() else {"bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
        entries.append({"file": filename, "integrity": integrity, **proof})
    save(area / "work/dependency-index.json", {"entries": entries})
    run_container("install", area, start)
    run_container("build", area, start)
    output = area / "out"
    output_tree = tree(output)
    files = {"output/" + p: h for p, h in output_tree.items() if p.startswith(("build/", "public/"))}
    need(files and any(p.startswith("output/build/") for p in files), "BUILD_OUTPUT_EMPTY")
    bundle = ROOT / "release"
    bundle.mkdir()
    index = {"upstream_commit": COMMIT, "original_lock_sha256": LOCK, "derived_lock_sha256": DERIVED, "base_image": BASE, "patch_manifest_sha256": sha((ROOT / "patch-manifest.json").read_bytes()), "ci_commit": os.environ["GITHUB_SHA"], "ci_run_id": os.environ["GITHUB_RUN_ID"], "files": files, "runtime_production_data": False, "database_connected": False, "signature_qa": False}
    save(bundle / "build-manifest.json", index)
    artifact = bundle / "documenso-build-public.tar.gz"
    with tarfile.open(artifact, "w:gz") as tar:
        for name in ("build", "public"):
            tar.add(output / name, arcname="output/" + name, recursive=True)
        tar.add(ROOT / "Dockerfile.output", arcname="Dockerfile")
    need(artifact.stat().st_size < 2 * 1024**3, "RELEASE_ASSET_SIZE_LIMIT")
    image_proof = package_runtime_image(area, bundle, files, start)
    index["runtime_image"] = {"manifest": "runtime-image-manifest.json", "image_id": image_proof["image_id"], "archive": image_proof["archive"], "sha256": image_proof["sha256"], "vps_build_required": False}
    save(bundle / "build-manifest.json", index)
    save(bundle / "build-results.json", {s: read_json(output / (s + "-result.json")) for s in ("prune", "install", "build")})
    logs = [(output / (s + ".log")).read_bytes() for s in ("prune", "install", "build")]
    logs.append((output / "builder.log").read_bytes())
    (bundle / "build.log").write_bytes(b"\n".join(logs))
    checksums = {p.name: file_proof(p, budget=lambda: remaining_budget(start))["sha256"] for p in bundle.iterdir() if p.is_file()}
    save(bundle / "SHA256.json", checksums)
    print(json.dumps({"built": True, "released": False, "deployed": False, "artifact_sha256": checksums[artifact.name]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "build"), nargs="?", default="plan")
    args = parser.parse_args()
    if args.action == "plan":
        print(json.dumps({"executor": REPOSITORY, "base_image": BASE, "memory_bytes": CAP, "deadline_seconds": DEADLINE, "runs_build": False}))
    else:
        build()
